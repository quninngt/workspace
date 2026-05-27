# Cumbre — 待优化清单

> 更新时间: 2026-05-27
>
> 图例: ✅ 已完成 | 🔄 进行中 | ⬜ 待开始
>
> 共 8 大类 47 项优化，按优先级排列

---

## P0 — 安全与数据完整性（必须修复）

| # | 分类 | 任务 | 状态 | 涉及文件 | 说明 |
|---|------|------|------|----------|------|
| 1 | 安全 | **admin 端点无权限校验** | ✅ | `routers/admin.py` | 添加 `get_admin_user` 依赖，所有 admin 端点限制为管理员 |
| 2 | 安全 | **tools 端点无权限校验** | ✅ | `routers/tools.py` | `reset_signals` 改用 `get_admin_user`，SQL 注入模式修复 |
| 3 | 安全 | **JWT secret 硬编码默认值** | ✅ | `config.py` | 启动时检测默认值并打印 warning |
| 4 | 安全 | **change_password 接受 raw dict** | ✅ | `services/auth.py` | 改用 `ChangePasswordRequest` Pydantic Model |
| 5 | 安全 | **密码强度要求过低** | ✅ | `services/auth.py`, `schemas/auth.py` | 最小长度提升至 8 位 |
| 6 | 安全 | **JWT 过期时间 30 天无刷新机制** | ✅ | `config.py` | 过期时间缩短为 2 天 + 启动警告（完整 refresh token 后续实现） |
| 7 | 数据库 | **fund_navs 缺少唯一约束** | ✅ | `models/fund.py` | 添加 `UniqueConstraint(fund_code, date)` + 复合索引 |
| 8 | 数据库 | **signals 缺少唯一约束** | ✅ | `models/signal.py` | 添加 `UniqueConstraint(fund_code, date)` + date 索引 |
| 9 | 数据库 | **watchlists 缺少唯一约束** | ✅ | `models/watchlist.py` | 添加 `UniqueConstraint(user_id, fund_code)` |
| 10 | 数据库 | **auto_configs 缺少 user_id 唯一约束** | ✅ | `models/auto.py` | 添加 `UniqueConstraint(user_id)` |

---

## P1 — 信号引擎优化（核心价值）

| # | 分类 | 任务 | 状态 | 涉及文件 | 说明 |
|---|------|------|------|----------|------|
| 11 | 信号 | **估值因子未接入指数 PE/PB** | ✅ | `signal_engine/engine.py` | 预加载 IndexQuota PE/PB 百分位，传入 calculate_valuation |
| 12 | 信号 | **质量因子子维度缺失** | ✅ | `signal_engine/engine.py` | 从 NAV 数据计算 max_drawdown_pct 并传入（manager_tenure/fund_age 暂不可用） |
| 13 | 信号 | **情绪因子语义偏差** | ✅ | `signal_engine/factors/sentiment.py` | 更新文档注释，明确衡量"基金自身波动风险"而非市场情绪 |
| 14 | 信号 | **因子权重与 PRD/文档不一致** | ✅ | `signal_engine/scorer.py`, `PRD-v2.md` | 更新 docstring 和 PRD 匹配实际权重 15/10/30/30/15 |
| 15 | 信号 | **`score_single_fund` 路径未标准化** | ✅ | `signal_engine/engine.py` | 移除遗留函数，更新 __init__.py |
| 16 | 信号 | **标准化管道硬编码魔数** | ✅ | `signal_engine/engine.py` | 提取为 Z_CLAMP/Z_SCALE/Z_CENTER 模块级常量 |
| 17 | 信号 | **`_stable_stats` 空列表越界风险** | ✅ | `signal_engine/engine.py` | 空列表返回安全默认值 {"mean": 50.0, "std": 10.0} |

---

## P2 — 数据采集优化（基础保障）

| # | 分类 | 任务 | 状态 | 涉及文件 | 说明 |
|---|------|------|------|----------|------|
| 18 | 采集 | **HTTP 请求无重试机制** | ✅ | `data_collector/fund_list.py`, `fund_nav.py` | 添加 `_request_with_retry` 3 次重试 + 指数退避 |
| 19 | 采集 | **`asyncio.gather` 无异常隔离** | ✅ | `data_collector/collector.py` | 添加 `return_exceptions=True` + 逐个检查结果 |
| 20 | 采集 | **基金列表同步 N+1 查询** | ✅ | `data_collector/collector.py` | 改为一次 SELECT 所有已有 code，然后分 insert/update |
| 21 | 采集 | **NAV 去重 O(N*M) 查询** | ✅ | `data_collector/collector.py` | 利用唯一约束 + try/except 降级去重 |
| 22 | 采集 | **N+1 session 创建** | ⬜ | `data_collector/collector.py` | `_fetch_and_prep_nav` 仍独立创建 session（需更大重构） |
| 23 | 采集 | **print() 代替 logging** | ✅ | `data_collector/` 全部文件 | 主要文件替换为 logging 模块 |
| 24 | 采集 | **SQL 注入风险模式** | ✅ | `data_collector/collector.py` | `trim_nav_records` 改用参数化查询 |

