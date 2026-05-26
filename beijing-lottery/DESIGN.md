# 北京小客车摇号模拟器 — 设计文档

## 核心规则（个人摇号）

1. **申请**：每人一个申请编码，进入摇号池
2. **阶梯基数**：
   - 初始：1 个机会
   - 每摇 6 次不中 → 基数 +1（1→2→3→4→...，无上限）
3. **中签概率** = 你的机会数 / 全池总机会数
4. **每月开奖**：从池中按概率抽取 N 个中签者
5. **中签后**：退出摇号池

## 功能规划

### MVP（个人视角）
- 创建/重置个人档案
- 每月模拟摇号（点一次 = 一个月）
- 记录每次结果 + 累计统计数据
- 显示概率变化曲线
- 支持快进模拟（跑 N 个月）

### 扩展（暂时不做）
- 家庭摇号 / 新能源轮候
- 多人竞争模拟
- 历史中签率数据

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python + FastAPI |
| 前端 | React + Vite + TailwindCSS |
| 数据库 | SQLite（单人数据，足够） |
| 图表 | Recharts |

## 数据结构

```
lottery_profile:
  name: str           # 申请人姓名
  created_at: date
  base_chances: int   # 阶梯基数（初始=1）
  total_attempts: int # 累计摇号次数
  is_winner: bool     # 是否已中签
  won_at_attempt: int # 第几次中签

lottery_record:
  id: int
  attempt_number: int  # 第N次摇号
  date: date
  outcome: bool        # 中/未中
  chances: int         # 当时的机会数
  total_pool_chances: int  # 全池机会数
  pool_size: int       # 总申请人
  probability_pct: float  # 当时概率
```

## 模拟器参数

- 全池参与人数：固定（简化模拟：指定一个池子规模）
- 每月中签名额：固定数字
- 非用户申请人的基数随机分配（1~3）
