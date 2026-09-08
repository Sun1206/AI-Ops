# 贡献指南

感谢你愿意参与 AI Ops。这个项目还在快速演进，任何问题反馈、文档修正、演示数据补充、测试用例和功能贡献都很有价值。

## 开始之前

- 先阅读 [README.md](README.md)，确认项目定位、启动方式和主要模块。
- 如果是较大的功能改动，建议先提交 Issue 说明背景、目标和大致方案。
- 如果改动涉及权限、路由守卫、菜单、按钮或 WebSocket 访问，请先更新后端 RBAC enforcement，再同步前端展示。

## 本地开发

后端：

```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py seed_templates
python -m daphne -b 0.0.0.0 -p 8000 sxdevops.asgi:application
```

前端：

```bash
cd frontend
npm install
npm run dev
```

常用校验：

```bash
cd backend && python manage.py test
cd frontend && npm run build
```

## 代码风格

- Python 使用 4 空格缩进，模块、函数和 app-local helper 使用 snake_case。
- Vue view 和 layout 文件使用 PascalCase，例如 `K8sManage.vue`。
- API、store、utility 模块使用小写文件名，例如 `request.js` 和 `app.js`。
- 当前仓库没有统一 formatter 或 linter，提交前请匹配周边代码风格并移除未使用 import。
- 中文 UI、接口响应、日志和注释请保持 UTF-8 编码，避免提交乱码。

## 前端约定

管理台和控制台页面优先沿用现有飞书风格工作台节奏：

- 使用紧凑顶部 hero，主标题只放第一行。
- 适合时采用 `hero + stats cards + compact hint strip + tabs/content` 结构。
- 顶部指标复用 `release-stat-card` 视觉语言。
- 环境、集群、命名空间、域名等筛选器放在 tabs 或顶部控制附近的紧凑工具栏。
- 避免旧式 `page-header`、重复内部统计和过大的营销式区块。

## 提交 Pull Request

PR 描述建议包含：

- 改了什么。
- 为什么需要改。
- 如何验证。
- 是否涉及数据库迁移、权限变更、配置变更或外部服务。

提交前请尽量完成：

- 后端改动运行相关测试或说明未运行原因。
- 前端改动运行 `npm run build`。
- 涉及中文文案的改动做一次乱码检查。
- 涉及截图或 README 的改动确认 Markdown 链接可访问。

## 贡献许可

除非你在提交时明确说明，否则你提交给 AI Ops 的贡献将按照项目当前的 Apache License 2.0 授权。

## 不应提交的内容

- 生产密钥、真实 Token、Kubeconfig、SSH 私钥、客户数据和主机凭据。
- 本地 SQLite 数据库、运行日志、临时截图、构建产物和依赖目录。
- 一次性过程笔记、私有演示材料和不可复现的本地配置。
