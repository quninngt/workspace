# Cumbre — 基金智投跟投平台 需求文档 v2.0

> 更新时间: 2026-05-15
> 状态: 功能开发完成，待调优

---

## 1. 产品概述

### 1.1 产品定位

Cumbre 是一个面向中国公募基金市场的智能投资跟投平台。系统通过多因子信号引擎对全市场基金进行每日评分，生成买入/持有/卖出信号，并通过自动跟投和手动跟投两种模式帮助用户执行投资策略。

### 1.2 核心目标

- 覆盖中国公募基金全市场（当前收录 26,710 只基金）
- 多因子量化模型驱动信号生成（估值、趋势、动量、质量、情绪）
- 双模式执行：自动跟投（模型验证）+ 手动跟投（用户自主决策）
- 完整的投资组合管理和收益追踪

### 1.3 目标用户

- 个人基金投资者，希望通过量化信号辅助投资决策
- 对自动定投策略感兴趣的验证性投资者
- 偏好自主决策但仍需信号参考的半主动投资者

---

## 2. 系统架构

### 2.1 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Python FastAPI + Uvicorn |
| 前端框架 | React 19 + TypeScript + Vite 6 |
| UI 组件 | TailwindCSS 3 + lucide-react 图标 |
| 图表库 | Recharts 2 (LineChart, PieChart, AreaChart) |
| 数据库 | SQLite (开发) / MySQL (生产) |
| ORM | SQLAlchemy 2.0 Async (aiosqlite) |
| 认证 | JWT (python-jose + bcrypt) |
| 数据采集 | httpx (异步 HTTP) |
| 定时任务 | APScheduler |
| 数据源 | 天天基金 (eastmoney.com) 公开 API |

### 2.2 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    数据采集层 (Data Collector)               │
│  天天基金 API → 基金列表 / 净值 / 持仓 / 经理信息            │
│  腾讯行情 API → 指数估值 (PE/PB/百分位)                     │
└───────────────────────┬─────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    信号引擎 (Signal Engine)                  │
│  估值因子(15%) + 趋势因子(10%) + 动量因子(30%)              │
│  + 质量因子(30%) + 情绪因子(15%) → 评分(S/A/B/C/D)         │
└───────────────────────┬─────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                       执行清单                               │
│              从信号生成 → 用户审查/编辑 → 提交执行           │
└───────┬─────────────────────────────────┬───────────────────┘
        │                                 │
        ▼                                 ▼
┌──────────────────┐          ┌──────────────────────────┐
│   自动跟投模式     │          │     手动跟投模式           │
│ 自动分配+执行     │          │ 用户增删改+确认提交         │
│ 不可编辑          │          │ 完全自主控制               │
│ 模型验证工具      │          │ 实际投资决策               │
└──────────────────┘          └──────────────────────────┘
        │                                 │
        ▼                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                      投资组合追踪                             │
│  持仓管理 / 交易记录 / 资产配置比例 / 收益报告                │
│  历史回测 (信号策略表现评估)                                 │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 目录结构

