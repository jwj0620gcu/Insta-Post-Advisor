"""
커버 이미지를 JPEG로 변환/압축해 멀티모달 LLM 입력 크기와 토큰 사용량을 제어한다.
"""
from __future__ import annotations

import io
import os

from PIL import Image


def jpeg_bytes_for_vision(image_bytes: bytes) -> bytes:
    """
    일반 이미지 포맷을 RGB JPEG로 변환한다.
    긴 변이 `VISION_MAX_EDGE`를 넘으면 비율을 유지해 축소한다.

    @param image_bytes - 원본 이미지 바이트
    @returns JPEG 바이트(MIME: image/jpeg)
    """
    max_edge = int(os.getenv("VISION_MAX_EDGE", "1280"))
    max_edge = max(256, min(max_edge, 4096))
    quality = int(os.getenv("VISION_JPEG_QUALITY", "85"))
    quality = max(60, min(quality, 95))

    im = Image.open(io.BytesIO(image_bytes))
    im = im.convert("RGB")
    w, h = im.size
    m = max(w, h)
    if m > max_edge:
        scale = max_edge / m
        im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()
