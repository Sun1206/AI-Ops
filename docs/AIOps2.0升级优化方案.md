# AIOps 2.0 升级优化方案

本文记录 AI Ops AIOps 2.0 的升级目标、架构调整点、核心能力清单与当前落地状态。它是平台智能体能力从“问答助手”走向“受控运维 Agent”的架构演进说明。

## 1. 升级定位

AIOps 2.0 的目标不是增加一个通用聊天入口，而是把 AI 能力做进 AI Ops 的运维控制面：让 assistant 理解用户所在页面、知识图谱关联对象、环境、告警、变更、日志、链路、K8s、发布任务、工单和值班上下文，并通过受控工具完成分析、推荐和待确认操作。

核心定位：

- 从“问答助手”升级为“可配置的运维 Agent 平台”。
- 从“单一大模型回复”升级为“意图路由 + Action 任务入口 + Skill 能力包 + 受控工具 + 结构化 UI”。
- 从“自然语言建议”升级为“证据链、预检、确认流、审计流闭环”。
- 从“平台内浮窗”升级为“Web assistant + MCP/A2A 互操作能力”。

## 2. 设计原则

1. 平台 API 是唯一执行边界  
   LLM 只负责理解、规划和生成候选参数，所有查询、创建、修改、执行动作都必须通过后端工具层调用平台 API，不能绕过 RBAC、审计和参数校验。

2. Action 负责任务入口和流程策略  
   Action 是稳定的后端协议，负责识别任务类型、选择 agent 模式、声明风险等级、预检 schema、输出 block、默认 Skill 和安全策略。

3. Skill 负责能力包沉淀  
   Skill 是可复用能力包，负责 SOP、证据清单、工具依赖、查询规范、输出要求和安全边界。一个 Action 可以加载多个 Skill，一个 Skill 也可以被多个 Action 复用。

4. 结构化响应驱动前端交互  
   assistant 返回 Markdown 之外，还要返回结构化 block，让前端可以渲染事件卡片、证据时间线、查询建议、审批表单、回滚计划、自愈推荐和待确认按钮。

5. 先预检，再确认，再执行  
   创建、修改、执行类动作必须先补齐关联对象、环境、集群、命名空间、服务、时间窗口、审批人等关键参数，再进入 dry-run、人工确认和审计执行。

6. 自愈默认推荐，不默认执行  
   自愈能力先给出候选脚本、风险说明、适用范围、回滚方案和执行 marker。真正执行必须经过用户确认、权限校验和审计记录。

7. 后端权限强制，前端权限镜像  
   后端先做 RBAC 强制控制；前端只负责隐藏入口、按钮和操作列，不能作为安全边界。

## 3. 总体架构调整

```text
页面上下文 / 全局聊天 / 外部 Agent
        |
        v
AIOps API 层
        |
        v
会话与流式状态层
        |
        v
Action Router
        |
        +--> Direct Agent
        +--> ReAct Agent
        +--> Plan + ReAct Agent
        |
        v
Skill Registry + Tool Registry + MCP Registry
        |
        v
平台 API 安全封装层
        |
        v
知识图谱 / 监控告警 / 日志 / 链路 / K8s / CI-CD / Git / 制品库 / 工单 / 值班 / 任务中心 / 自愈
```

关键变化：

- `Action Router` 负责识别任务类型，不直接执行业务动作。
- `Agent Kernel` 支持 Direct、ReAct、Plan + ReAct 三类模式。
- `Skill Registry` 负责加载能力包、工具依赖、输出约束和场景模板。
- `Tool Registry` 负责暴露平台能力、校验参数、执行权限和记录审计。
- `Structured Block Renderer` 负责把 AI 输出转成可交互 UI。
- `State Store` 负责会话状态、消息流、取消信号、并发锁和恢复能力。

## 4. Action 与 Skill 的边界

Action 和 Skill 的边界要按“任务入口”和“能力包”拆开，避免两个配置页都变成一组相似的提示词、工具和风险字段。