```
cumbre/
├── PRD-v1.md                    # 产品需求文档 v1
├── PRD-v2.md                    # 产品需求文档 v2 (本文件)
├── TODO.md                      # 待执行清单
├── CLAUDE.md                    # 项目指引
├── package.json                 # Monorepo 根
├── backend/
│   ├── .env                     # 环境变量
│   ├── requirements.txt         # Python 依赖
│   ├── cumbre.db                # SQLite 数据库
│   ├── populate_demo.py         # 批量数据填充脚本
│   ├── data/                    # 数据文件 (回测结果等)
│   └── app/
│       ├── main.py              # 入口 + lifespan + CORS
│       ├── config.py            # Pydantic Settings
│       ├── database.py          # 异步引擎 + Session
│       ├── models/              # 18 个 ORM 模型
│       │   ├── user.py
│       │   ├── fund.py          # Fund, FundNav, FundHolding, FundValuation, FundManager
│       │   ├── signal.py        # Signal
│       │   ├── auto.py          # AutoConfig, AutoPortfolio, AutoPosition, AutoTrade, AutoReport
│       │   ├── manual.py        # ExecutionItem, ManualPortfolio, ManualPosition, ManualTrade
│       │   └── watchlist.py     # Watchlist
│       ├── schemas/             # Pydantic v2 请求/响应模型
│       ├── routers/             # 10 个路由模块
│       │   ├── auth.py          # 注册/登录/获取用户/修改密码
│       │   ├── funds.py         # 基金列表/详情/净值/持仓/估值/信号
│       │   ├── signals.py       # 信号列表/分布
│       │   ├── market.py        # 市场总览
│       │   ├── execution_list.py # 执行清单 CRUD + 从信号生成
│       │   ├── auto.py          # 自动跟投配置/组合/报告
│       │   ├── manual.py        # 手动组合/提交执行
│       │   ├── watchlist.py     # 自选管理
│       │   └── admin.py         # 数据同步/信号生成/自动执行/回测
│       └── services/
│           ├── auth.py          # bcrypt + JWT
│           ├── dependencies.py  # get_current_user
│           ├── scheduler.py     # APScheduler 定时任务
│           ├── data_collector/  # 天天基金数据采集
│           │   ├── collector.py # 编排器
│           │   ├── fund_list.py # 基金列表 API
│           │   ├── fund_nav.py  # 净值 API
│           │   ├── fund_holdings.py # 持仓 API
│           │   └── index_quota.py   # 指数估值 API
│           ├── signal_engine/   # 信号引擎
│           │   ├── engine.py    # 编排器
│           │   ├── scorer.py    # 加权评分
│           │   └── factors/     # 5 因子
│           │       ├── valuation.py
│           │       ├── trend.py
│           │       ├── momentum.py
│           │       ├── quality.py
│           │       └── sentiment.py
│           ├── auto_executor.py     # 自动执行引擎
│           ├── manual_executor.py   # 手动提交流程
│           └── backtesting/         # 历史回测
│               └── backtester.py
└── client/
    ├── package.json
    ├── vite.config.ts           # 代理 /api → localhost:8000
    ├── tailwind.config.js       # 自定义 primary 色板
    └── src/
        ├── main.tsx             # 入口 + BrowserRouter + AuthProvider
        ├── App.tsx              # 路由定义
        ├── api/client.ts        # Axios 实例 + 类型化 API 方法
        ├── context/AuthContext.tsx # 认证上下文
        ├── components/
        │   ├── Layout.tsx       # 侧边栏 + Outlet
        │   └── Sidebar.tsx      # 导航项
        └── pages/
            ├── Login.tsx / Register.tsx
            ├── Dashboard.tsx      # 市场总览
            ├── FundList.tsx       # 基金列表
            ├── FundDetail.tsx     # 基金详情
            ├── AutoFollow.tsx     # 自动跟投
            ├── ManualFollow.tsx   # 执行清单
            ├── ManualPortfolio.tsx # 手动组合
            ├── Watchlist.tsx      # 自选管理
            ├── Settings.tsx       # 设置
            └── Backtest.tsx       # 历史回测
```

---

## 3. 功能需求

### 3.1 用户认证 (Auth)

#### 3.1.1 注册
- **接口**: `POST /api/auth/register`
- **输入**: name, email, password
- **输出**: JWT token + user 信息
- **规则**: 
  - email 唯一性校验
  - 密码至少 6 位
  - 密码用 bcrypt 哈希存储

#### 3.1.2 登录
- **接口**: `POST /api/auth/login`
- **输入**: email, password
- **输出**: JWT token + user 信息
- **规则**:
  - 验证邮箱是否存在
  - 验证密码哈希
  - 返回 JWT token（Bearer 格式）

#### 3.1.3 获取当前用户
- **接口**: `GET /api/auth/me`
- **认证**: Bearer token
- **输出**: user 信息 (id, name, email)

#### 3.1.4 修改密码
- **接口**: `POST /api/auth/change-password`
- **认证**: Bearer token
- **输入**: current_password, new_password
- **规则**:
  - 验证当前密码正确性
  - 新密码至少 6 位
  - 重新哈希存储

### 3.2 基金数据 (Funds)

