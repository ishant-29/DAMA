from fastapi import APIRouter

router = APIRouter()

@router.get("/active")
async def get_active_alerts():
    return [{"id": 1, "message": "Player breakout detected!", "severity": "high"}]
