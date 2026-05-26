# 📊 服务管理门户 (Service Portal)

统一管理服务器上所有运行中的 Web 服务。一键启停、状态监控、公网隧道直达。

**👉 https://mystery-beans-mumbai-included.trycloudflare.com**

## 功能

- **服务概览** — 所有服务的后端/前端运行状态一目了然
- **一键启停** — 点卡片的 ⏹️ 停止服务，▶️ 启动服务
- **快捷重启** — 🔄 重启服务（先停后启，间隔 1 秒）
- **公网直达** — 🌐 直接跳转到服务的公开页面
- **实时刷新** — 每 8 秒自动检测端口状态
- **三态指示** — 🟢 全运行 / 🟡 部分运行 / 🔴 已停止

## 快速启动

### 后端
```bash
cd /home/ubuntu/workspace/portal/backend
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

### 前端
```bash
cd /home/ubuntu/workspace/portal/client
npx vite --host 0.0.0.0 --port 5175
```

### 隧道
```bash
cloudflared tunnel --url http://localhost:5175
```

### 一键启动（完整流程）
```bash
# 1. 后端
cd /home/ubuntu/workspace/portal/backend && uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload &

# 2. 前端
cd /home/ubuntu/workspace/portal/client && npx vite --host 0.0.0.0 --port 5175 &

# 3. 等待 4 秒后开隧道
sleep 4 && cloudflared tunnel --url http://localhost:5175
```

## 架构

```
浏览器 ──HTTPS──→ Cloudflare Tunnel ──→ Vite (5175) ──proxy──→ FastAPI (8002)
                                        /api/*                        │
                                                             ┌───────┼───────┐
                                                             ▼       ▼       ▼
                                                        TCP 检测 :8000 :8001 :8002
                                                             │       │       │
                                                        cumbre  lottery  portal
                                                         bk      bk      bk
                                                        :5173   :5174   :5175
                                                        cumbre  lottery  portal
                                                         fe      fe      fe
```

前端通过 Vite 代理 `/api` 请求到后端 8002。后端通过 TCP socket 连接测试检测每个服务的端口存活状态。

## 工程结构

```
portal/
├── backend/
│   └── app/
│       ├── main.py           # FastAPI 入口（25行）
│       │                     # app 创建 + CORS 配置 + 路由挂载
│       ├── router.py         # API 端点（61行）
│       │                     # 6 个端点：list / detail / start / stop / restart / health
│       └── services.py       # 服务引擎（160行）
│                             # 服务定义 + 端口检测 + 启停管理
├── client/
│   └── src/
│       ├── App.tsx           # 主组件（~230行）
│       │                     # 仪表盘：状态摘要 + 服务卡片 + 响应式
│       ├── main.tsx          # React DOM 入口
│       └── index.css         # 暗色主题样式（~200行）
│                             # CSS only，无 UI 框架依赖
├── DESIGN.md                 # 详细设计文档
└── README.md                 # 本文件
```

## 关键文件说明

| 文件 | 行数 | 职责 |
|------|------|------|
| `services.py` | 160 | SERVICE 数组（服务注册表）、check_port async 检测、_kill_port 双策略杀进程、start/stop/restart |
| `router.py` | 61 | asyncio.gather 并行检测、404 处理 |
| `main.py` | 25 | FastAPI app 对象、CORSMiddleware（allow all） |
| `App.tsx` | ~230 | useState/useEffect/useCallback 状态管理、8 秒轮询、卡片渲染 |
| `index.css` | ~200 | 暗色主题、响应式断点 640px |

## 管理的服务

| 服务 | 后端 | 前端 | 隧道 URL |
|------|------|------|----------|
| 🚗 北京摇号模拟器 | :8001 | :5174 | introducing-colors-findings-polo.trycloudflare.com |
| 💰 Cumbre 基金智投 | :8000 | :5173 | silly-detective-over-adjustment.trycloudflare.com |
| ⚙️ 服务管理门户 | :8002 | :5175 | mystery-beans-mumbai-included.trycloudflare.com |

### 添加新服务

在 `services.py` 的 `SERVICES` 数组中新增一项即可自动出现在 Portal 面板：

```python
{
    "id": "my-new-app",                     # URL 标识
    "name": "我的新应用",                    # 显示名称
    "description": "新应用的功能描述",       # 卡片显示
    "category": "工具",                     # 决定图标
    "web_url": "https://xxx.trycloudflare.com",
    "backend": {"port": 8003, "path": "...", "cmd": "uvicorn ..."},
    "frontend": {"port": 5176, "path": "...", "cmd": "npx vite ..."},
    "tunnel": "https://xxx.trycloudflare.com",
}
```

## API 端点

| 方法 | 路径 | 输入 | 输出 | 说明 |
|------|------|------|------|------|
| GET | `/api/services` | — | `{services: [...]}` | 所有服务状态（并行检测） |
| GET | `/api/services/{id}` | — | 单服务详情 | 404 if not found |
| POST | `/api/services/{id}/start` | — | `{backend_started, frontend_started}` | 非阻塞启动 |
| POST | `/api/services/{id}/stop` | — | `{backend, frontend}` | SIGKILL 杀端口 |
| POST | `/api/services/{id}/restart` | — | `{backend_started, frontend_started}` | 停→1秒→启 |
| GET | `/api/health` | — | `{status: "ok"}` | 健康检查 |

## 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 后端 | Python / FastAPI / uvicorn | 3.10+ / 0.133 / 0.41 |
| 前端 | React / TypeScript / Vite | 18 / 5.6 / 6.0 |
| 样式 | 纯 CSS（暗色主题） | — |
| 图表 | 无（纯列表） | — |
| 隧道 | Cloudflare Tunnel | TryCloudflare 免费版 |
| 端口检测 | asyncio.open_connection | TCP SYN + 2s 超时 |
| 进程管理 | subprocess.Popen + fuser/lsof | SIGKILL |

## 日志

各服务的 stdout/stderr 写入 `/tmp` 目录：

```
/tmp/{service_id}_backend.log
/tmp/{service_id}_frontend.log
```

例如：北京摇号后端的日志在 `/tmp/beijing-lottery_backend.log`

## 设计文档

详见 [DESIGN.md](./DESIGN.md)，涵盖：
- 架构设计与拓扑图
- 核心设计决策（端口检测、启停实现、三态模型）
- 安全考虑与已知限制
