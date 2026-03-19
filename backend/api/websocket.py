"""WebSocket 实时视频检测 — 高性能二进制流水线版（无人机交通检测）
协议：
  text frame  → JSON metadata（tracks, fps, latency, frame_id 等）
  binary frame → JPEG 图像字节（紧跟 text frame 之后）
前端需要按照 text → binary 交替接收。
"""
import asyncio
import collections
import json
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
import cv2
import numpy as np

from fastapi import WebSocket, WebSocketDisconnect

from config import UPLOAD_DIR
from models.tracker import EMATracker

# ---- TurboJPEG（可选加速） ----
_turbo_jpeg = None
try:
    from turbojpeg import TurboJPEG
    _turbo_jpeg = TurboJPEG()  # Linux 自动查找 .so, Windows 需要在 PATH 中
    print("[WS] TurboJPEG 加速已启用")
except Exception:
    print("[WS] TurboJPEG 不可用，回退到 cv2.imencode")

# 全局推理线程池（单线程，GPU 推理串行）
_inference_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="yolo-infer")

# ---- 常量 ----
TARGET_FPS = 20          # 目标输出帧率（限速发送，减轻前端压力）
TRANSMIT_WIDTH = 960     # 传输帧最大宽度（MapView面板仅560px，960足够）
JPEG_QUALITY = 75        # JPEG 压缩质量（75视觉无明显差异，体积减30%）
QUEUE_MAXSIZE = 15       # 帧队列容量（~0.75秒缓冲，吸收推理时间抖动）
FPS_WINDOW = 20          # FPS 滑动窗口大小（帧数）
MAX_MASK_POINTS = 50     # WebSocket 传输中 mask 多边形最大点数
INFER_INTERVAL = 2       # 每 N 帧推理一次（2=每2帧推理1次，平衡流畅与性能）


# =====================================================================
#  FrameReader — 独立线程预读视频帧，消除 cv2.read() 阻塞推理
# =====================================================================
class FrameReader:
    """独立线程预读视频帧。
    改进：阻塞式生产，读出一帧后等待消费者取走再读下一帧，
    避免推理慢于读取时大量跳帧导致视频加速。
    """
    def __init__(self, cap: cv2.VideoCapture):
        self._cap = cap
        self._lock = threading.Lock()
        self._frame = None
        self._frame_pos = 0
        self._finished = False
        self._stop = threading.Event()
        self._has_frame = threading.Event()       # 通知消费者：有帧可取
        self._consumed = threading.Event()         # 通知生产者：上一帧已被消费
        self._consumed.set()                       # 初始状态：可以开始读第一帧
        self._thread = threading.Thread(target=self._run, daemon=True, name="frame-reader")
        self._thread.start()

    def _run(self):
        pos = 0
        while not self._stop.is_set():
            # 等待消费者取走上一帧（或初始状态）
            if not self._consumed.wait(timeout=0.5):
                continue
            if self._stop.is_set():
                return
            self._consumed.clear()

            ret, frame = self._cap.read()
            if not ret:
                with self._lock:
                    self._finished = True
                self._has_frame.set()
                return
            pos += 1
            with self._lock:
                self._frame = frame
                self._frame_pos = pos
            self._has_frame.set()

    def get(self, timeout: float = 1.0):
        if not self._has_frame.wait(timeout=timeout):
            with self._lock:
                return None

        with self._lock:
            if self._finished and self._frame is None:
                return None
            frame = self._frame
            pos = self._frame_pos
            self._frame = None
            self._has_frame.clear()

        # 通知生产者可以读下一帧
        self._consumed.set()

        if frame is None:
            return None
        return (frame, pos)

    def stop(self):
        self._stop.set()
        self._consumed.set()  # 解除生产者可能的阻塞
        self._thread.join(timeout=2.0)

    @property
    def finished(self):
        with self._lock:
            return self._finished


def _simplify_mask(mask_poly, max_points=MAX_MASK_POINTS):
    """简化 mask 多边形点数，减少 WebSocket 传输体积"""
    if not mask_poly or len(mask_poly) <= max_points:
        return mask_poly
    step = len(mask_poly) / max_points
    return [mask_poly[int(i * step)] for i in range(max_points)]


def _encode_jpeg(frame: np.ndarray, quality: int = JPEG_QUALITY, max_width: int = TRANSMIT_WIDTH) -> bytes:
    h, w = frame.shape[:2]
    if w > max_width:
        scale = max_width / w
        frame = cv2.resize(frame, (max_width, int(h * scale)), interpolation=cv2.INTER_LINEAR)

    if _turbo_jpeg is not None:
        return _turbo_jpeg.encode(frame, quality=quality)
    else:
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buf.tobytes()