#### 3.2.1 基金列表
- **接口**: `GET /api/funds`
- **参数**: type(筛选类型), codes(批量查名), skip, limit
- **输出**: 基金列表 (code, name, type, company, fund_size, risk_level)
- **基金类型**: stock(股票型), mixed(混合型), bond(债券型), index(指数型), money_market(货币型), qdii(QDII), fof(FOF), other(其他)

#### 3.2.2 基金详情
- **接口**: `GET /api/funds/{code}`
- **输出**: 单只基金完整信息

#### 3.2.3 净值历史
- **接口**: `GET /api/funds/{code}/nav`
- **参数**: limit
- **输出**: NAV 记录列表 (date, nav, acc_nav)

#### 3.2.4 持仓数据
- **接口**: `GET /api/funds/{code}/holdings`
- **输出**: 股票持仓列表 (stock_code, stock_name, ratio, date)

#### 3.2.5 估值数据
- **接口**: `GET /api/funds/{code}/valuations`
- **参数**: limit
- **输出**: PE/PB 百分位历史

#### 3.2.6 基金信号历史
- **接口**: `GET /api/funds/{code}/signals`
- **参数**: limit
- **输出**: 信号历史列表 (score, level, action, date, factors_detail)

### 3.3 信号引擎 (Signals)

#### 3.3.1 信号列表
- **接口**: `GET /api/signals`
- **参数**: level(S/A/B/C/D), action(buy/hold/sell), limit
- **输出**: 信号列表含基金名称

#### 3.3.2 信号分布
- **接口**: `GET /api/signals/distribution`
- **输出**: 各等级信号数量统计 + 最新信号日期

#### 3.3.3 评分模型

五因子加权评分模型：

| 因子 | 权重 | 计算方法 |
|------|------|----------|
| 估值 (Valuation) | 15% | NAV 52 周范围代理 + 短期反转（指数基金可用 PE/PB 百分位） |
| 趋势 (Trend) | 10% | MA20/MA60 均线交叉 + 价格偏离度（当前市场环境下权重最小化） |
| 动量 (Momentum) | 30% | RSI(14) + MACD(12,26,9)，区分度最大 |
| 质量 (Quality) | 30% | 基金规模 + 最大回撤 + NAV 收益一致性 |
| 情绪 (Sentiment) | 15% | 基金自身波动率逆向指标（非市场情绪） |

**信号等级**:

| 等级 | 分数范围 | 操作 |
|------|----------|------|
| S (强买入) | ≥ 80 | 2 倍权重买入 |
| A (买入) | 65-79 | 1 倍权重买入 |
| B (持有) | 40-64 | 持有不动 |
| C (卖出) | 25-39 | 卖出 25% 持仓 |
| D (强卖出) | < 25 | 卖出 50% 持仓 |

#### 3.3.4 信号生成流程
1. 每日 20:30（北京时间）定时触发
2. 加载所有有净值数据的基金（当前 192 只）
3. 对每只基金加载至少 60 个交易日的净值数据
4. 依次计算 5 个因子得分
5. 加权计算总分，映射到 S/A/B/C/D 等级
6. 存储信号记录到数据库

### 3.4 市场总览 (Dashboard)

#### 3.4.1 市场概览
- **接口**: `GET /api/market/overview`
- **输出**: 
  - 指数列表 (名称, PE, PB, 百分位)
  - 信号分布统计
  - 基金总数
  - 最新信号日期

#### 3.4.2 页面功能
- 指数 PE/PB 百分位彩色矩阵展示
- 统计卡片：收录基金数、今日信号数、待执行数、自动组合市值
- 信号分布饼图 (Recharts PieChart)
- 快捷入口链接

### 3.5 执行清单 (Execution List)

#### 3.5.1 列表
- **接口**: `GET /api/execution-list`
- **参数**: status(pending/executed/skipped)
- **输出**: 执行项目列表 (fund_code, action, suggested_amount, status, date)

#### 3.5.2 创建
- **接口**: `POST /api/execution-list`
- **输入**: fund_code, action(buy/sell/hold), suggested_amount_min/max
- **自动字段**: plan_type="daily", date=today, status="pending"

