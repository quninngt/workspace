"""FastAPI router for Beijing Lottery Simulator."""
from fastapi import APIRouter, HTTPException
from app.simulator import get_profile, reset_profile, get_stats

router = APIRouter(prefix="/api/lottery", tags=["lottery"])


@router.get("/profile")
async def profile():
    """Get current lottery profile."""
    p = get_profile()
    return p.to_dict()


@router.post("/reset")
async def reset():
    """Reset lottery profile."""
    reset_profile()
    return {"ok": True}


@router.post("/draw")
async def draw():
    """Run one lottery draw (1 draw = half a year)."""
    p = get_profile()
    if p.is_winner:
        raise HTTPException(status_code=400, detail="已经中签了！重置后重新开始。")
    result = p.draw()
    result["profile"] = {
        "total_attempts": p.total_attempts,
        "base_chances": p.base_chances,
        "probability_pct": round(p.probability_pct, 4),
        "is_winner": p.is_winner,
    }
    return result


@router.post("/draw-batch")
async def draw_batch(years: int = 3):
    """Run N years of lottery draws (1 year = 2 draws)."""
    if years < 1 or years > 60:
        raise HTTPException(status_code=400, detail="年数应在 1-60 之间")
    p = get_profile()
    if p.is_winner:
        raise HTTPException(status_code=400, detail="已经中签了！重置后重新开始。")
    results = p.draw_batch(years)
    return {
        "years_attempted": years,
        "draws_attempted": len(results),
        "won": p.is_winner,
        "won_at_attempt": p.won_at_attempt,
        "results": results,
        "current_profile": {
            "total_attempts": p.total_attempts,
            "base_chances": p.base_chances,
            "probability_pct": round(p.probability_pct, 4),
        },
    }


@router.get("/stats")
async def stats():
    """Get lottery statistics."""
    return get_stats()


@router.get("/records")
async def records():
    """Get all draw records."""
    p = get_profile()
    return {"records": p.records, "total": len(p.records)}


@router.get("/probability-trend")
async def probability_trend():
    """Get probability trend data for charting."""
    p = get_profile()
    trend = []
    for r in p.records:
        trend.append({
            "attempt": r["attempt"],
            "probability_pct": r["probability_pct"],
            "chances": r["chances"],
            "won": r["won"],
        })
    return {"trend": trend}
