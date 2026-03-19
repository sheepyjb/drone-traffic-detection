"""
DroneVehicle VOC XML → YOLO TXT 格式转换脚本
处理: 类名拼写错误修正、polygon→HBB转换、标注清洗
"""

import xml.etree.ElementTree as ET
import os
import shutil
from pathlib import Path
from collections import Counter

# ── 类别映射 (修正脏数据) ──────────────────────────────
CLASS_MAP = {
    "car": 0,
    "truck": 0 + 1,    # → 1
    "truvk": 1,          # typo
    "bus": 2,
    "van": 3,
    "feright car": 4,    # typo (space)
    "feright_car": 4,    # typo (underscore)
    "feright": 4,         # truncated
    "freight_car": 4,
    "freight car": 4,
}
# fix: truck=1
CLASS_MAP["truck"] = 1
CLASS_MAP["truvk"] = 1

CLASS_NAMES = ["car", "truck", "bus", "van", "freight_car"]
NUM_CLASSES = 5

# ── 源数据路径 ─────────────────────────────────────────
SRC_ROOT = "/root/autodl-fs"
DST_ROOT = "/root/autodl-tmp/dataset"

SPLITS = {
    "train": {
        "rgb_img": f"{SRC_ROOT}/train/trainimg",
        "ir_img":  f"{SRC_ROOT}/train/trainimgr",
        "rgb_lbl": f"{SRC_ROOT}/train/trainlabel",
        "ir_lbl":  f"{SRC_ROOT}/train/trainlabelr",
    },
    "val": {
        "rgb_img": f"{SRC_ROOT}/val/valimg",
        "ir_img":  f"{SRC_ROOT}/val/valimgr",
        "rgb_lbl": f"{SRC_ROOT}/val/vallabel",
        "ir_lbl":  f"{SRC_ROOT}/val/vallabelr",
    },
    "test": {
        "rgb_img": f"{SRC_ROOT}/test/testimg",
        "ir_img":  f"{SRC_ROOT}/test/testimgr",
        "rgb_lbl": f"{SRC_ROOT}/test/testlabel",
        "ir_lbl":  f"{SRC_ROOT}/test/testlabelr",
    },
}


def polygon_to_hbb(polygon_elem):
    """将 XML polygon (4角点) 转换为 HBB [xmin, ymin, xmax, ymax]"""
    xs, ys = [], []
    for i in range(1, 5):
        x = float(polygon_elem.find(f"x{i}").text)
        y = float(polygon_elem.find(f"y{i}").text)
        xs.append(x)
        ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def convert_xml_to_yolo(xml_path, img_w, img_h):
    """解析一个 VOC XML 文件，返回 YOLO 格式行列表"""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # 尝试从 XML 获取图像尺寸
    size_elem = root.find("size")
    if size_elem is not None:
        w = int(size_elem.find("width").text)
        h = int(size_elem.find("height").text)
        if w > 0 and h > 0:
            img_w, img_h = w, h

    lines = []
    for obj in root.findall("object"):
        name = obj.find("name").text.strip().lower()
        if name == "*" or name not in CLASS_MAP:
            continue

        cls_id = CLASS_MAP[name]

        # 跳过 difficult 标注
        diff = obj.find("difficult")
        if diff is not None and diff.text == "1":
            continue

        polygon = obj.find("polygon")
        if polygon is not None:
            xmin, ymin, xmax, ymax = polygon_to_hbb(polygon)
        else:
            bndbox = obj.find("bndbox")
            if bndbox is None:
                continue
            xmin = float(bndbox.find("xmin").text)
            ymin = float(bndbox.find("ymin").text)
            xmax = float(bndbox.find("xmax").text)
            ymax = float(bndbox.find("ymax").text)

        # 裁剪到图像边界
        xmin = max(0, xmin)
        ymin = max(0, ymin)
        xmax = min(img_w, xmax)
        ymax = min(img_h, ymax)

        # 过滤无效框 (太小)
        bw = xmax - xmin
        bh = ymax - ymin
        if bw < 2 or bh < 2:
            continue

        # 转为 YOLO 归一化格式
        cx = (xmin + xmax) / 2.0 / img_w
        cy = (ymin + ymax) / 2.0 / img_h
        nw = bw / img_w
        nh = bh / img_h

        lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")

    return lines