核心定义：

- Action 是用户意图进入平台任务的分类入口，也负责流程和安全策略，回答“这次属于哪类任务、需要哪些上下文、按什么流程做、是否需要预检或确认、输出什么结构、风险边界是什么”。
- Skill 是可复用能力包，回答“完成这类任务需要哪些专业能力、工具依赖、SOP、证据清单、查询规范、风险判断和回答格式”。

运行关系：

- 用户问题先进入 Action Router，识别一个主 Action。
- Action 根据任务分类决定 agent 模式、预检表单、输出 block、风险等级、确认流和默认加载的 Skill。
- Skill 声明工具依赖、MCP 能力、SOP、证据清单、字段规范、判断规则和回答格式。
- 最终可用工具不是 Action 或 Skill 单独决定，而是 `选中 Skill 的工具依赖 ∩ MCP 当前可用工具 ∩ 用户 RBAC ∩ Action 安全策略`。
- Action 不直接堆叠工具列表；Action 只保留安全策略兜底，例如只读、草稿、写入、执行、是否允许高风险工具、是否必须 preflight。

字段归属：

| 归属 | 字段 | 含义 |
| --- | --- | --- |
| Action 独占 | `agent_mode` | 决定 Direct、ReAct、Plan+ReAct 等执行编排方式。 |
| Action 独占 | `required_context` | 执行前必须具备的环境、服务、集群、时间窗口等上下文。 |
| Action 独占 | `preflight_schema` | 缺参、写入或执行前的表单补齐协议。 |
| Action 独占 | `rbac_permissions` | 发起、确认、执行所需权限。 |
| Action 独占 | `output_schema` | 前端结构化 block 协议。 |
| Action 负责 | `suggested_questions` | 典型用户问题示例，用于展示任务入口和辅助意图路由。 |
| Action 负责 | `skills` | 默认加载哪些能力包。 |
| Action 负责 | `tool_policy` | 安全策略兜底，例如只读/可写/需确认/禁止高危工具。当前实现可继续兼容旧 `allowed_tools` 字段，但 UI 和文档不把它作为主设计入口。 |
| Skill 负责 | `content` | SOP、证据清单、查询规范、安全边界、回答格式。 |
| Skill 负责 | `tool_dependencies` | 能力包需要的 MCP/API/CLI 工具依赖。当前实现对应 `builtin_tools` 和 `recommended_tools`。 |
| Skill 负责 | `applicable_actions` | 声明这个能力包可挂载到哪些 Action。 |
| Skill 负责 | `output_contract` | 输出指导，只约束表达方式，不替代 Action 的结构化响应 schema。 |
| Skill 负责 | `risk_level` | 知识包风险提示，不作为执行权限或工具调用权限。 |

页面呈现原则：

- Action 页面按“任务入口”展示，突出任务分类、示例入口、上下文、预检、风险等级、输出结构和关联 Skill。
- Skill 页面按“能力包”展示，突出工具依赖、SOP、证据清单、适用 Action、风险提示和输出指导。
- Action 页面不再把工具作为核心字段展示；工具主要从 Skill 能力包来。
- Skill 的工具依赖也不是无边界执行权限，最终仍要经过 MCP 可用性、RBAC 和 Action 安全策略过滤。

示例映射：

| Action | 默认加载 Skill |
| --- | --- |
| `alert.root_cause` | 告警证据清单、K8s 告警排障、日志模式分析、变更影响分析、回答整形 |
| `change.correlation` | 变更影响分析、事件时间线关联、回答整形 |
| `log.query_generate` | 日志查询规范、日志字段字典、回答整形 |
| `k8s.diagnose` | K8s 排障、容器只读取证、安全边界、回答整形 |
| `self_heal.recommend` | 自愈风险护栏、任务模板选择、回滚策略、回答整形 |

典型入口问题归 Action，不归 Skill。Skill 可以保留“适用场景样例”，但 UI 上不应把它表现成任务入口。