async def ws_detect_handler(websocket: WebSocket, detector):
    await websocket.accept()
    ema = EMATracker()
    stop_event = asyncio.Event()
    pause_event = asyncio.Event()
    pause_event.set()

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "start":
                source = data.get("source", "")
                if source.startswith("rtsp://") or source.startswith("http://"):
                    video_source = source
                else:
                    video_source = str(UPLOAD_DIR / source)

                stop_event.clear()
                pause_event.set()
                await _stream_detection(websocket, detector, video_source, ema, stop_event, pause_event)

            elif action == "stop":
                stop_event.set()
                pause_event.set()
                ema.reset()
                await websocket.send_json({"type": "status", "connected": True, "message": "stopped"})

            elif action == "pause":
                pause_event.clear()
                await websocket.send_json({"type": "status", "connected": True, "message": "paused"})

            elif action == "resume":
                pause_event.set()
                await websocket.send_json({"type": "status", "connected": True, "message": "resumed"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass


def _sync_detect_from_reader(reader: FrameReader, detector, last_tracks_holder: list):
    """读取一帧并推理（或跳帧复用上次结果）。
    last_tracks_holder: [tracks, frame_count] — 可变列表用于跨帧保持状态。
    """
    t_start = time.time()

    result = reader.get(timeout=0.5)
    if result is None:
        return None

    frame, frame_pos = result
    t_got = time.time()

    frame_count = last_tracks_holder[1] = last_tracks_holder[1] + 1

    # 跳帧：只在第 N 帧执行推理，中间帧复用上次检测结果
    if frame_count % INFER_INTERVAL == 0 or not last_tracks_holder[0]:
        results = detector.track(frame)
        tracks = results[0]["tracks"] if results else []
        # 简化 mask 多边形以减少传输体积
        for t in tracks:
            if t.get("mask"):
                t["mask"] = _simplify_mask(t["mask"])
        last_tracks_holder[0] = tracks
    else:
        tracks = last_tracks_holder[0]

    t_infer = time.time()

    jpeg_bytes = _encode_jpeg(frame)
    t_encode = time.time()

    infer_ms = (t_infer - t_got) * 1000
    encode_ms = (t_encode - t_infer) * 1000
    total_ms = (t_encode - t_start) * 1000

    return (jpeg_bytes, tracks, infer_ms, frame_pos, total_ms, encode_ms)


async def _stream_detection(websocket: WebSocket, detector, source: str, ema: EMATracker, stop_event: asyncio.Event, pause_event: asyncio.Event):
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        await websocket.send_json({"type": "error", "message": f"Cannot open: {source}"})
        return

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 25

    await websocket.send_json({
        "type": "video_info",
        "total_frames": total_frames,
        "src_fps": round(src_fps, 1),
        "duration_s": round(total_frames / src_fps, 1) if src_fps > 0 else 0,
    })

    reader = FrameReader(cap)
    loop = asyncio.get_event_loop()
    detect_count = 0
    last_tracks_holder = [[], 0]  # [tracks, frame_count] — 跳帧状态

    frame_queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    producer_done = asyncio.Event()

    async def producer():
        nonlocal detect_count
        try:
            while not stop_event.is_set() and not reader.finished:
                if not pause_event.is_set():
                    await pause_event.wait()
                    if stop_event.is_set():
                        break

                result = await loop.run_in_executor(
                    _inference_pool,
                    _sync_detect_from_reader, reader, detector, last_tracks_holder
                )

                if result is None:
                    break

                jpeg_bytes, raw_tracks, infer_ms, frame_pos, total_ms, encode_ms = result
                detect_count += 1

                if detect_count % 30 == 0:
                    print(f"[Perf] infer={infer_ms:.1f}ms encode={encode_ms:.1f}ms total={total_ms:.1f}ms frame_pos={frame_pos}")

                smoothed = ema.update(raw_tracks)
                item = (jpeg_bytes, smoothed, infer_ms, frame_pos, detect_count)

                if frame_queue.full():
                    try:
                        frame_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                await frame_queue.put(item)

        except Exception as e:
            print(f"[WS] Producer error: {e}")
            traceback.print_exc()
        finally:
            producer_done.set()

    async def client_listener():
        try:
            while not stop_event.is_set():
                try:
                    client_msg = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                    act = client_msg.get("action")
                    if act == "stop":
                        stop_event.set()
                        return
                    elif act == "pause":
                        pause_event.clear()
                    elif act == "resume":
                        pause_event.set()
                except asyncio.TimeoutError:
                    if producer_done.is_set():
                        break
                    continue
                except (WebSocketDisconnect, Exception):
                    break
        except Exception:
            pass

    async def consumer():
        send_timestamps = collections.deque(maxlen=FPS_WINDOW)
        next_send_at = time.perf_counter()
        target_interval = 1.0 / TARGET_FPS  # 限速：控制发送帧率上限
        try:
            while True:
                try:
                    item = await asyncio.wait_for(frame_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    if producer_done.is_set() and frame_queue.empty():
                        break
                    continue

                jpeg_bytes, smoothed, infer_ms, frame_pos, dcount = item

                # 匀速发送：等待到目标间隔再发，避免丢帧造成卡顿
                sleep_for = next_send_at - time.perf_counter()
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                send_perf = time.perf_counter()
                send_wall = time.time()
                while next_send_at <= send_perf:
                    next_send_at += target_interval

                send_timestamps.append(send_perf)
                if len(send_timestamps) >= 2:
                    span = send_timestamps[-1] - send_timestamps[0]
                    actual_fps = (len(send_timestamps) - 1) / span if span > 0 else 0.0
                else:
                    actual_fps = 0.0

                meta = {
                    "type": "detection",
                    "frame_id": frame_pos,
                    "total_frames": total_frames,
                    "timestamp": send_wall,
                    "fps": round(actual_fps, 1),
                    "latency_ms": round(infer_ms, 1),
                    "tracks": smoothed,
                }
                await websocket.send_text(json.dumps(meta))
                await websocket.send_bytes(jpeg_bytes)

                if stop_event.is_set():
                    break

        except Exception as e:
            print(f"[WS] Consumer error: {e}")
            traceback.print_exc()

    try:
        await asyncio.gather(producer(), consumer(), client_listener())
    except Exception as e:
        print(f"[WS] Stream error: {e}")
        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        reader.stop()
        cap.release()
        try:
            await websocket.send_json({
                "type": "status",
                "connected": True,
                "message": "stream_ended",
                "total_processed": detect_count,
                "total_frames": total_frames,
            })
        except:
            pass
