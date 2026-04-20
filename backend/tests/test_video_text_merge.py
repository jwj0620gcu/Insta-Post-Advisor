"""
영상 빠른 인식 본문 정제/병합 로직 테스트.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.screenshot_api import (
    _strip_video_scene_caption_lines,
    _merge_stt_into_video_result,
    _video_subtitle_payload_insufficient,
)


def test_strip_scene_caption_lines_keeps_real_transcript():
    text = "영상 프레임에 한 여성이 주방에서 요리하는 장면이 표시됩니다\n우리 집 식탁에서 가장 자주 등장하는 요리입니다"
    cleaned = _strip_video_scene_caption_lines(text)
    assert "영상 프레임" not in cleaned
    assert "우리 집 식탁에서 가장 자주 등장하는 요리입니다" in cleaned


def test_merge_stt_replaces_scene_caption_only_payload():
    result = {"content_text": "영상은 한 블로거가 데치지 말라는 자막과 함께 등장하는 장면을 보여줍니다"}
    _merge_stt_into_video_result(result, "절대 데치지 마세요\n이렇게 해야 더 아삭하고 향이 좋아요")
    assert "영상은" not in result["content_text"]
    assert "절대 데치지 마세요" in result["content_text"]


def test_video_payload_insufficient_when_only_scene_caption():
    result = {"content_text": "영상 프레임에 한 여성이 주방에서 버섯을 요리하고 데치지 말라는 자막이 표시됩니다"}
    assert _video_subtitle_payload_insufficient(result) is True
