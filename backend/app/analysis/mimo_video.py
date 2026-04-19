"""
MiMo 비디오 이해(chat.completions 멀티모달) 요청 본문 생성 유틸.

공식 문서(OpenAI 호환 Chat Completions) 기준:
https://platform.xiaomimimo.com/#/docs/usage-guide/multimodal-understanding/video-understanding

핵심 규칙:
- `content` 항목은 `type: video_url` 사용.
- 동일 user 메시지에는 가급적 "비디오 + 텍스트"만 포함(다중 이미지/오디오 혼합 지양).
- `video_url`에는 외부 접근 가능한 `url`과 샘플링 `fps` 포함.
- `media_resolution`은 `video_url`과 같은 레벨에서 `default` 또는 `max`.
"""
from __future__ import annotations

import os
from typing import Optional


def mimo_video_fps() -> float:
    """@returns MiMo 권장 범위로 클램프된 샘플링 FPS."""
    for key in ("MIMO_VIDEO_FPS", "QUICK_RECOGNIZE_VIDEO_FPS"):
        raw = os.getenv(key)
        if raw and raw.strip():
            try:
                return max(0.1, min(float(raw.strip()), 10.0))
            except ValueError:
                break
    return 2.0


def mimo_video_media_resolution() -> str:
    """@returns `default` 또는 `max`(유효하지 않으면 `default`)."""
    r = (os.getenv("MIMO_VIDEO_MEDIA_RESOLUTION") or "default").strip().lower()
    return r if r in ("default", "max") else "default"


def build_mimo_video_url_content_part(
    video_url: str,
    *,
    fps: Optional[float] = None,
    media_resolution: Optional[str] = None,
) -> dict:
    """
    단일 user content part(`video_url` + `media_resolution`)를 생성한다.
    @param video_url - 외부에서 접근 가능한 비디오 URL(HTTPS 권장)
    @param fps - 지정 시 환경값 대신 사용, 미지정 시 `mimo_video_fps()`
    @param media_resolution - `default` | `max`, 미지정 시 환경값 사용
    """
    fps_val = mimo_video_fps() if fps is None else max(0.1, min(float(fps), 10.0))
    if media_resolution is None:
        res = mimo_video_media_resolution()
    else:
        r = str(media_resolution).strip().lower()
        res = r if r in ("default", "max") else mimo_video_media_resolution()
    return {
        "type": "video_url",
        "video_url": {
            "url": video_url,
            "fps": fps_val,
        },
        "media_resolution": res,
    }
