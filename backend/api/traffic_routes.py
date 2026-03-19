"""交通分析 REST 端点"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from services.traffic import analyze_traffic, check_zone_violations

router = APIRouter(prefix="/traffic", tags=["traffic"])


# ===== 请求模型 =====

class VehicleItem(BaseModel):
    track_id: int = 0
    class_id: int = 0
    class_name: str = ""
    confidence: float = 0.0
    cx: float = 0.5
    cy: float = 0.5


class BoundsItem(BaseModel):
    north: float = 0
    south: float = 0
    east: float = 0
    west: float = 0


class AnalyzeRequest(BaseModel):
    vehicles: List[VehicleItem] = []
    bounds: Optional[BoundsItem] = None


class PositionItem(BaseModel):
    lng: float = 0
    lat: float = 0


class ZoneVehicle(BaseModel):
    track_id: int = 0
    class_id: int = 0
    class_name: str = ""
    position: PositionItem = PositionItem()


class ZonePolygonPoint(BaseModel):
    lng: float = 0
    lat: float = 0


class ZoneItem(BaseModel):
    id: str = ""
    name: str = ""
    polygon: List[ZonePolygonPoint] = []
    restrictedClasses: List[int] = []
    color: str = "#ff0000"


class ZoneCheckRequest(BaseModel):
    vehicles: List[ZoneVehicle] = []
    zones: List[ZoneItem] = []


# ===== 端点 =====

@router.post("/analyze")
async def traffic_analyze(req: AnalyzeRequest):
    """分析车流并生成配时策略"""
    vehicles = [v.model_dump() for v in req.vehicles]
    return analyze_traffic(vehicles)


@router.post("/zone-check")
async def traffic_zone_check(req: ZoneCheckRequest):
    """检查区域违规"""
    vehicles = [v.model_dump() for v in req.vehicles]
    zones = [z.model_dump() for z in req.zones]
    alerts = check_zone_violations(vehicles, zones)
    return {"alerts": alerts}
