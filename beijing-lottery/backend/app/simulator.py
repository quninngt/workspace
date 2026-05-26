"""Lottery simulation engine for Beijing 摇号.

Rules (as of 2024-2025):
- 一年两期: June and December
- 阶梯基数: 初始1, 每2次不中+1 (1→2→3→...)
- 每期抽 N 个名额
- 每人有多个"机会数"(基数), 基数越高权重越大
- 概率 = 你的机会数 / 全池总机会数
"""
import random
from typing import Optional

# Real Beijing lottery parameters (approximate 2024-2025)
POOL_SIZE = 2_600_000        # 个人燃油车申请人数 (approx 260万)
QUOTA_PER_DRAW = 19_000       # 每期指标数 (一年两期, 全年约38,000)
MIN_CHANCES = 1               # 初始基数
CHANCE_INTERVAL = 2           # 每2次不中基数+1
DRAWS_PER_YEAR = 2            # 一年两期摇号


def _other_avg_chances(pool_avg_draws: float = 12) -> float:
    """估算其他申请人的平均基数。
    pool_avg_draws: 全池平均摇号次数 (default ~6年).
    """
    intervals = pool_avg_draws // CHANCE_INTERVAL
    return MIN_CHANCES + intervals


class LotteryProfile:
    def __init__(self, name: str = "我"):
        self.name = name
        self.total_attempts = 0
        self.is_winner = False
        self.won_at_attempt: Optional[int] = None
        self.records: list[dict] = []

    @property
    def base_chances(self) -> int:
        """阶梯基数: 每 CHANCE_INTERVAL 次不中 +1."""
        if self.total_attempts == 0:
            return MIN_CHANCES
        intervals = self.total_attempts // CHANCE_INTERVAL
        return MIN_CHANCES + intervals

    def _calc_probability(self) -> tuple[float, int, int]:
        """返回 (probability_pct, my_chances, total_chances_in_pool)."""
        my_chances = self.base_chances
        others_avg = _other_avg_chances()
        total_chances = int((POOL_SIZE - 1) * others_avg + my_chances)
        # 每期抽 QUOTA_PER_DRAW 个名额, 每个名额独立抽签
        single_trial = my_chances / total_chances
        prob = 1 - (1 - single_trial) ** QUOTA_PER_DRAW
        return prob * 100, my_chances, total_chances

    @property
    def probability_pct(self) -> float:
        p, _, _ = self._calc_probability()
        return p

    def draw(self) -> dict:
        """模拟一期摇号."""
        if self.is_winner:
            return {"error": "Already won"}
        self.total_attempts += 1
        prob, chances, total_chances = self._calc_probability()
        won = random.random() < (prob / 100)
        if won:
            self.is_winner = True
            self.won_at_attempt = self.total_attempts
        record = {
            "attempt": self.total_attempts,
            "won": won,
            "chances": chances,
            "total_pool_chances": total_chances,
            "pool_size": POOL_SIZE,
            "quota_per_draw": QUOTA_PER_DRAW,
            "probability_pct": round(prob, 4),
        }
        self.records.append(record)
        return record

    def draw_batch(self, years: int) -> list[dict]:
        """模拟 N 年 (每期 = 半年一次)."""
        results = []
        draws = years * DRAWS_PER_YEAR
        for _ in range(draws):
            if self.is_winner:
                break
            results.append(self.draw())
        return results

    def reset(self):
        self.total_attempts = 0
        self.is_winner = False
        self.won_at_attempt = None
        self.records = []

    def to_dict(self) -> dict:
        prob, chances, total_ch = self._calc_probability()
        return {
            "name": self.name,
            "pool_size": POOL_SIZE,
            "quota_per_draw": QUOTA_PER_DRAW,
            "total_attempts": self.total_attempts,
            "base_chances": chances,
            "probability_pct": round(prob, 4),
            "is_winner": self.is_winner,
            "won_at_attempt": self.won_at_attempt,
            "records": self.records,
            "simulation_params": {
                "pool_size": POOL_SIZE,
                "quota_per_draw": QUOTA_PER_DRAW,
                "avg_others_draws": 12,
                "avg_others_chances": _other_avg_chances(),
                "chance_interval": CHANCE_INTERVAL,
                "draws_per_year": DRAWS_PER_YEAR,
            },
        }


_store: dict[str, LotteryProfile] = {}


def get_profile(name: str = "我") -> LotteryProfile:
    if name not in _store:
        _store[name] = LotteryProfile(name)
    return _store[name]


def reset_profile(name: str = "我"):
    if name in _store:
        _store[name].reset()


def get_stats() -> dict:
    p = get_profile()
    if not p.records:
        return {
            "total_draws": 0,
            "avg_probability": 0,
            "max_probability": 0,
            "min_probability": 0,
            "is_winner": False,
            "draws_to_win": None,
            "current_chances": 1,
            "current_probability": round(p.probability_pct, 4),
        }
    probs = [r["probability_pct"] for r in p.records]
    return {
        "total_draws": len(p.records),
        "avg_probability": round(sum(probs) / len(probs), 4),
        "max_probability": round(max(probs), 4),
        "min_probability": round(min(probs), 4),
        "is_winner": p.is_winner,
        "draws_to_win": p.won_at_attempt,
        "current_chances": p.base_chances,
        "current_probability": round(p.probability_pct, 4),
    }