def process_split(split_name, paths):
    """处理一个数据集分割 (train/val/test)"""
    print(f"\n{'='*60}")
    print(f"Processing: {split_name}")
    print(f"{'='*60}")

    # 创建输出目录 (使用软链接节省磁盘)
    rgb_img_dst = Path(DST_ROOT) / split_name / "images"
    ir_img_dst = Path(DST_ROOT) / split_name / "images_ir"
    lbl_dst = Path(DST_ROOT) / split_name / "labels"

    rgb_img_dst.mkdir(parents=True, exist_ok=True)
    ir_img_dst.mkdir(parents=True, exist_ok=True)
    lbl_dst.mkdir(parents=True, exist_ok=True)

    src_rgb_img = paths["rgb_img"]
    src_ir_img = paths["ir_img"]
    src_rgb_lbl = paths["rgb_lbl"]

    xml_files = sorted([f for f in os.listdir(src_rgb_lbl) if f.endswith(".xml")])
    stats = Counter()
    skipped = 0
    total = 0

    for xml_file in xml_files:
        stem = Path(xml_file).stem
        img_file = stem + ".jpg"

        # 检查 RGB 和 IR 图像都存在
        rgb_path = os.path.join(src_rgb_img, img_file)
        ir_path = os.path.join(src_ir_img, img_file)
        if not os.path.exists(rgb_path) or not os.path.exists(ir_path):
            skipped += 1
            continue

        # 转换标注
        xml_path = os.path.join(src_rgb_lbl, xml_file)
        yolo_lines = convert_xml_to_yolo(xml_path, 840, 712)

        if not yolo_lines:
            skipped += 1
            continue

        # 写 YOLO 标签文件
        txt_path = lbl_dst / (stem + ".txt")
        with open(txt_path, "w") as f:
            f.write("\n".join(yolo_lines) + "\n")

        # 创建软链接 (节省磁盘空间)
        rgb_link = rgb_img_dst / img_file
        ir_link = ir_img_dst / img_file
        if not rgb_link.exists():
            os.symlink(rgb_path, rgb_link)
        if not ir_link.exists():
            os.symlink(ir_path, ir_link)

        # 统计
        for line in yolo_lines:
            cls_id = int(line.split()[0])
            stats[CLASS_NAMES[cls_id]] += 1
        total += 1

    print(f"  Converted: {total} images")
    print(f"  Skipped:   {skipped} images")
    print(f"  Class distribution:")
    for cls_name in CLASS_NAMES:
        cnt = stats.get(cls_name, 0)
        print(f"    {cls_name:15s}: {cnt:>8d}")
    print(f"  Total boxes: {sum(stats.values())}")

    return total


def write_data_yaml():
    """生成 data.yaml 配置文件"""
    yaml_path = Path(DST_ROOT) / "data.yaml"
    content = f"""path: {DST_ROOT}
train: train/images
val: val/images
test: test/images

nc: {NUM_CLASSES}
names:
  0: car
  1: truck
  2: bus
  3: van
  4: freight_car
"""
    with open(yaml_path, "w") as f:
        f.write(content)
    print(f"\ndata.yaml written to: {yaml_path}")


if __name__ == "__main__":
    print("DroneVehicle VOC XML → YOLO TXT Converter")
    print(f"Source: {SRC_ROOT}")
    print(f"Output: {DST_ROOT}")
    print(f"Classes: {CLASS_NAMES}")

    # 清理旧数据
    if os.path.exists(DST_ROOT):
        print(f"\nRemoving old dataset dir: {DST_ROOT}")
        shutil.rmtree(DST_ROOT)

    for split_name, paths in SPLITS.items():
        process_split(split_name, paths)

    write_data_yaml()
    print("\nDone! Dataset ready for training.")