---

## P3 — 前端体验优化

| # | 分类 | 任务 | 状态 | 涉及文件 | 说明 |
|---|------|------|------|----------|------|
| 25 | 前端 | **大部分页面无错误状态展示** | ✅ | `pages/` 多个文件 | FundDetail/FundList/Watchlist 添加 error state + 错误提示 |
| 26 | 前端 | **无 Error Boundary** | ✅ | `App.tsx` | 创建 ErrorBoundary 组件，包裹全局路由 |
| 27 | 前端 | **大量 any 类型** | ⬜ | `pages/` 多个文件 | Dashboard/FundList/FundDetail/SignalList/AutoFollow/ManualFollow/ManualPortfolio 状态均为 `any[]` |
| 28 | 前端 | **Backtest 硬编码日期** | ✅ | `pages/Backtest.tsx` | 改为 `new Date().toISOString().split('T')[0]` |
| 29 | 前端 | **Watchlist 添加无验证** | ✅ | `pages/Watchlist.tsx` | 添加 try/catch + 错误提示 UI |
| 30 | 前端 | **搜索无清除按钮** | ✅ | `pages/FundList.tsx` | 搜索激活时显示"清除"按钮 |
| 31 | 前端 | **使用 alert() 提示** | ✅ | `pages/FundDetail.tsx` | 替换为应用内 toast 组件 |
| 32 | 前端 | **响应式布局缺失** | 🔜 | `components/Layout.tsx`, `pages/` | 后续单独 UI 优化任务 |

---

## P4 — API 层优化

| # | 分类 | 任务 | 状态 | 涉及文件 | 说明 |
|---|------|------|------|----------|------|
| 33 | API | **status 参数无枚举校验** | ✅ | `routers/execution_list.py` | 添加 `VALID_STATUSES` 集合校验 |
| 34 | API | **market.py distinct() 兼容性** | ✅ | `routers/market.py` | 改用子查询 + JOIN 方案，兼容 SQLite 和 PostgreSQL |
| 35 | API | **tools.py SQL 拼接模式** | ✅ | `routers/tools.py` | Batch 1 已修复，改用参数化 IN 子句 |
| 36 | API | **无请求频率限制** | ⬜ | `routers/auth.py` | 需要额外依赖（slowapi），暂跳过 |
| 37 | API | **网络请求无统一错误处理** | ✅ | `api/client.ts` | 拦截器添加 500+ 错误日志 |

---

## P5 — 调度器健壮性

| # | 分类 | 任务 | 状态 | 涉及文件 | 说明 |
|---|------|------|------|----------|------|
| 38 | 调度 | **任务失败无告警通知** | ✅ | `services/scheduler.py` | `_run_step` 失败记录耗时 + FAILED 标记，后续步骤有条件跳过 |
| 39 | 调度 | **catchup 逻辑不校验信号数量** | ✅ | `services/scheduler.py` | 添加 `_MIN_SIGNAL_COUNT=1000` 阈值，不足则重新运行 |
| 40 | 调度 | **周日任务与每日任务可能重叠** | ✅ | `services/scheduler.py` | 添加文件锁 `_FileLock`，并发任务自动跳过 |
| 41 | 调度 | **无分布式锁** | ✅ | `services/scheduler.py` | 基于 `fcntl.flock` 的文件锁，SQLite 单实例场景足够 |

---

## P6 — 数据库索引与字段

| # | 分类 | 任务 | 状态 | 涉及文件 | 说明 |
|---|------|------|------|----------|------|
| 42 | 数据库 | **fund_navs 缺少复合索引** | ✅ | `models/fund.py` | Batch 1 已添加 `ix_fund_nav_code_date` 复合索引 |
| 43 | 数据库 | **signals.date 无索引** | ✅ | `models/signal.py` | Batch 1 已添加 `ix_signal_date` 索引 |
| 44 | 数据库 | **trades 表缺少 created_at** | ✅ | `models/auto.py` | Batch 1 迁移已添加 `created_at` 列到 `auto_trades` |

---

## 优先级总览