## 5. Action Router 设计

P0 先内置以下 Action：

| Action | 目标场景 | 示例入口 |
| --- | --- | --- |
| `alert.root_cause` | 告警根因分析 | 分析这条告警为什么触发 |
| `change.correlation` | 变更关联分析 | 最近哪些变更可能影响这个服务 |
| `log.query_generate` | 日志查询生成 | 帮我生成订单服务错误日志查询 |
| `metric.query_generate` | PromQL/指标查询生成 | 帮我生成错误率和 P95 延迟查询 |
| `k8s.diagnose` | K8s 排障 | 这个命名空间有哪些 Pod 异常 |
| `deploy.failure_diagnose` | 发布失败诊断 | 这次发布失败可能是什么原因 |
| `slo.analysis` | SLO/服务健康分析 | 当前服务健康度下降受哪些指标影响 |
| `self_heal.recommend` | 自愈推荐 | 这个故障适合自愈吗 |
| `notification.policy_suggest` | 通知和升级策略建议 | 这个告警应该通知谁并如何升级 |
| `runbook.generate` | Runbook 生成 | 把这次故障沉淀成 Runbook |

每个 Action 至少定义：

- `code`：稳定编码。
- `display_name`：前端展示名称。
- `risk_level`：`read_only` / `draft` / `write` / `execute`。
- `agent_mode`：`direct` / `react` / `plan_react`。
- `required_context`：必须具备的上下文。
- `skills`：默认加载 Skill slug。
- `preflight_schema`：缺参时返回的表单 schema。
- `output_schema`：结构化响应 block schema。
- `rbac_permissions`：发起、确认、执行所需权限。
- `suggested_questions`：典型用户入口问题。
- `tool_policy`：工具安全策略兜底，例如只读、需确认、禁止高危执行。

## 6. Skill 库设计

Skill 是 AI Ops assistant 的领域能力包，可以声明工具依赖，但不能绕过平台权限和 Action 安全策略直接执行。Skill 管理的重点是“让 assistant 在某一类问题上具备稳定专业能力”，而不是堆叠零散的一句话提示词。

### Skill 包结构

每个 Skill 至少包含：

- `name`：名称。
- `slug`：稳定标识。
- `category`：问题分类，例如告警排障、日志查询、K8s 诊断、自愈安全。
- `description`：适用场景摘要。
- `applicable_actions`：可复用到哪些 Action。
- `tool_dependencies`：能力包需要的 MCP/API/CLI 工具依赖，当前实现对应 `builtin_tools` 和 `recommended_tools`。
- `examples`：方法适用场景样例，不作为任务入口展示。
- `max_iterations`：建议最大推理/工具轮次，0 表示完全由 Action 决定。
- `risk_level`：知识包风险提示，用于提醒方法风险，不作为执行权限。
- `output_contract`：输出指导，用于约束回答组织方式，不替代 Action 的结构化响应 schema。
- `content`：完整 SOP、证据清单、查询规范、安全约束和回答格式。

### P0 内置 Skill

- `sx-alert-evidence-checklist`：告警根因分析证据清单，约束必须输出结论、证据、影响范围和下一步动作。
- `sx-k8s-alert-troubleshooting`：K8s 告警排障，约束集群、命名空间、工作负载、Pod、Event、日志和资源状态取证顺序。
- `sx-log-pattern-analysis`：日志模式分析，约束字段、过滤条件、时间范围、聚合方式和样本解释。
- `sx-change-impact-analysis`：变更影响分析，约束时间窗口、发布记录、工单、事件和知识图谱依赖关系。
- `sx-log-query-guide`：日志查询生成规范，约束查询语句、过滤项、字段解释和可复制输出。
- `sx-log-field-dictionary`：日志字段字典，沉淀 service、level、trace_id、span_id、pod、namespace 等字段含义。
- `sx-k8s-troubleshooting`：K8s 排障 SOP，覆盖 Pending、CrashLoopBackOff、ImagePull、探针失败、资源不足等场景。
- `sx-container-readonly-guard`：容器只读取证安全边界，禁止 assistant 直接执行集群或主机写操作。
- `sx-self-heal-risk-guard`：自愈风险护栏，约束推荐、dry-run、确认、执行、审计和回滚。
- `sx-task-template-selection`：任务模板选择，约束如何匹配任务中心模板与目标资源。
- `sx-rollback-strategy`：回滚策略，约束回滚前置条件、影响范围、验证项和失败处理。
- `answer-formatter`：回答整形器，负责把工具事实整理成稳定的最终回答。