#### 3.5.3 更新
- **接口**: `PUT /api/execution-list/{id}`
- **可更新字段**: action, suggested_amount, status

#### 3.5.4 删除
- **接口**: `DELETE /api/execution-list/{id}`

#### 3.5.5 从信号生成
- **接口**: `POST /api/execution-list/generate-from-signals`
- **参数**: action(buy/hold/sell 筛选)
- **逻辑**: 将今日的买入(及可选筛选)信号转换为执行清单项目
- **规则**: 自动跳过已存在的同基金待执行项目

#### 3.5.6 前端功能
- 表格展示所有执行项目
- 基金代码 + 基金名称并排显示
- 操作标签：买入(绿)/卖出(红)/持有(灰)
- 状态标签：待执行(黄)/已执行(绿)/已跳过(灰)
- 操作按钮：标记为已执行、跳过、删除
- "从信号生成"按钮：一键导入今日信号
- "提交执行"按钮：推送到手动组合
- 添加弹窗：基金代码、操作类型、建议金额范围

### 3.6 自动跟投 (Auto Follow)

#### 3.6.1 投资配置
- **接口**: `GET/POST /api/auto/config`
- **配置项**: total_amount (每交易日投资金额), status
- **前端**: 输入金额 + 启动/更新按钮 + 运行中状态标签

#### 3.6.2 执行逻辑
- 每个交易日自动执行：
  1. 将 `total_amount` 添加到组合现金
  2. 处理卖出信号（C 级卖 25%，D 级卖 50%）
  3. 处理买入信号（S 级 2 倍权重，A 级 1 倍权重分配现金）
  4. 单只基金上限：组合总值的 30%
  5. 更新组合市值、现金、净值历史

#### 3.6.3 组合概览
- **接口**: `GET /api/auto/portfolio`
- **输出**: 组合信息 + 持仓列表 + 交易记录
- **前端展示**:
  - 统计卡片：总投入、当前市值、可用现金
  - 持仓明细表：基金名称、份额、成本净值、占比
  - 资产配置饼图
  - 交易记录表

#### 3.6.4 收益报告
- **接口**: `GET /api/auto/reports`
- **参数**: period_type
- **输出**: 历史收益报告列表

### 3.7 手动组合 (Manual Portfolio)

#### 3.7.1 组合列表
- **接口**: `GET /api/manual/portfolios`
- **输出**: 组合列表含持仓和交易记录

#### 3.7.2 组合详情
- **接口**: `GET /api/manual/portfolios/{id}`

#### 3.7.3 提交执行
- **接口**: `POST /api/manual/submit-execution`
- **逻辑**:
  1. 查询用户所有 pending 的执行项目
  2. 查找或创建手动组合
  3. 对每个买入项创建交易记录，更新持仓（加权平均成本）
  4. 对每个卖出项创建交易记录，减少持仓份额
  5. Hold 项标记为跳过
  6. 更新组合总投资额

#### 3.7.4 前端功能
- 可展开/收起的组合卡片
- 组合名称、总投资、现金余额概览
- 持仓明细表
- 交易记录表

### 3.8 自选管理 (Watchlist)

#### 3.8.1 列表
- **接口**: `GET /api/watchlist`
- **参数**: group_name

#### 3.8.2 添加
- **接口**: `POST /api/watchlist`
- **参数**: fund_code, group_name

#### 3.8.3 删除
- **接口**: `DELETE /api/watchlist/{id}`

#### 3.8.4 前端功能
- 分组展示自选基金
- 基金详情页星标收藏功能
- 一键取消收藏

### 3.9 用户设置 (Settings)

#### 3.9.1 功能
- 用户信息展示 (名称、邮箱、用户 ID)
- 修改密码表单：当前密码 + 新密码 + 确认密码
- 表单验证（非空、密码匹配、最小长度）
- 成功/错误消息提示

### 3.10 历史回测 (Backtesting)

#### 3.10.1 回测触发
- **接口**: `POST /api/admin/backtest`
- **参数**: start_date, end_date
- **类型**: 后台异步执行

#### 3.10.2 结果查询
- **接口**: `GET /api/admin/backtest/result`
- **输出**: 回测结果 JSON

