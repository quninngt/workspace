# 服务管理门户 — 设计文档

## 一、设计目标

统一管理服务器上所有运行中的 Web 服务，提供：

1. **服务发现** — 自动检测各服务端口的存活状态
2. **一键启停** — 通过 API 启动/停止/重启服务进程
3. **统一入口** — 每个服务的公网隧道地址集中展示
4. **实时监控** — 前端每 8 秒自动刷新状态

## 二、架构概览

### 2.1 系统拓扑

```
┌──────────────┐
│   浏览器      │  HTTPS (Cloudflare)
└──────┬───────┘
       │
┌──────▼───────┐
│ Cloudflare   │  try.cloudflare.com
│ Tunnel       │
└──────┬───────┘
       │ localhost:5175
┌──────▼───────┐      ┌──────────────────┐
│ Vite Dev     │ ──── │ Vite Proxy       │
│ Server       │      │ /api → :8002     │
│ (port 5175)  │      └──────────────────┘
└──────────────┘
       │
┌──────▼───────┐
│ FastAPI       │  Service Portal Backend
│ (port 8002)  │
└──────┬───────┘
       │
┌──────┴───────────────────────────────────┐
│            Port Detection                │
│ ┌────────┐  ┌────────┐  ┌────────┐      │
│ │ :8000  │  │ :8001  │  │ :8002  │      │
│ │ cumbre │  │lottery │  │ portal │      │
│ │  bk    │  │  bk    │  │  bk    │      │
│ └────────┘  └────────┘  └────────┘      │
│ ┌────────┐  ┌────────┐  ┌────────┐      │
│ │ :5173  │  │ :5174  │  │ :5175  │      │
│ │ cumbre │  │lottery │  │ portal │      │
│ │  fe    │  │  fe    │  │  fe    │      │
│ └────────┘  └────────┘  └────────┘      │
└──────────────────────────────────────────┘
```

### 2.2 数据流

```
浏览器 ──GET /api/services──→ FastAPI
                                 │
                      asyncio.gather(
                        check_port(8000),
                        check_port(8001),
                        check_port(8002),
                        check_port(5173),
                        check_port(5174),
                        check_port(5175),
                      )
                                 │
                          asyncio.open_connection
                          (TCP 连接测试, 2s 超时)
                                 │
                          JSON 响应 ←────────
                                 │
浏览器 ←── 渲染卡片列表 ──────┘
```

## 三、核心设计决策

### 3.1 端口存活检测而非 HTTP 健康检查

**方案选择：**
- ❌ HTTP `/health` 轮询 — 需要每个服务都实现端点
- ✅ **TCP socket 连接测试** — 端口开放即认为存活

**理由：** 端口检测是通用方案，无需每个服务配合。单个 TCP SYN 包即可判断，开销极低。

**实现：**
```python
async def check_port(port: int) -> bool:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", port), timeout=2
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
        return False
```

**局限性：**
- 端口开放 ≠ 服务正常运行（可能僵死但端口未释放）
- 如需精确检测，需改为 HTTP 健康检查

### 3.2 服务启停实现

#### 停止流程

```python
def _kill_port(port: int):
    # 首选 fuser -k（Linux 专用，快）
    subprocess.run(["fuser", "-k", f"{port}/tcp"])
    # 备用 lsof + SIGKILL
    subprocess.run(["lsof", "-ti", f":{port}"])
    os.kill(pid, signal.SIGKILL)
```

**为什么用 SIGKILL 而非 SIGTERM：** 前端 dev server（Vite）和后端 dev server（uvicorn --reload）没有优雅关闭的必要，直接杀进程释放端口最可靠。

#### 启动流程

```python
# 后端（带 virtualenv 激活）
shell_cmd = f"cd {path} && source {venv}/bin/activate && nohup {cmd} > /tmp/{id}_backend.log 2>&1 &"
subprocess.Popen(["bash", "-c", shell_cmd], preexec_fn=os.setpgrp)

# 前端（无需 venv）
shell_cmd = f"cd {path} && nohup {cmd} > /tmp/{id}_frontend.log 2>&1 &"
```

**为什么用 Popen 而非 subprocess.run：** 需要非阻塞启动，Popen 立即返回，服务在后台继续运行。

### 3.3 Virtualenv 自动发现