### 自定义 Skill

团队可在平台内创建自定义 Skill，用于沉淀团队自己的 Runbook、排障 SOP、日志字段规范、发布回滚策略、K8s 常见故障处理、数据库故障处理和自愈脚本规范。

自定义 Skill 必须遵守：

- 必须声明适用 Action，不允许成为无边界的通用提示词。
- 必须声明风险提示和工具依赖。
- 写入或执行类 Skill 必须包含预检、确认、dry-run、审计和回滚要求。
- 不允许把密钥、token、kubeconfig、证书等敏感信息写入内容。

## 7. 工具层升级

工具层是 AIOps 2.0 的安全边界。所有工具必须是平台 API 的后端封装，不允许模型直接拼接数据库查询或绕过服务层。

工具统一规范：

- `name`：工具名。
- `description`：模型可见说明。
- `input_schema`：参数 schema。
- `output_schema`：返回 schema。
- `permission`：所需权限。
- `risk_level`：风险等级。
- `timeout`：超时时间。
- `rate_limit`：限流策略。
- `audit_event`：审计事件类型。
- `dry_run_supported`：是否支持 dry-run。
- `preflight_required`：是否必须预检。
- `idempotency_key`：写入或执行类动作的幂等键。

建议工具分组：

- 知识图谱：服务、环境关联、负责人、依赖关系、上下游拓扑。
- 监控告警：当前告警、历史告警、告警规则、订阅、屏蔽、通知策略。
- 指标查询：指标数据源、PromQL 生成、指标曲线、服务健康。
- 日志查询：日志数据源、字段字典、查询生成、错误日志聚合。
- 链路追踪：Trace 查询、Span 错误、慢调用、上下游依赖。
- K8s：集群、命名空间、Workload、Pod、Event、容器日志、资源用量。
- CI-CD：发布任务、构建日志、部署记录、回滚候选。
- Git 与制品：提交、分支、Tag、制品版本、镜像信息。
- 工单和值班：工单、审批人、值班表、升级策略。
- 任务中心：任务模板、巡检任务、执行历史、脚本 dry-run。
- 自愈：候选脚本、适用条件、风险评估、执行 marker。
- SQL 审计：数据源、查询申请、审批、执行审计。

## 8. 结构化响应协议

AIOps 2.0 需要把“回答内容”和“前端可交互对象”分开。建议每次回复包含：

```json
{
  "answer": "面向用户的自然语言总结",
  "blocks": [],
  "actions": [],
  "trace": [],
  "citations": []
}
```

建议内置 block：

| Block | 用途 |
| --- | --- |
| `incident_card` | 故障或异常摘要卡片 |
| `evidence_timeline` | 告警、日志、链路、变更证据时间线 |
| `query_suggestion` | PromQL、SQL、LogQL 等查询建议 |
| `chart_query` | 可直接跳转或渲染的指标查询 |
| `alert_rule_draft` | 告警规则草稿 |
| `dashboard_draft` | 仪表盘草稿 |
| `change_candidate` | 可能相关的变更记录 |
| `rollback_plan` | 发布回滚计划 |
| `k8s_action` | K8s 操作建议或待确认动作 |
| `self_heal_recommendation` | 自愈推荐卡片 |
| `approval_form` | 待补参或待确认表单 |
| `tool_trace` | 工具调用追踪 |
| `risk_notice` | 风险提示 |

