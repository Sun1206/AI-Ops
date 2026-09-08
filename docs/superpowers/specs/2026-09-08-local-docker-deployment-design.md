# SxDevOps 本机 Docker 部署设计

## 目标

在当前 Windows 主机上使用仓库已有的 Docker Compose 配置启动 SxDevOps，并通过 `http://localhost:8000` 提供可登录、可浏览的本机演示环境。

## 方案

- 使用 `docker-compose.yml` 编排 `sxdevops`、MySQL 8 和 Redis 7 三个服务。
- 应用镜像采用现有多阶段 `Dockerfile`：Node 20 构建 Vue 3 前端，Python 3.12 安装 Django 后端依赖，Daphne 在 8000 端口同时提供 HTTP 与 WebSocket 服务。
- 使用随机生成的 `SECRET_KEY`，只注入当前 Compose 进程，不写入仓库。
- 使用命名卷 `mysql_data` 和 `redis_data` 保存本机演示数据；本次不清理已有卷。
- 入口脚本等待 MySQL 后自动执行数据库迁移、演示数据初始化和模板初始化。

## 兼容性品牌替换

- 将网页标题、导航品牌、登录页、终端欢迎语、面向用户的接口说明、演示内容以及产品文档中的 `SxDevOps` 或自然语言语境中的 `sxdevops` 替换为 `AI Ops`。
- 保留 Django 包名和导入路径 `sxdevops`、`DJANGO_SETTINGS_MODULE`、Daphne 启动目标、`SXDEVOPS_*` 环境变量、Compose 服务/镜像/容器/数据库标识、缓存与浏览器存储键、浏览器事件名、MCP 工具名、HTTP 兼容请求头、Kubernetes/Docker 标签、临时目录前缀及测试夹具中的协议值。
- 保留现有文件名和 `sxdevops.top` 外部链接，避免静态路径和线上地址失效；链接的展示名称可以改为 `AI Ops`。
- 不迁移已有浏览器本地状态、数据库、容器卷或外部集成标识。

## 启动与数据流

1. 启动 Docker Desktop/Engine。
2. 校验 Compose 配置并确认 8000 端口可用。
3. 构建前后端一体镜像并后台启动三个服务。
4. 浏览器请求进入 Daphne；`/api/` 由 Django REST Framework 处理，前端静态资源由 Django 从镜像内的 `frontend/dist` 提供。
5. Django 使用 Compose 内网连接 MySQL 和 Redis，Channels 使用 Redis 的独立逻辑库。

## 错误处理

- Docker Engine 无法启动时，检查 Docker Desktop 进程和 daemon 状态后重试。
- 镜像构建失败时，定位失败阶段（npm、pip 或复制/构建步骤），仅针对根因做最小修改。
- 数据库初始化失败时，检查 MySQL 健康状态、入口脚本输出和迁移日志。
- 应用启动后若页面或 API 不可用，检查容器状态、应用日志和 HTTP 响应；不通过删除数据卷来规避问题。

## 验证标准

- 源码中剩余的 `sxdevops` 均属于上述兼容性保留项，用户主要界面不再显示旧品牌名。
- Django 配置检查和后端测试通过，Vue 生产构建通过。
- `docker compose ps` 显示应用运行，MySQL 和 Redis 健康。
- `http://localhost:8000` 返回成功响应并包含前端页面。
- 登录 API 可用，演示账号能够登录。
- 应用日志没有持续崩溃、迁移失败或数据库/Redis 连接错误。

## 非目标

本次不配置公网域名、TLS、反向代理、生产密码体系、外部可观测性数据源或云/Kubernetes 凭据，也不修改业务功能。
