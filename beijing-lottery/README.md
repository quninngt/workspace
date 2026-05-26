# 🚗 北京摇号模拟器

模拟北京小客车燃油车指标个人摇号。一年两期、阶梯基数递增、真实概率计算。

**👉 在线体验：** https://introducing-colors-findings-polo.trycloudflare.com

## 功能

- **🔮 摇一期** — 模拟半年一次的开奖（6月或12月）
- **⏩ 快进 N 年** — 一次跑多年（支持 1/3/5/10 年快捷按钮和自定义输入）
- **📈 概率曲线** — 面积图展示概率随等待时间的增长趋势
- **📋 摇号记录** — 查看每次摇号的期次、时间、基数、概率
- **🔄 重置重来** — 清空记录重新开始

## 快速启动

### 后端

```bash
cd /home/ubuntu/workspace/beijing-lottery/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 前端

```bash
cd /home/ubuntu/workspace/beijing-lottery/client
npx vite --host 0.0.0.0 --port 5174
```

### 隧道

```bash
cloudflared tunnel --url http://localhost:5174
```

## 工程结构

```
beijing-lottery/
├── backend/
│   └── app/
│       ├── main.py          # FastAPI 入口 + CORS 配置
│       ├── router.py        # 7 个 API 端点
│       └── simulator.py     # 摇号引擎（核心逻辑）
├── client/
│   └── src/
│       ├── App.tsx          # 主组件（~300 行，全量 UI）
│       ├── main.tsx         # React DOM 入口
│       └── index.css        # 样式（响应式+深色主题）
├── DESIGN.md                # 详细设计文档
└── README.md                # 本文件
```

### 关键文件说明

| 文件 | 行数 | 职责 |
|------|------|------|
| `simulator.py` | ~150 | 摇号引擎：LotteryProfile 类、阶梯基数计算、概率公式、中签判定 |
| `router.py` | ~60 | 6 个 API 端点，串联引擎到 HTTP |
| `App.tsx` | ~300 | 前端仪表盘：状态面板、摇号按钮、快进控制、概率图表、记录表格 |
| `main.py` | ~25 | FastAPI app 对象、CORS 中间件 |

## 模拟参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 池子规模 | 260 万人 | 2024-2025 年北京燃油车个人申请者约数 |
| 每期配额 | 19,000 个指标 | 一年两期合计约 38,000 |
| 摇号频率 | 每年 2 期 | 6 月和 12 月 |
| 阶梯间隔 | 每 2 期 +1 | 2 次不中基数增加 1 |
| 初始概率 | ~0.104% | 基数=1 时的本期中签概率 |

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.10+ / FastAPI / uvicorn |
| 前端 | React 18 / TypeScript / Vite 6 |
| 图表 | Recharts (AreaChart 面积图) |
| 隧道 | Cloudflare Tunnel (TryCloudflare) |
| 包管理 | npm (frontend) / uv (backend) |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/lottery/profile` | 获取当前档案 |
| POST | `/api/lottery/draw` | 摇一期 |
| POST | `/api/lottery/draw-batch?years=N` | 快进 N 年 |
| POST | `/api/lottery/reset` | 重置 |
| GET | `/api/lottery/stats` | 统计数据 |
| GET | `/api/lottery/records` | 摇号记录 |
| GET | `/api/lottery/probability-trend` | 概率趋势 |

## 设计文档

详见 [DESIGN.md](./DESIGN.md)，涵盖：
- 核心规则与参数推导
- 概率计算公式
- 数据结构
- 技术决策及理由
- 已知限制
