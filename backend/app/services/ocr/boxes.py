"""OCR 框：四点或 [x,y,w,h] → 轴对齐矩形。"""

from __future__ import annotations

from typing import Any


def box_to_xywh(box: Any) -> tuple[float, float, float, float] | None:
    """RapidOCR 四点框或 [x,y,w,h] → 轴对齐矩形。"""
    if box is None:
        return None
    if hasattr(box, "tolist"):
        try:
            box = box.tolist()
        except (TypeError, ValueError):
            return None
    if not isinstance(box, (list, tuple)) or not box:
        return None
    first = box[0]
    xs: list[float]
    ys: list[float]
    if isinstance(first, (list, tuple)) and len(first) >= 2:
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
    else:
        try:
            nums = [float(value) for value in box]
        except (TypeError, ValueError):
            return None
        if len(nums) == 4:
            return nums[0], nums[1], nums[2], nums[3]
        if len(nums) < 8:
            return None
        xs = nums[0:8:2]
        ys = nums[1:8:2]
    x0, y0 = min(xs), min(ys)
    width, height = max(xs) - x0, max(ys) - y0
    if width < 1 or height < 1:
        return None
    return x0, y0, width, height
