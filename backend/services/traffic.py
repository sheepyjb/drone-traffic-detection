"""交通流分析、红绿灯配时、区域违规检测"""
import math
import time
import uuid

# ===== 配时参数 =====
BASE_CYCLE = 120   # 总周期 (秒)
MIN_GREEN = 15     # 最小绿灯时间

DIRECTION_MAP = {
    "north": "南北方向 (北)",
    "south": "南北方向 (南)",
    "east": "东西方向 (东)",
    "west": "东西方向 (西)",
}


def classify_direction(cx: float, cy: float) -> str:
    """按归一化坐标分配方向: cy<0.5→north, cy>=0.5→south, cx<0.5→west, cx>=0.5→east
    取距中心更远的轴作为主方向"""
    dx = abs(cx - 0.5)
    dy = abs(cy - 0.5)
    if dy >= dx:
        return "north" if cy < 0.5 else "south"
    else:
        return "west" if cx < 0.5 else "east"


def analyze_traffic(vehicles: list) -> dict:
    """分析车流并生成配时策略"""
    dir_counts = {"north": 0, "south": 0, "east": 0, "west": 0}

    for v in vehicles:
        d = classify_direction(v.get("cx", 0.5), v.get("cy", 0.5))
        dir_counts[d] += 1

    ns_count = dir_counts["north"] + dir_counts["south"]
    ew_count = dir_counts["east"] + dir_counts["west"]
    total = ns_count + ew_count

    if total == 0:
        ns_green = BASE_CYCLE // 2
        ew_green = BASE_CYCLE // 2
    else:
        ns_weight = ns_count / total
        ew_weight = ew_count / total
        ns_green = max(MIN_GREEN, round(BASE_CYCLE * ns_weight))
        ew_green = max(MIN_GREEN, BASE_CYCLE - ns_green)

    directions = [
        {
            "name": "north",
            "label": "北",
            "vehicleCount": dir_counts["north"],
            "greenSeconds": ns_green,
        },
        {
            "name": "south",
            "label": "南",
            "vehicleCount": dir_counts["south"],
            "greenSeconds": ns_green,
        },
        {
            "name": "east",
            "label": "东",
            "vehicleCount": dir_counts["east"],
            "greenSeconds": ew_green,
        },
        {
            "name": "west",
            "label": "西",
            "vehicleCount": dir_counts["west"],
            "greenSeconds": ew_green,
        },
    ]

    # 起始相位: 车多的方向先行
    current_phase = "NS" if ns_count >= ew_count else "EW"

    # 生成文字报告
    report_lines = [
        f"=== 交通信号配时策略报告 ===",
        f"分析时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"检测车辆总数: {total}",
        f"",
        f"方向分布:",
        f"  北: {dir_counts['north']} 辆  南: {dir_counts['south']} 辆  (南北合计: {ns_count})",
        f"  东: {dir_counts['east']} 辆  西: {dir_counts['west']} 辆  (东西合计: {ew_count})",
        f"",
        f"配时策略 (总周期 {BASE_CYCLE}s):",
        f"  南北方向绿灯: {ns_green}s",
        f"  东西方向绿灯: {ew_green}s",
        f"  起始相位: {'南北' if current_phase == 'NS' else '东西'}优先",
        f"",
        f"建议: {'南北方向车流较大，优先放行' if ns_count > ew_count else '东西方向车流较大，优先放行' if ew_count > ns_count else '各方向车流均衡'}",
    ]

    return {
        "currentPhase": current_phase,
        "greenRemaining": ns_green if current_phase == "NS" else ew_green,
        "cycleLength": BASE_CYCLE,
        "directions": directions,
        "report": "\n".join(report_lines),
    }


# ===== 区域违规检测 =====

def point_in_polygon(point: dict, polygon: list) -> bool:
    """射线法判断点是否在多边形内"""
    x, y = point["lng"], point["lat"]
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]["lng"], polygon[i]["lat"]
        xj, yj = polygon[j]["lng"], polygon[j]["lat"]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def check_zone_violations(vehicles: list, zones: list) -> list:
    """检查车辆是否在限制区域内"""
    alerts = []
    for v in vehicles:
        pos = v.get("position", {})
        class_id = v.get("class_id", -1)
        for zone in zones:
            if class_id in zone.get("restrictedClasses", []):
                if point_in_polygon(pos, zone.get("polygon", [])):
                    alerts.append({
                        "id": str(uuid.uuid4())[:8],
                        "zoneName": zone.get("name", "未知区域"),
                        "track_id": v.get("track_id", 0),
                        "class_name": v.get("class_name", "unknown"),
                        "timestamp": int(time.time() * 1000),
                        "position": pos,
                    })
    return alerts