| 优先级 | 分类 | 数量 | 状态 | 建议 |
|--------|------|------|------|------|
| **P0** | 安全 + 数据完整性 | 10 | ✅ 全部完成 | — |
| **P1** | 信号引擎 | 7 | ✅ 全部完成 | — |
| **P2** | 数据采集 | 7 | ✅ 6/7 完成 | #22 session 复用需更大重构 |
| **P3** | 前端体验 | 8 | ✅ 7/8 完成 | #27 any 类型需逐页改造，#32 响应式布局后续任务 |
| **P4** | API 层 | 5 | ✅ 4/5 完成 | #36 rate limiting 需额外依赖 |
| **P5** | 调度器 | 4 | ✅ 全部完成 | — |
| **P6** | 数据库索引 | 3 | ✅ 全部完成 | — |
| **Phase 1** | 宏观信号模块 | 5 | ✅ 全部完成 | 沪深300 PE百分位驱动评分折扣 |

---

## Phase 1 — 宏观信号模块（2026-05-27 完成）

基于沪深300 PE/PB 百分位判断市场环境，动态调整信号引擎评分。

| # | 分类 | 任务 | 状态 | 涉及文件 | 说明 |
|---|------|------|------|----------|------|
| 43 | 宏观 | **宏观信号服务** | ✅ | `signal_engine/macro.py` | PE百分位 < 30% → risk_on (×1.0)，30-70% → neutral (×0.92)，> 70% → risk_off (×0.75) |
| 44 | 宏观 | **宏观信号 API** | ✅ | `routers/macro.py` | `GET /api/macro-signal` 返回信号等级、折扣系数、PE/PB百分位 |
| 45 | 宏观 | **信号引擎集成宏观折扣** | ✅ | `signal_engine/engine.py` | z-score 归一化后应用宏观乘数，重新派生 level/action |
| 46 | 宏观 | **前端宏观环境指示器** | ✅ | `pages/Dashboard.tsx` | Dashboard 顶部显示宏观信号卡片（积极/中性/防守） |
| 47 | 宏观 | **路由注册 + API客户端** | ✅ | `routers/__init__.py`, `api/client.ts` | macro_router 注册，macroApi 类型添加 |

**效果**：risk_off 环境下所有基金评分打 75 折，大量基金从 B 级降到 C/D 级，避免在高估市场中激进买入。

---

## Phase 2 — 风险指标完善（2026-05-27 进行中）

给每只基金加上风险画像，帮助用户理解"风险有多大"。

| # | 分类 | 任务 | 状态 | 涉及文件 | 说明 |
|---|------|------|------|----------|------|
| 48 | 风险 | **风险指标计算服务** | ⬜ | `signal_engine/risk.py` | 年化波动率、95% VaR、夏普比率、最大回撤、回撤恢复天数 |
| 49 | 风险 | **风险等级分档** | ⬜ | `signal_engine/risk.py` | 低风险(< 10%)、中风险(10-20%)、高风险(> 20%) |
| 50 | 风险 | **风险指标 API** | ⬜ | `routers/funds.py` | `GET /api/funds/{code}/risk` 返回完整风险画像 |
| 51 | 风险 | **前端风险指标卡片** | ⬜ | `pages/FundDetail.tsx` | 风险等级标签 + 指标卡片 (波动率/VaR/夏普/回撤) |
| 52 | 风险 | **信号引擎集成风险等级** | ⬜ | `signal_engine/engine.py` | factors_detail 中附加 risk_metrics |

**预期效果**：用户看到基金评分时，同时看到风险等级，避免只看收益不看风险。

---

## 已完成项（历史）

- ✅ 项目骨架：monorepo + FastAPI + React + SQLite
- ✅ 用户认证：注册 / 登录 / JWT 鉴权
- ✅ 18 张数据表
- ✅ 数据采集：天天基金全市场基金列表 + 净值 + 持仓 + 指数估值
- ✅ 信号引擎：五因子模型
- ✅ 定时调度：APScheduler 每日 20:30 + 周日 21:00
- ✅ 后端 23 个 API 端点
- ✅ 前端 13 个页面
- ✅ 用户设置页（P2 #5）
- ✅ 手动提交流程（P2 #6）
- ✅ 自动执行引擎（P2 #7）
- ✅ 历史回测（P2 #8）
- ✅ 批量净值同步（rankhandler 批量 API，13,674 只基金覆盖）
- ✅ NAV 6 个月窗口优化（130 条/只，节省 96% 数据量）
- ✅ Phase 1: 宏观信号模块（macro.py + API + 信号引擎集成 + Dashboard 指示器）