```python
def get_venv_path(backend_path: str) -> str:
    for p in [".venv/bin/python3", "venv/bin/python3"]:
        if os.path.isfile(p):
            return os.path.dirname(os.path.dirname(p))
    return ""
```

支持 `.venv`（uv 默认）和 `venv`（传统）两种目录名。

### 3.4 三态状态模型

| 状态 | 条件 | 颜色 |
|------|------|------|
| running | 后端 ✅ + 前端 ✅ | 🟢 |
| partial | 后端或前端其一在线 | 🟡 |
| stopped | 两端均离线 | 🔴 |

## 四、服务定义

```python
SERVICES = [
    {
        "id": "beijing-lottery",          # 唯一标识符
        "name": "北京摇号模拟器",          # 显示名称
        "description": "...",              # 描述
        "category": "模拟器",              # 分类（决定图标）
        "web_url": "https://...",          # 公网链接
        "backend": {
            "port": 8001,                  # 检测端口
            "path": ".../backend",         # 工作目录
            "cmd": "uvicorn app.main:app --host 0.0.0.0 --port 8001"
        },
        "frontend": {
            "port": 5174,                  # 检测端口
            "path": ".../client",          # 工作目录
            "cmd": "npx vite --host 0.0.0.0 --port 5174"
        },
        "tunnel": "https://...",           # Cloudflare URL
    },
]
```

每添加一个新服务，只需在 `SERVICES` 数组中增加一项即可自动出现在 Portal 面板中。

## 五、前端设计

### 5.1 组件结构

```
App
 ├── Header (logo + 标题 + 刷新按钮)
 ├── Summary (🟢 运行中 / 🟡 部分 / 🔴 已停计数)
 ├── Toast (操作反馈消息)
 ├── Card[] (每个服务一张卡片)
 │    ├── Header (分类图标 + 服务名 + 状态指示灯)
 │    ├── Details (后端/前端状态 + 隧道链接)
 │    └── Actions (▶️启动 / ⏹️停止 / 🔄重启 / 🌐打开)
 └── Footer
```

### 5.2 状态刷新

- 首次加载：立即查询
- 轮询：每 8 秒自动刷新
- 操作后：1.5 秒后主动刷新（确保进程有足够时间启动/停止）
- 手动刷新：点击 🔄 按钮

### 5.3 响应式设计

- 桌面端：卡片网格布局
- 移动端（<640px）：紧凑卡片 + 小字号

### 5.4 Portal 自身保护

Portal 卡片不显示操作按钮，防止误操作关掉管理面板自身：
```tsx
{s.id !== 'portal' && (
  <div className="card-actions">
    ...
  </div>
)}
```

## 六、API 规范

### 6.1 端点列表

| 方法 | 路径 | 输入 | 输出 |
|------|------|------|------|
| GET | `/api/services` | — | `{services: [{id, name, status, backend, frontend, web_url, tunnel}]}` |
| GET | `/api/services/{id}` | — | 单个服务状态 |
| POST | `/api/services/{id}/start` | — | `{id, backend_started: bool, frontend_started: bool}` |
| POST | `/api/services/{id}/stop` | — | `{id, backend: bool, frontend: bool}` |
| POST | `/api/services/{id}/restart` | — | `{id, backend_started: bool, frontend_started: bool}` |
| GET | `/api/health` | — | `{status: "ok"}` |

### 6.2 错误处理

- 服务 ID 不存在 → 404
- 启动失败 → 返回 `false` 而非抛异常
- 停止失败（端口无人占用）→ 返回 `false`，无害

## 七、安全考虑

- CORS 允许所有来源 `*`（内网管理工具，无敏感数据）
- 所有操作通过 Cloudflare Tunnel 加密传输
- 未实现认证（纯内网工具，隧道 URL 随机生成）
- **⚠️ 不推荐暴露到公网** — TryCloudflare 隧道每次重启 URL 会变，限制了暴露时间

## 八、已知限制

1. **非阻塞启停** — start/stop 调用立即返回，不等待服务就绪
2. **端口检测粒度粗** — 只看端口是否开放，不检测服务健康度
3. **无持久化状态** — Portal 重启后不保存服务历史状态
4. **日志路径** — 各服务的 stdout/stderr 写入 `/tmp/{id}_backend.log` 和 `/tmp/{id}_frontend.log`
5. **隧道 URL 不持久** — Cloudflare TryCloudflare 每次重启分配新 URL，需手动更新 `services.py`