## 9. Preflight 与确认流

创建、修改、执行类 Action 必须走统一流程：

1. 用户提出目标。
2. Action Router 识别 Action。
3. Agent 检查缺失参数。
4. 返回 `approval_form` 或 `preflight_form`。
5. 用户补齐关联对象、环境、集群、命名空间、服务、时间窗口、审批人等信息。
6. 后端校验 RBAC、参数 schema、资源范围和风险等级。
7. 生成 dry-run 或草稿。
8. 用户二次确认。
9. 后端执行平台 API。
10. 记录审计、工具调用、执行结果和可回溯链路。

## 10. MCP/A2A 互操作

AI Ops 不只服务 Web 页面，也要服务外部 Agent 编排平台。

AI Ops 作为 MCP Server：

- 暴露知识图谱、告警、日志、链路、K8s、发布、工单、任务中心等只读工具。
- 写入和执行类工具默认要求 preflight 和用户确认。
- 统一鉴权、权限过滤、审计和限流。

AI Ops 接入外部 MCP：

- 管理外部 MCP Server 配置。
- 做健康检查、工具发现、权限绑定和超时控制。
- 外部工具输出必须进入事实集，不能直接变成最终回答。

A2A 方向在产品界面上命名为“协同任务 / Runbook”，避免把协议名直接暴露给普通运维用户：

- 支持外部系统或 Agent 创建 AIOps 协同任务草案。
- 支持任务状态查询、取消、结果回调。
- 支持跨系统编排时保留用户身份、权限和审计链路。

## 11. 落地优先级

### P0：AIOps assistant 基座

| 状态 | 任务 | 当前落地说明 |
| --- | --- | --- |
| 已完成 | LLM 配置中心升级为 Provider + Model Profile | 已落地 Provider 管理、默认/备用模型、连接测试、模型拉取、输入/输出 Token 单价配置。当前未单独拆出 Model Profile 表，先由 Provider 字段承载。 |
| 已完成 | 会话流式响应、取消、恢复和 ChatLock | 已有会话、消息、异步发送、取消信号、上下文恢复和并发保护基础能力。 |
| 已完成 | Action registry 初版 | 已内置 Action 注册表，覆盖告警根因、变更关联、日志/指标查询生成、K8s 诊断、发布失败诊断、自愈建议、Runbook 生成等入口。 |
| 已完成 | RBAC 工具层和工具 schema 规范 | 后端 RBAC 强制校验，前端只做入口镜像；工具调用统一记录权限、入参、结果、耗时和状态。 |
| 已完成 | 页面上下文注入 | 已支持从页面和知识环境注入上下文，结合环境、服务、集群、日志、链路、事件等范围做分析。 |
| 已完成 | 结构化响应 block 协议 | 已支持 `approval_form`、工具追踪、任务草案等结构化对象；前端可渲染确认和审计信息。 |
| 已完成 | Skill 库初版 | 已内置告警证据、K8s 排障、日志分析、变更影响、自愈护栏、任务模板、回滚策略、回答整形等 Skill。 |
| 已完成 | 工具调用追踪和基础审计 | 已有会话审计、工具调用审计、待确认动作审计，并扩展模型调用审计。 |

### P1：能力增强

