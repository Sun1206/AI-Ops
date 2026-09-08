# AIOps 2.1.2 Action Handler 与上下文 Copilot 设计

## 背景

AIOps 2.1 已具备模型供应商、平台 MCP、Skill、Action Registry、知识图谱环境、待确认动作、调用审计和成本统计。2.1.2 的目标不是新增一个聊天入口，而是把现有能力整理成更稳定的生产闭环：

- Action Handler 拆分：把意图识别、上下文预检、工具选择、提示词约束、结果解析从大运行时里解耦。
- 结构化预检/回复块：让用户在进入模型或工具执行前确认关键上下文，并让前端按类型渲染证据、查询、风险和确认表单。
- 页面上下文 Copilot：从告警、日志、容器、系统态势、任务等页面打开助手时，自动携带页面、对象、筛选条件和默认问题。

本阶段不处理协同任务、Runbook 和 A2A 编排，只把单轮问答与受控动作的确定性先打牢。

## 产品原则

1. Action 是入口合同

Action 负责定义“用户要完成什么事”，包括风险等级、必要上下文、允许工具、默认 Skill、输出块、权限边界和预检策略。模型不能绕过 Action 合同直接执行高风险动作。

2. Skill 是经验包

Skill 只提供 SOP、证据清单、字段规范、风险判断和回答格式，不承担权限判断。运行时按 Action 命中结果裁剪 Skill，避免把所有经验一次性塞入 Prompt。

3. 页面上下文是提示，不是隐式授权

页面上下文可以帮助助手预填环境、服务、集群、数据源、告警 ID、时间范围等字段，但写入、生成和自愈类动作仍需结构化预检或待确认动作。

4. 回答要可审计

每次命中的 Action、缺失字段、预检表单、调用工具、引用证据、回复块和动作决策都进入 message metadata，审计页可以按 Action/Skill/MCP 追踪。

## 后端设计

### Action Handler

新增轻量 Handler 层，围绕现有 `BUILTIN_ACTION_REGISTRY` 注册运行时行为。每个 Handler 可声明：

- `code`：对应 Action Registry 的 code。
- `match`：在规则命中之外补充页面上下文或关键词路由。
- `preflight`：返回缺失字段和候选项，不满足时直接生成结构化预检回复。
- `build_prompt_hints`：为运行时 Prompt 提供短提示，不再把完整分支逻辑塞进主 Prompt。
- `build_context_blocks`：根据页面上下文补充 `context_summary`、`query_suggestion` 等回复块。
- `run`：可选。直接调用现有确定性工具链，如告警、日志、K8s、任务草稿。

2.1.2 先覆盖高收益 Action：

- `alert.root_cause`
- `log.query_generate`
- `k8s.diagnose`
- `host_task.generate`
- `self_heal.recommend`
- `slo.analysis`
- `change.correlation`

### 结构化预检

预检返回统一 `approval_form` 或 `context_form` 块：

```json
{
  "type": "context_form",
  "title": "上下文预检",
  "summary": "已识别为日志查询生成，请确认环境和服务后继续。",
  "status": "needs_info",
  "metrics": [
    {"label": "Action", "value": "日志查询生成"},
    {"label": "缺失项", "value": "1 项"}
  ],
  "fields": [
    {
      "name": "service",
      "label": "服务/应用",
      "type": "text",
      "required": true,
      "value": "",
      "placeholder": "例如：订单服务"
    }
  ],
  "actions": [
    {"type": "reuse", "label": "带上下文继续", "value": "帮我查询电商测试环境订单服务最近 30 分钟 ERROR 日志"}
  ]
}
```

前端按 `fields` 渲染确认项；当前阶段先提供“复用提示/复制提示”动作，不直接提交复杂表单，避免扩大改造面。

### 页面上下文 Copilot

`AIOpsChatSession.context` 增加 `page_context`：

```json
{
  "page": "logs.query",
  "title": "日志查询",
  "route": "/logs/query",
  "params": {},
  "query": {"env": "test", "service": "order"},
  "hints": {
    "environment": "电商测试环境",
    "service": "订单服务",
    "datasource_type": "log"
  },
  "suggested_questions": [
    "查询订单服务最近 30 分钟 ERROR 日志"
  ]
}
```

处理流程：

1. 前端创建会话或发送消息时携带 `page_context`。
2. 后端写入会话上下文，并用它辅助环境识别、服务识别、Action 选择和预检候选。
3. 回复 metadata 中输出 `page_context`、`selected_action` 和 `response_blocks`。
4. 审计页继续读取现有 skill/action trace，不新增权限码。

## 前端设计

### 聊天入口

AIOps 组件根据当前路由生成页面上下文：

- 路由标题、path、params、query。
- query 中常见字段：`environment/env`、`service/app`、`cluster`、`namespace`、`alert_id`、`datasource_id`。
- 按页面生成快捷问题。

页面上下文在顶部工具条显示为紧凑标签：页面、环境、服务/集群。用户发送消息时自动附带，但输入框内容仍以用户原文为准。

### 回复块渲染

在现有 `response_blocks` 基础上补充支持：

- `context_summary`：展示页面上下文和预填字段。
- `context_form`：展示缺失字段、候选值和继续提问按钮。
- `query_suggestion`：可点击把查询建议放回输入框。
- `risk_notice`：展示动作风险和限制。

已存在的 `approval_form`、`tool_trace`、`evidence_timeline` 保持兼容。

## 验收标准

- 文档存在于 `docs/AIOps2.1.2-Action-Handler与上下文Copilot设计.md`，且不包含外部项目名称。
- 后端有独立 Action Handler 模块或等价拆分，不再只依赖主运行时硬编码分支。
- 发送消息支持 `page_context`，会话 context 会持久化页面上下文。
- 命中 Action 但缺上下文时，返回结构化 `context_form` 或 `approval_form` 块。
- 前端发送消息携带页面上下文，并能渲染 `context_summary`、`context_form`。
- `python manage.py test aiops` 和 `npm run build` 通过。
- 涉及中文的文件为 UTF-8，无新增乱码或替换字符。