#### 3.10.3 回测逻辑
1. 遍历日期范围内所有交易日
2. 每日对所有有净值数据的基金运行信号引擎
3. 模拟交易策略（S/A 买入，C/D 卖出）
4. 追踪组合每日价值

#### 3.10.4 回测指标
- 区间总收益率
- 基准收益率（沪深 300 对比）
- 最大回撤
- 月度收益率
- 信号等级分布
- 因子贡献度分析

#### 3.10.5 前端功能
- 日期范围选择器
- 运行回测按钮 + 进度加载
- 结果展示：收益卡片、信号分布条形图、因子贡献条形图、月度收益网格
- 每日详情可折叠表格

### 3.11 数据采集 (Data Collection)

#### 3.11.1 定时任务
| 任务 | 时间 | 内容 |
|------|------|------|
| 日度采集 | 每日 20:30 北京时间 | 增量净值同步 + 指数估值 + 信号生成 + 自动执行 |
| 周度全量同步 | 每周日 21:00 北京时间 | 全量基金列表 + 所有基金净值 + 信号生成 |

#### 3.11.2 手动触发 (Admin)
- `POST /api/admin/sync/funds` — 同步基金列表
- `POST /api/admin/sync/nav` — 同步净值数据
- `POST /api/admin/signals/generate` — 运行信号引擎
- `POST /api/admin/auto/execute` — 运行自动执行

#### 3.11.3 数据源
| 数据 | 来源 | 接口说明 |
|------|------|----------|
| 基金列表 | 天天基金 JS API | 全市场基金基本信息，含类型分类 |
| 净值历史 | 天天基金 NAV API | 分页获取，每页 20 条 |
| 股票持仓 | 天天基金 HTML | JS 内容解析 + 正则提取 |
| 指数估值 | 腾讯行情 qt.gtimg.cn | 8 大主要指数 PE/PB + 历史百分位 |

---

## 4. 数据模型

### 4.1 核心业务表

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| users | 用户 | id, name, email, password_hash |
| funds | 基金 | code(PK), name, type, company, fund_size |
| fund_navs | 基金净值 | fund_code, date, nav, acc_nav |
| fund_valuations | 基金估值 | fund_code, date, pe, pb, pe_percentile, pb_percentile |
| fund_holdings | 基金持仓 | fund_code, stock_code, stock_name, ratio, date |
| fund_managers | 基金经理 | id, name, description, tenure, fund_codes |
| index_quotas | 指数估值 | index_code, name, pe, pb, pe_percentile, pb_percentile |
| signals | 信号 | fund_code, date, score, level, action, factors_detail(JSON) |
| execution_items | 执行清单 | user_id, fund_code, action, suggested_amount, status, date |
| auto_configs | 自动配置 | user_id, total_amount, status |
| auto_portfolios | 自动组合 | user_id, cash, total_invested, market_value, nav_history(JSON) |
| auto_positions | 自动持仓 | portfolio_id, fund_code, shares, cost_nav, allocation_ratio |
| auto_trades | 自动交易 | portfolio_id, fund_code, type, amount, shares, nav, date |
| auto_reports | 自动报告 | user_id, period_type, period_start, period_end, stats(JSON) |
| manual_portfolios | 手动组合 | user_id, name, cash, total_invested |
| manual_positions | 手动持仓 | portfolio_id, fund_code, shares, cost_nav |
| manual_trades | 手动交易 | portfolio_id, fund_code, type, amount, shares, nav, date |
| watchlists | 自选 | user_id, fund_code, group_name |

---

## 5. 非功能需求

### 5.1 性能
- API 响应时间 < 500ms（数据采集类后台任务除外）
- NAV 数据加载：单只基金 100 条记录 < 200ms
- 信号生成：192 只基金 < 60 秒

### 5.2 安全
- 密码 bcrypt 哈希存储
- JWT token 认证
- 所有 API 必须鉴权（除注册/登录）
- 用户数据隔离（只能访问自己的数据）

### 5.3 可用性
- 前端在 Vite 开发模式下热更新
- 后端自动重载
- APScheduler 定时任务自动启动
- 数据库自动建表（首次启动）