| 状态 | 任务 | 当前落地说明 |
| --- | --- | --- |
| 已完成 | Skill 市场和团队自定义 Skill | 已支持内置 Skill 市场、团队克隆、自定义 Skill、适用 Action、工具依赖、风险等级和输出约束。 |
| 已完成初版 | MCP 接入与对外暴露 | 已支持外部 MCP Server 配置、健康检查和工具发现；2.1 新增 AI Ops 对外 MCP Server，只暴露只读平台工具，并接入统一 Token 鉴权、RBAC、限流和事件审计。 |
| 已完成 | preflight 表单 | 已提供 `POST /api/aiops/admin/actions/preflight/`，可按 Action 返回缺参、风险、权限和 `approval_form` 合同。 |
| 已完成 | AI 执行审计 | 已覆盖会话、工具调用、待确认动作、模型调用、协同任务和 Runbook 的审计数据。 |
| 已完成 | 工具调用追踪详情 | 已有工具调用列表、详情展开、单条/批量删除和失败信息展示。 |
| 已完成 | 模型连接测试和模型列表 | 已支持 Provider 连接测试、模型列表拉取、推荐模型和超时/连接错误提示。 |
| 已完成 | 模型成本统计 | 已记录模型调用 Token、耗时、用途、Provider、请求模型/实际模型和估算成本，提供 `GET /api/aiops/admin/audit/costs/` 成本概览。 |
| 部分完成 | 工具调用成本统计 | 当前已统计工具调用次数、耗时和按工具聚合；尚未引入工具级单价，因此不是严格货币成本。 |

### P2：深度编排

| 状态 | 任务 | 当前落地说明 |
| --- | --- | --- |
| 已完成初版 | A2A | 后端已新增 `AIOpsExternalTask` 和 `/api/aiops/a2a/tasks/`，前端以“外部协同任务”展示，支持创建任务草案、查看状态和取消。 |
| 已完成初版 | 多 Agent 编排 | 2.1 已拆出诊断 Agent、证据 Agent、变更 Agent、Runbook Agent，并在协同任务中记录 Agent 分工、结果和合并规则。 |
| 已完成初版 | Plan + ReAct 深度排障 | 2.1 已支持计划、执行、观察、修正、终止条件和用户中断，协同任务可运行或中断并保留 `react_trace`。 |
| 已完成增强 | 自动生成 Runbook | 后端已新增 `AIOpsRunbook` 和 `/api/aiops/runbooks/draft/`；2.1 补齐从事故会话生成、发布、归档、版本历史和引用来源。 |
| 已完成初版 | 自动沉淀复盘知识 | 2.1 新增 `AIOpsReviewKnowledge`，支持从事故会话、协同任务和 Runbook 自动沉淀并检索复盘知识。 |

## 12. 当前接口与数据模型清单

### 新增和扩展的数据模型

- `AIOpsModelProvider`：新增 `input_token_price_per_1m`、`output_token_price_per_1m`，用于模型成本估算。
- `AIOpsModelInvocation`：记录模型调用、Token、模型、用途、耗时、错误和估算成本。
- `AIOpsExternalTask`：记录外部系统或 Agent 提交的协同任务草案，2.1 新增 `orchestration_state`、`agent_results` 和 `react_trace`。
- `AIOpsRunbook`：记录 Runbook 手册草案、发布/归档状态、版本号和引用来源。
- `AIOpsRunbookVersion`：记录 Runbook 每次发布/归档快照、变更说明、证据和来源引用。
- `AIOpsReviewKnowledge`：记录由事故会话、协同任务和 Runbook 自动沉淀的可检索复盘知识。

### 新增和关键接口

