"""EMA 时序平滑器"""
from config import EMA_ALPHA


class EMATracker:
    """
    对 ByteTrack 输出的 bbox 和 confidence 做 EMA 时序平滑，
    减少帧间检测框抖动。
    """

    def __init__(self, alpha: float = EMA_ALPHA):
        self.alpha = alpha
        # track_id -> { bbox: [x1,y1,x2,y2], confidence: float, age: int }
        self.states: dict[int, dict] = {}

    def update(self, tracks: list[dict]) -> list[dict]:
        """
        输入原始 tracks，返回平滑后的 tracks。
        """
        active_ids = set()
        smoothed = []

        for t in tracks:
            tid = t["track_id"]
            active_ids.add(tid)
            bbox = t["bbox"]
            conf = t["confidence"]

            if tid in self.states:
                prev = self.states[tid]
                # EMA 平滑
                new_bbox = [
                    self.alpha * b + (1 - self.alpha) * p
                    for b, p in zip(bbox, prev["bbox"])
                ]
                new_conf = self.alpha * conf + (1 - self.alpha) * prev["confidence"]
                prev["bbox"] = new_bbox
                prev["confidence"] = round(new_conf, 3)
                prev["age"] += 1
            else:
                self.states[tid] = {
                    "bbox": list(bbox),
                    "confidence": conf,
                    "age": 1,
                }

            state = self.states[tid]
            smoothed.append({
                **t,
                "bbox": [round(v, 5) for v in state["bbox"]],
                "confidence": state["confidence"],
                "age": state["age"],
            })

        # 清理消失的 track
        stale = [tid for tid in self.states if tid not in active_ids]
        for tid in stale:
            del self.states[tid]

        return smoothed

    def reset(self):
        self.states.clear()