---

## 6. 已知问题 (Known Issues)

### 6.1 信号分布偏窄
- **描述**: 个体基金 PE/PB 数据不可用，估值因子使用沪深 300 PE 替代，导致 94.6% 的评分集中在 B（持有）
- **影响**: 买/卖信号稀疏，自动/手动执行交易机会少
- **优先级**: P1

### 6.2 NAV 同步范围有限
- **描述**: 当前仅 192/26,710 只基金有净值数据，覆盖率 0.7%
- **影响**: 信号引擎只对 192 只基金生成信号
- **优先级**: P1

### 6.3 持仓数据稀疏
- **描述**: 仅 ~50 条持仓记录覆盖 5 只基金
- **影响**: 基金详情页持仓展示数据不足
- **优先级**: P1

### 6.4 基金详情字段缺失
- **描述**: company, risk_level, manager_id, established_date 多为 NULL
- **影响**: 基金详情页信息不完整
- **优先级**: P1

### 6.5 前端可视化缺失
- 信号因子雷达图/柱状图 (P3)
- PE/PB 估值走势图 (P3)

### 6.6 工程优化
- Token 过期自动刷新 (P3)
- 响应式布局适配移动端 (P3)
- 网络请求错误统一提示 (P3)
- 密码找回机制缺失

---

## 7. API 端点完整清单

### 7.1 公开端点 (无需认证)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/register | 注册 |
| POST | /api/auth/login | 登录 |

### 7.2 认证端点 (需 Bearer Token)

#### 用户
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/auth/me | 获取当前用户 |
| POST | /api/auth/change-password | 修改密码 |

#### 基金
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/funds | 基金列表 (支持 codes 批量查询) |
| GET | /api/funds/{code} | 基金详情 |
| GET | /api/funds/{code}/nav | 净值历史 |
| GET | /api/funds/{code}/holdings | 股票持仓 |
| GET | /api/funds/{code}/valuations | PE/PB 估值 |
| GET | /api/funds/{code}/signals | 信号历史 |

#### 信号
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/signals | 信号列表 |
| GET | /api/signals/distribution | 信号分布统计 |

#### 市场
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/market/overview | 市场总览 |

#### 执行清单
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/execution-list | 列表 (按 status 筛选) |
| POST | /api/execution-list | 创建 |
| PUT | /api/execution-list/{id} | 更新 |
| DELETE | /api/execution-list/{id} | 删除 |
| POST | /api/execution-list/generate-from-signals | 从信号生成 |

#### 自动跟投
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/auto/config | 获取配置 |
| POST | /api/auto/config | 保存配置 |
| GET | /api/auto/portfolio | 组合详情 |
| GET | /api/auto/reports | 收益报告 |

#### 手动跟投
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/manual/portfolios | 组合列表 |
| GET | /api/manual/portfolios/{id} | 组合详情 |
| POST | /api/manual/submit-execution | 提交执行 |

#### 自选
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/watchlist | 列表 |
| POST | /api/watchlist | 添加 |
| DELETE | /api/watchlist/{id} | 删除 |

#### 管理后台
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/admin/sync/funds | 同步基金列表 |
| POST | /api/admin/sync/nav | 同步净值 |
| POST | /api/admin/signals/generate | 生成信号 |
| POST | /api/admin/auto/execute | 触发自动执行 |
| POST | /api/admin/backtest | 运行回测 |
| GET | /api/admin/backtest/result | 获取回测结果 |

---

## 8. 数据库当前状态

| 指标 | 数值 |
|------|------|
| 收录基金总数 | 26,710 |
| 有净值数据的基金 | 192 |
| 净值记录总数 | 68,981 |
| 信号总数 | 184 |
| 信号分布 | A: 10, B: 174 |
| 指数估值 | 8 个 |
| 持仓数据 | ~50 条 / 5 只基金 |
| 用户数 | 3 |
| 自动配置数 | 1 |
| 自动组合数 | 1 |
| 自动持仓数 | 10 |
| 自动交易记录 | 10 |
| 执行清单项目 | 10 (已执行) |
| 基金经理记录 | 0 |