- `GET /api/aiops/admin/skills/marketplace/`：查看内置 Skill 市场。
- `POST /api/aiops/admin/skills/{id}/clone/`：把内置 Skill 克隆为团队 Skill。
- `POST /api/aiops/admin/actions/preflight/`：获取 Action 预检和确认表单合同。
- `GET /api/aiops/admin/audit/model-invocations/`：查看模型调用审计。
- `GET /api/aiops/admin/audit/costs/`：查看模型成本和工具调用概览，兼容无尾斜杠。
- `GET /api/aiops/mcp/manifest/`：查看 AI Ops 对外 MCP Server 清单、鉴权和限流信息。
- `GET /api/aiops/mcp/tools/`：查看对外 MCP 只读工具列表。
- `POST /api/aiops/mcp/rpc/`：以 JSON-RPC 方式执行 `initialize`、`tools/list` 和 `tools/call`。
- `POST /api/aiops/mcp/call/`：直接调用单个对外 MCP 只读工具。
- `GET/POST /api/aiops/a2a/tasks/`：查看或创建外部协同任务草案。
- `POST /api/aiops/a2a/tasks/{public_id}/run/`：运行多 Agent Plan + ReAct 编排。
- `POST /api/aiops/a2a/tasks/{public_id}/interrupt/`：中断多 Agent Plan + ReAct 编排。
- `POST /api/aiops/a2a/tasks/{public_id}/cancel/`：取消协同任务。
- `GET /api/aiops/runbooks/`：查看 Runbook 手册。
- `POST /api/aiops/runbooks/draft/`：生成 Runbook 手册草案。
- `POST /api/aiops/runbooks/from-session/`：从事故会话一键生成 Runbook 草案。
- `POST /api/aiops/runbooks/{id}/publish/`：发布 Runbook 并自动沉淀复盘知识。
- `POST /api/aiops/runbooks/{id}/archive/`：归档 Runbook 并生成版本快照。
- `GET /api/aiops/runbooks/{id}/versions/`：查看 Runbook 版本历史。
- `GET/POST /api/aiops/review-knowledge/`：查看或维护复盘知识。
- `POST /api/aiops/review-knowledge/auto-ingest/`：从会话、协同任务或 Runbook 自动沉淀复盘知识。

### 权限补充

- `aiops.a2a.view`：查看协同任务。
- `aiops.a2a.invoke`：创建或取消协同任务。
- `aiops.mcp.view`：查看 AI Ops 对外 MCP Server 工具清单。
- `aiops.mcp.invoke`：调用 AI Ops 对外 MCP 只读工具。
- `aiops.runbook.view`：查看 Runbook 手册。
- `aiops.runbook.manage`：生成、更新或删除 Runbook 手册。
- `aiops.review.view`：查看自动沉淀的复盘知识。
- `aiops.review.manage`：自动沉淀、编辑或删除复盘知识。

## 13. 运行与迁移注意事项

本次升级包含数据库结构变更。部署或本地调试时必须先执行：

```bash
cd backend
python manage.py migrate aiops
```

否则访问模型供应商、模型审计、协同任务或 Runbook 接口时，可能出现类似 `no such column: aiops_aiopsmodelprovider.input_token_price_per_1m` 的数据库错误。

如果后端使用 Daphne 启动，代码变更后需要手动重启：

```bash
cd backend
python -m daphne -b 0.0.0.0 -p 8000 sxdevops.asgi:application
```

前端变更至少执行：

```bash
cd frontend
npm run build
```

建议验收顺序：

1. `python manage.py check`
2. `python manage.py test aiops`
3. `python manage.py test rbac`
4. `npm run build`
5. 打开 `/aiops/config`，检查模型提供商、Skill、Action、协同任务 / Runbook、审计页签。

## 14. 当前完成状态

2.1 已补齐以下能力：

- AI Ops 作为 MCP Server 对外暴露只读平台工具，并接入统一鉴权、限流和审计。
- 多 Agent 编排：拆出诊断 Agent、证据 Agent、变更 Agent、Runbook Agent，并定义结果合并规则。
- 完整 Plan + ReAct 深度排障：支持计划、执行、观察、修正、终止条件和用户中断。
- Runbook 发布、归档、版本历史、引用来源和从事故会话一键生成。
- 自动复盘知识沉淀：把会话、工具证据、协同任务和 Runbook 关联成可检索知识。
- 真实执行器、跨系统回调和长任务恢复已经具备后端合同、管理页入口和测试覆盖，可按实际接入系统继续扩展。

## 15. 结论

AIOps 2.0 的价值在于把 AI 做进 AI Ops 的运维控制面，而不是外接一个通用 Bot。当前系统已经围绕“Action 合同 + Skill 知识包 + 权限工具层 + 结构化 UI + 安全执行闭环”形成主要闭环，P0/P1/P2 的核心能力均已落地。
