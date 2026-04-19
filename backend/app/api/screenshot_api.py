"""
다차원 스크린샷 업로드 + AI 빠른 인식 + 심층 분석 API.
커버/본문/프로필/댓글 스크린샷 및 영상 업로드를 지원한다.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from PIL import Image

from app.agents.base_agent import _get_client, _is_mimo_openai_compat, _llm_provider, _parse_json_from_llm_text
from app.analysis.mimo_video import build_mimo_video_url_content_part
from app.analysis.video_stt import transcribe_video_with_whisper
from app.api.diagnose import (
    MAX_VIDEO_SIZE,
    MIME_TO_EXT,
    MIMO_VIDEO_MIME,
    _extract_first_video_frame,
    _store_temp_video_and_build_url,
    get_public_base_url_diagnostics,
)

router = APIRouter()
logger = logging.getLogger("instarx.screenshot")


def _env_int(name: str, default: int, *, min_v: int, max_v: int) -> int:
    """정수형 환경변수를 읽고 [min_v, max_v] 범위로 클램프한다."""
    try:
        v = int(os.getenv(name, str(default)))
    except ValueError:
        v = default
    return max(min_v, min(v, max_v))


def _env_float(name: str, default: float, *, min_v: float, max_v: float) -> float:
    """실수형 환경변수를 읽고 [min_v, max_v] 범위로 클램프한다."""
    try:
        v = float(os.getenv(name, str(default)))
    except ValueError:
        v = default
    return max(min_v, min(v, max_v))


def _quick_image_max_out_tokens() -> int:
    """빠른 이미지 인식 토큰 상한. 과도한 max_completion_tokens 거절을 방지한다."""
    return _env_int("QUICK_RECOGNIZE_MAX_COMPLETION_TOKENS", 2048, min_v=256, max_v=8192)


def _quick_ocr_max_tokens() -> int:
    """빠른 OCR 토큰 상한. 긴 content JSON 절단을 줄이기 위한 값이다."""
    return _env_int("QUICK_RECOGNIZE_OCR_MAX_TOKENS", 2048, min_v=512, max_v=8192)


MAX_IMAGE_SIZE = 10 * 1024 * 1024
ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_MIME = {"video/mp4", "video/webm", "video/quicktime"}

SLOT_LABELS = {
    "cover": "커버 이미지",
    "content": "본문 스크린샷",
    "profile": "프로필 스크린샷",
    "comments": "댓글 스크린샷",
}

_QUICK_PROMPT = """이 인스타그램 스크린샷의 타입을 판별하고 텍스트를 추출하라.

## slot_type 판별 규칙
- cover: 커버/썸네일처럼 대표 이미지 중심 화면
- content: 캡션/본문/해시태그가 읽히는 게시물 화면
- comments: 댓글 목록 화면(프로필+닉네임+댓글 텍스트)
- profile: 프로필 정보 + 게시물 그리드 화면
- other: 위 타입이 아님

## 추출 규칙
- title: content 타입에서만 추출, 없으면 ""
- content_text: content 타입에서만 추출, 없으면 ""
- title/content_text는 화면에 실제 보이는 원문만 사용하고 번역/의역 금지
- category: 아래 키 중 하나
  food / fashion / tech / travel / beauty / fitness / business / lifestyle / education / shop
- summary: 1문장 요약(반드시 한국어)
- likes: 화면에서 보이는 좋아요 수(정수), 없으면 0

보이지 않는 정보는 절대 추측하지 말고 빈 값으로 둔다.

평탄한 JSON 하나만 출력:
{"slot_type":"","category":"","title":"","content_text":"","summary":"","confidence":0.0,"likes":0}"""

_VIDEO_QUICK_PROMPT = """너는 인스타 릴스/영상 콘텐츠 이해 보조 AI다. 입력은 전체 영상 파일이다.

## title 규칙(매우 중요)
인스타 게시물 title은 장면 설명문과 다르며, 영상만으로는 확정하기 어려운 경우가 많다.
- **title은 기본적으로 \"\"(빈 문자열)** 로 둔다.
- 게시 화면의 제목란 텍스트가 명확히 보이는 경우에만 title에 반영한다.
- 장면 설명, 단계 안내, 음성 요약, 스티커/자막 문구, \"영상은 ~를 보여준다\" 유형 문장은 title에 넣지 않는다.
- 제목 자동 입력이 필요하면 제목/커버가 보이는 스크린샷을 별도 업로드해야 한다.

## content_text 규칙(매우 중요)
영상 처음부터 끝까지 확인해 **시간 순서대로** 텍스트를 추출한다.
- 화면 자막/꽃자막/스티커/오버레이/팝업 텍스트를 가능한 한 원문 그대로 기록한다.
- 화면 텍스트가 없고 음성이 명확하면 음성도 연속 텍스트로 전사해 포함한다.
- \"영상은 ~를 보여준다\" 같은 메타 설명문을 본문으로 쓰지 않는다(필요 시 summary에 1문장만).
- 해시태그 #xxx가 보이면 순서대로 content_text에 포함한다.
- 불명확한 구간은 `[인식 불가]`로 표기한다(예: `[약 00:15 인식 불가]`).
- 동일 문구가 반복되면 하나로 합치고 `(반복)`을 붙일 수 있다.

## 기타 필드
1) slot_type: 대부분 content. 프로필 화면은 profile, 댓글 목록은 comments, 그 외는 other.
2) extra_slots: 빠른 스크린샷 인식 규칙과 동일.
3) category: quick 규칙의 category 키 사용.
4) summary: 1~2문장 전체 요약(사람이 빠르게 훑는 용도). content_text 대체 금지.
   summary는 반드시 한국어로 작성한다.
5) confidence: 0~1, 자막/전사 정확도 및 완성도 신뢰도.

JSON만 출력하고 markdown 코드블록은 금지:
{"slot_type": "", "extra_slots": [], "category": "", "title": "", "content_text": "", "summary": "", "confidence": 0.0}"""

_VIDEO_SUBTITLE_TRANSCRIPT_PROMPT = """너는 영상 자막/음성 전사 전담 AI다. 입력은 전체 영상이다.

## 유일한 작업
영상 처음부터 끝까지 보고, 시간 순서대로 항목을 나열한다.
- 화면 자막/꽃자막/스티커/오버레이 문구
- 명확히 들리는 음성 문장

## 출력 형식(고정)
JSON만 출력하고 markdown 코드블록은 금지:
{"subtitle_lines":["첫 문장","둘째 문장","셋째 문장",...]}

## 필수 규칙
- subtitle_lines는 가능한 한 충분히 길고 세분화한다(한두 문장 요약 금지).
- category/title/summary/slot_type 등 다른 필드는 출력 금지.
- 장면 설명문(예: \"영상은 ~를 보여준다\") 금지. 원문 자막/대사만 기록.
- 후반부/엔딩 구간도 초반과 동일하게 누락 없이 반영한다.
- 불명확 구간은 `[인식 불가]`로 표기한다.
- 반복 문장은 1회만 남기고 `(반복)` 표시 가능."""

_DEEP_PROMPT_COVER = """인스타 커버/썸네일의 시각 흡인력을 분석하고 JSON으로 출력:
{"visual_score": 0-100, "color_scheme": "배색 설명", "composition": "구도 평가", "text_overlay": "텍스트 오버레이 평가", "suggestions": ["개선안1", "개선안2"]}"""

_DEEP_PROMPT_CONTENT = """인스타 본문/캡션 스크린샷의 핵심 정보를 추출하고 JSON으로 출력:
{"title": "제목", "content": "본문 전체 또는 핵심 요약", "tags": ["해시태그1"], "word_count": 숫자, "readability": "가독성 평가"}"""

_DEEP_PROMPT_PROFILE = """인스타 프로필 화면을 분석하고 JSON으로 출력:
{"nickname": "계정명", "follower_count": "팔로워 수 텍스트", "note_count": "게시물 수", "bio": "소개", "account_level": "초기/성장/상위", "niche": "주요 카테고리"}"""

_DEEP_PROMPT_COMMENTS = """인스타 댓글 화면을 분석하고 JSON으로 출력:
{"comments": [{"text": "댓글 내용", "sentiment": "positive|negative|neutral"}], "overall_sentiment": "전체 감성", "engagement_quality": "상호작용 품질", "top_concerns": ["핵심 반응1"]}"""

DEEP_PROMPTS = {
    "cover": _DEEP_PROMPT_COVER,
    "content": _DEEP_PROMPT_CONTENT,
    "profile": _DEEP_PROMPT_PROFILE,
    "comments": _DEEP_PROMPT_COMMENTS,
}

LINK_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)


def strip_links(text: str) -> str:
    """텍스트에서 모든 http/https 링크를 제거한다."""
    return LINK_PATTERN.sub("", text).strip()


def _normalize_tags(tags: list[object]) -> str:
    cleaned: list[str] = []
    for tag in tags:
        t = str(tag).strip()
        if not t:
            continue
        cleaned.append(t if t.startswith("#") else f"#{t}")
    return " ".join(cleaned)


def _normalize_extra_slots(raw: object) -> list[str]:
    """모델의 extra_slots를 cover/content/profile/comments 부분집합으로 정규화한다."""
    allowed = {"cover", "content", "profile", "comments"}
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        t = _normalize_slot_type(item)
        if t in allowed and t not in out:
            out.append(t)
    return out


def _normalize_slot_type(raw: object) -> str:
    """모델 slot_type을 정규화해 대소문자/동의어 오판을 줄인다."""
    text = str(raw or "").strip().lower()
    alias_map = {
        "cover": "cover",
        "커버": "cover",
        "썸네일": "cover",
        "content": "content",
        "detail": "content",
        "details": "content",
        "본문": "content",
        "캡션": "content",
        "profile": "profile",
        "home": "profile",
        "프로필": "profile",
        "comments": "comments",
        "comment": "comments",
        "댓글": "comments",
        "댓글창": "comments",
        "other": "other",
        "unknown": "other",
    }
    return alias_map.get(text, "other")


def _prepare_quick_recognize_image(image_bytes: bytes) -> tuple[bytes, str]:
    """
    빠른 인식 전 이미지 압축/리사이즈.
    - 세로 장문 이미지(h>2w): 폭 가독성을 우선 보존
    - 일반 이미지: 긴 변을 max_edge로 제한
    @returns (image_bytes, image_mime)
    """
    max_edge = int(os.getenv("QUICK_RECOGNIZE_MAX_EDGE", "1280"))
    quality = int(os.getenv("QUICK_RECOGNIZE_JPEG_QUALITY", "92"))
    mime_map = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "GIF": "image/gif",
        "MPO": "image/jpeg",
    }
    if max_edge <= 0:
        try:
            im0 = Image.open(BytesIO(image_bytes))
            fmt0 = (im0.format or "PNG").upper()
            return image_bytes, mime_map.get(fmt0, "image/png")
        except Exception:
            return image_bytes, "image/png"
    try:
        im = Image.open(BytesIO(image_bytes))
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")
        elif im.mode != "RGB":
            im = im.convert("RGB")
        w, h = im.size
        fmt = (im.format or "PNG").upper()
        mime = mime_map.get(fmt, "image/png")

        need_resize = False

        if h > 2 * w:
            # === 세로 장문 이미지: 폭 가독성 우선 ===
            LONG_MAX_W = 1024
            LONG_MAX_H = 4096
            target_w = min(w, LONG_MAX_W)
            scale = target_w / w
            target_h = min(int(h * scale), LONG_MAX_H)
            if (target_w, target_h) != (w, h):
                im = im.resize((target_w, target_h), Image.Resampling.LANCZOS)
                need_resize = True
            logger.info("세로 장문 이미지 리사이즈: %dx%d -> %dx%d", w, h, target_w, target_h)
        else:
            # === 일반 이미지: 긴 변 제한 ===
            if max(w, h) > max_edge:
                im.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
                need_resize = True

        if not need_resize and max(w, h) <= max_edge:
            return image_bytes, mime

        buf = BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        logger.warning("빠른 인식용 리사이즈를 건너뛰고 원본 사용: %s", e)
        return image_bytes, "image/png"


async def _vision_call(
    client,
    prompt: str,
    image_bytes: bytes,
    *,
    model: str | None = None,
    max_out_tokens: int | None = None,
    image_mime: str = "image/png",
) -> dict:
    """멀티모달 모델로 이미지를 분석한다."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    resolved_model = model or os.getenv("LLM_MODEL_OMNI", "mimo-v2-omni")
    out_cap = max_out_tokens if max_out_tokens is not None else 2048

    kwargs = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "이 스크린샷을 분석해줘."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{image_mime};base64,{b64}"},
                    },
                ],
            },
        ],
    }
    if _is_mimo_openai_compat():
        kwargs["max_completion_tokens"] = out_cap
    else:
        kwargs["max_tokens"] = out_cap

    # MiMo API 응답 지연 방지를 위한 60초 타임아웃
    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(**kwargs),
            timeout=60,
        )
    except asyncio.TimeoutError:
        return {"error": "비전 인식 시간 초과(60초)", "slot_type": "other"}
    raw = resp.choices[0].message.content or ""
    # Try multiple JSON extraction strategies
    clean = raw.strip()
    # 1) Remove markdown code fence
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    # 2) Direct parse
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    # 3) Use enhanced parser from base_agent (handles thinking tags, raw_decode)
    try:
        from app.agents.base_agent import _parse_json_from_llm_text
        return _parse_json_from_llm_text(raw)
    except Exception:
        pass
    # 4) Last resort: find first { ... } manually
    left = raw.find("{")
    right = raw.rfind("}")
    if left != -1 and right > left:
        try:
            return json.loads(raw[left:right + 1])
        except json.JSONDecodeError:
            pass
    logger.warning("빠른 인식 비전 JSON 파싱 실패, 원본 출력 앞 300자: %s", raw[:300])
    return {"raw_text": raw[:200], "error": "JSON 파싱 실패"}


def _sanitize_video_derived_title(result: dict) -> None:
    """
    영상 빠른 인식 결과에서 장면 설명문이 title에 들어오면 제거하고 content_text로 이동한다.
    """
    t = str(result.get("title", "")).strip()
    if not t:
        return
    bad = False
    if t.startswith("영상"):
        bad = True
    if ("보여" in t or "장면" in t) and len(t) >= 8:
        bad = True
    if any(k in t for k in ("오버레이", "자막 안내", "음성", "화면에", "장면에", "영상에서")):
        bad = True
    if "화면" in t and any(k in t for k in ("한 명", "사람", "여성", "남성")):
        bad = True
    if not bad:
        return
    ct = str(result.get("content_text", "")).strip()
    result["content_text"] = f"{t}\n{ct}".strip() if ct else t
    result["title"] = ""


def _content_text_looks_like_video_scene_caption(text: str) -> bool:
    """
    content_text가 자막 원문이 아닌 장면 설명문인지 판별한다.
    장면 설명문이면 정리 후 프레임/OCR 폴백을 유도한다.
    """
    s = str(text or "").strip()
    if not s:
        return False
    markers = (
        "영상 프레임",
        "영상 장면에서",
        "화면에 한 명",
        "자막 안내가 표시",
        "오버레이 자막",
        "이 영상은",
        "영상은",
    )
    if any(m in s for m in markers):
        return True
    # 한 문장짜리 장면 설명문 패턴
    if s.startswith("영상") and len(s) >= 12 and ("보여" in s or "장면" in s):
        return True
    return False


def _strip_video_scene_caption_lines(text: str) -> str:
    """
    장면 설명형 문장을 제거하고 자막/음성 원문만 남긴다.
    """
    s = str(text or "").strip()
    if not s:
        return ""

    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    if not lines:
        return ""

    kept = [ln for ln in lines if not _content_text_looks_like_video_scene_caption(ln)]
    if kept:
        return "\n".join(kept).strip()
    return ""


def _sanitize_video_meta_narrative_content(result: dict) -> None:
    """
    본문에 장면 설명문이 섞이면 해당 줄만 제거하고 자막/음성 원문을 보존한다.
    """
    ct = str(result.get("content_text", "")).strip()
    if not ct:
        return
    cleaned = _strip_video_scene_caption_lines(ct)
    result["content_text"] = cleaned


def _normalize_quick_recognition_fields(
    result: dict,
    *,
    is_video_frame_fallback: bool = False,
) -> None:
    """
    빠른 인식 필드(slot_type/extra_slots/title/content)를 일관되게 정규화한다.
    @param is_video_frame_fallback - 프레임 폴백 시 본문이 있으면 cover 오판이라도 content_text를 보존한다.
    """
    slot_type = _normalize_slot_type(result.get("slot_type", ""))
    result["slot_type"] = slot_type
    result["extra_slots"] = _normalize_extra_slots(result.get("extra_slots"))
    # Normalize flat likes/publisher into engagement_signal/publisher for frontend
    if "likes" in result and "engagement_signal" not in result:
        likes = int(result.pop("likes", 0) or 0)
        result["engagement_signal"] = {"likes_visible": likes, "collects_visible": 0, "comments_visible": 0, "is_high_engagement": likes > 1000}
    if "name" in result and "publisher" not in result:
        result["publisher"] = {"name": result.pop("name", ""), "follower_count": result.pop("follower_count", "")}
    if is_video_frame_fallback and str(result.get("content_text", "")).strip():
        result["slot_type"] = "content"
        slot_type = "content"
    if slot_type == "cover":
        result["content_text"] = ""
    elif slot_type != "content":
        result["title"] = ""
        result["content_text"] = ""


def _coerce_alt_video_schema_to_quick(result: dict) -> None:
    """
    Gemini 등에서 quick 스키마 대신 scene_keywords/cover_suggestion 중심으로 응답할 때
    quick-recognize 형식으로 최소 필드를 보정한다.
    """
    if not isinstance(result, dict):
        return

    scene_keywords = result.get("scene_keywords")
    cover_suggestion = str(result.get("cover_suggestion", "")).strip()
    risk = result.get("risk_or_limitations")
    subtitle_lines = _parse_subtitle_lines_payload(result)

    has_scene = isinstance(scene_keywords, list) and any(str(x).strip() for x in scene_keywords)
    if not str(result.get("slot_type", "")).strip() and (has_scene or cover_suggestion or subtitle_lines):
        result["slot_type"] = "content"

    if not str(result.get("summary", "")).strip():
        if cover_suggestion:
            result["summary"] = cover_suggestion[:160]
        elif has_scene:
            kws = [str(x).strip() for x in scene_keywords if str(x).strip()][:4]
            if kws:
                result["summary"] = " / ".join(kws)[:160]
        elif isinstance(risk, list) and risk:
            r0 = str(risk[0]).strip()
            if r0:
                result["summary"] = r0[:160]

    if not str(result.get("content_text", "")).strip():
        if subtitle_lines:
            result["content_text"] = "\n".join(subtitle_lines[:20]).strip()
        elif has_scene:
            kws = [str(x).strip() for x in scene_keywords if str(x).strip()][:8]
            if kws:
                result["content_text"] = "\n".join(f"[키워드] {k}" for k in kws)


def _coerce_video_quick_slot_when_body_present(result: dict) -> None:
    """본문이 있는데 slot이 cover/other면 content로 보정한다."""
    body = str(result.get("content_text", "")).strip()
    if not body:
        return
    st = _normalize_slot_type(result.get("slot_type", ""))
    if st in ("profile", "comments"):
        return
    if st != "content":
        result["slot_type"] = "content"


def _quick_payload_is_empty(result: dict) -> bool:
    scene_keywords = result.get("scene_keywords")
    has_scene = isinstance(scene_keywords, list) and any(str(x).strip() for x in scene_keywords)
    return (
        not str(result.get("title", "")).strip()
        and not str(result.get("content_text", "")).strip()
        and not str(result.get("summary", "")).strip()
        and not has_scene
    )


def _video_subtitle_payload_insufficient(result: dict) -> bool:
    """
    영상 빠른 인식에서 자막 본문이 부족하면 프레임 분석 또는 OCR이 필요하다.
    """
    ct = str(result.get("content_text", "")).strip()
    if ct and not _strip_video_scene_caption_lines(ct):
        return True
    return _quick_payload_is_empty(result)


def _quick_video_mimo_part(video_url: str) -> dict:
    """
    영상 빠른 인식 전용 기본값: fps를 약간 높이고 해상도 기본값을 max로 둔다.
    QUICK_RECOGNIZE_VIDEO_FPS / QUICK_RECOGNIZE_VIDEO_MEDIA_RESOLUTION로 오버라이드 가능.
    """
    fps = _env_float("QUICK_RECOGNIZE_VIDEO_FPS", 4.0, min_v=0.5, max_v=10.0)
    res_raw = (os.getenv("QUICK_RECOGNIZE_VIDEO_MEDIA_RESOLUTION") or "max").strip().lower()
    res = res_raw if res_raw in ("default", "max") else "max"
    return build_mimo_video_url_content_part(video_url, fps=fps, media_resolution=res)


def _parse_subtitle_lines_payload(raw: object) -> list[str]:
    """전사 JSON에서 subtitle_lines를 추출한다(lines/subtitles 키도 허용)."""
    if not isinstance(raw, dict):
        return []
    for key in ("subtitle_lines", "lines", "subtitles"):
        val = raw.get(key)
        if isinstance(val, list):
            out: list[str] = []
            for x in val:
                s = str(x).strip()
                if not s:
                    continue
                for ln in s.split("\n"):
                    t = ln.strip()
                    if t:
                        out.append(t)
            return out
        if isinstance(val, str) and val.strip():
            return [ln.strip() for ln in val.replace("；", "\n").split("\n") if ln.strip()]
    return []


def _merge_subtitle_transcript_into_result(result: dict, lines: list[str]) -> None:
    """
    2차 전사 결과를 content_text에 병합한다. 더 완전한 경우 기존 값을 덮어쓴다.
    """
    cleaned = [str(x).strip() for x in lines if x and str(x).strip()]
    if not cleaned:
        return
    transcript = "\n".join(cleaned)
    prev = str(result.get("content_text", "")).strip()
    n_lines = len(cleaned)
    prev_lines = prev.count("\n") + (1 if prev else 0)
    much_richer = (
        len(transcript) > int(len(prev) * 1.05)
        or n_lines >= max(3, prev_lines + 1)
        or (n_lines >= 2 and prev_lines <= 1)
    )
    if not prev or much_richer:
        result["content_text"] = transcript
        logger.info(
            "영상 빠른 인식 전사 병합: lines=%s prev_len=%s new_len=%s",
            n_lines,
            len(prev),
            len(transcript),
        )


def _merge_stt_into_video_result(result: dict, stt: str) -> None:
    """Whisper 음성 전사 결과를 content_text에 병합한다(화면 자막과 상호보완)."""
    text = (stt or "").strip()
    if not text:
        return
    prev_raw = str(result.get("content_text", "")).strip()
    prev = _strip_video_scene_caption_lines(prev_raw)
    if not prev:
        result["content_text"] = text
        return
    if text in prev or prev in text:
        if len(text) > len(prev):
            result["content_text"] = text
        return
    result["content_text"] = f"{prev}\n\n{text}".strip()


async def _video_url_quick_call(client, video_url: str) -> dict:
    """
    MiMo video_url 기반 영상 이해 호출을 수행하고 빠른 인식과 동일 구조 JSON을 반환한다.
    메시지 포맷은 공식 문서(OpenAI 호환 video understanding)를 따른다.
    """
    resolved_model = os.getenv("LLM_MODEL_OMNI", "mimo-v2-omni")
    out_cap = _env_int("QUICK_RECOGNIZE_VIDEO_MAX_COMPLETION_TOKENS", 4096, min_v=256, max_v=8192)
    video_part = _quick_video_mimo_part(video_url)
    kwargs = {
        "model": resolved_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return ONLY valid JSON; no markdown fences. "
                    "Field content_text must be VERBATIM subtitle/caption/on-screen text lines "
                    "(and clear voiceover transcription) in time order — NOT a prose description "
                    "of scenes (never start with phrases like 'the video shows' or scene summaries)."
                ),
            },
            {
                "role": "user",
                "content": [
                    video_part,
                    {"type": "text", "text": _VIDEO_QUICK_PROMPT},
                ],
            },
        ],
        "temperature": min(float(os.getenv("LLM_TEMPERATURE", "0.3")), 0.15),
    }
    if _is_mimo_openai_compat():
        kwargs["max_completion_tokens"] = out_cap
    else:
        kwargs["max_tokens"] = out_cap

    resp = await client.chat.completions.create(**kwargs)
    raw = (resp.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        parsed = _parse_json_from_llm_text(raw)
        if isinstance(parsed, dict):
            return parsed
        return {"raw_text": raw, "error": "JSON 파싱 실패"}


async def _video_url_subtitle_transcript_call(client, video_url: str) -> list[str]:
    """
    2차 호출: 동일 video_url에 대해 subtitle_lines만 요청해 전사 누락을 줄인다.
    """
    resolved_model = os.getenv("LLM_MODEL_OMNI", "mimo-v2-omni")
    out_cap = _env_int(
        "QUICK_RECOGNIZE_VIDEO_TRANSCRIPT_MAX_COMPLETION_TOKENS",
        8192,
        min_v=512,
        max_v=8192,
    )
    video_part = _quick_video_mimo_part(video_url)
    kwargs = {
        "model": resolved_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return ONLY valid JSON with a single key subtitle_lines (array of strings). "
                    "Each string is one caption or spoken line in time order. No markdown fences."
                ),
            },
            {
                "role": "user",
                "content": [
                    video_part,
                    {"type": "text", "text": _VIDEO_SUBTITLE_TRANSCRIPT_PROMPT},
                ],
            },
        ],
        "temperature": min(float(os.getenv("LLM_TEMPERATURE", "0.3")), 0.1),
    }
    if _is_mimo_openai_compat():
        kwargs["max_completion_tokens"] = out_cap
    else:
        kwargs["max_tokens"] = out_cap

    resp = await client.chat.completions.create(**kwargs)
    raw = (resp.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = _parse_json_from_llm_text(raw)
        if not isinstance(parsed, dict):
            return []
    return _parse_subtitle_lines_payload(parsed)


def _video_title_body_same_short_hook(result: dict) -> bool:
    """
    title/content가 동일한 짧은 훅 문구인지 판단해 OCR 보강 트리거로 사용한다.
    """
    tt = str(result.get("title", "")).strip()
    ct = str(result.get("content_text", "")).strip()
    return bool(tt and ct and tt == ct and len(ct) <= 40)


def _ocr_supplement_already_sufficient(title_text: str, content_text: str) -> bool:
    """
    빠른 인식 결과가 충분히 완전한지 판단해 첫 프레임 OCR 보강을 생략할지 결정한다.
    """
    ct = (content_text or "").strip()
    tt = (title_text or "").strip()
    if not ct or not tt:
        return False
    if tt == ct and len(ct) <= 40:
        return False
    if len(ct) >= 52:
        return True
    if tt != ct and len(ct) >= 32:
        return True
    return False


async def _ocr_supplement_quick_result(client, image_bytes: bytes, result: dict, ocr_cap: int) -> None:
    """title/content가 비어 있거나 지나치게 짧을 때 OCR로 보강한다."""
    content_text = str(result.get("content_text", "")).strip()
    title_text = str(result.get("title", "")).strip()
    if _ocr_supplement_already_sufficient(title_text, content_text):
        return
    try:
        from app.analysis.ocr_processor import OCRProcessor

        ocr = OCRProcessor()
        ocr_result = await ocr.extract_text(image_bytes, client, max_tokens_override=ocr_cap)
        ocr_title = str(ocr_result.get("title", "")).strip()
        ocr_content = str(ocr_result.get("content", "")).strip()
        ocr_tags = ocr_result.get("tags", [])
        if not ocr_content and isinstance(ocr_tags, list):
            ocr_content = _normalize_tags(ocr_tags)
        if not title_text and ocr_title:
            result["title"] = ocr_title
        if not content_text and ocr_content:
            result["content_text"] = ocr_content
        elif content_text and ocr_content:
            # 비전이 짧은 문구만 추출한 경우 OCR 결과가 더 긴 본문일 수 있다.
            if len(ocr_content) > len(content_text) + 12 or ocr_content.count("\n") > content_text.count(
                "\n",
            ):
                result["content_text"] = ocr_content
        if not str(result.get("summary", "")).strip() and ocr_content:
            result["summary"] = ocr_content[:80]
    except Exception as ocr_error:
        logger.warning("quick-recognize OCR fallback failed: %s", ocr_error)


@router.post("/screenshot/quick-recognize")
async def quick_recognize(
    file: UploadFile = File(...),
    slot_hint: str = Form(""),
):
    """
    단일 스크린샷을 업로드하면 즉시 AI가 인식한다.
    @param file - 이미지 파일
    @param slot_hint - 선택 힌트: cover/content/profile/comments
    @returns slot_type/category/summary 포함 결과
    """
    if file.content_type and file.content_type not in ALLOWED_IMAGE_MIME:
        raise HTTPException(400, f"지원하지 않는 이미지 형식: {file.content_type}")

    image_bytes_raw = await file.read()
    if len(image_bytes_raw) > MAX_IMAGE_SIZE:
        raise HTTPException(400, "이미지는 10MB를 초과할 수 없습니다")

    image_bytes, image_mime = _prepare_quick_recognize_image(image_bytes_raw)

    client = _get_client()
    prompt = _QUICK_PROMPT
    if slot_hint and slot_hint in SLOT_LABELS:
        prompt += f"\n추가 힌트: 사용자가 이 이미지를 '{SLOT_LABELS[slot_hint]}'로 지정했다."

    # 빠른 인식은 _vision_call + 기본 LLM_MODEL_OMNI(멀티모달) 경로를 사용한다.
    quick_max_out = _quick_image_max_out_tokens()
    ocr_cap = _quick_ocr_max_tokens()

    try:
        result = await _vision_call(
            client,
            prompt,
            image_bytes,
            max_out_tokens=quick_max_out,
            image_mime=image_mime,
        )
        if not isinstance(result, dict):
            result = {}
        if result.get("error"):
            logger.warning("quick-recognize 비전 단계 실패: %s", result.get("error"))
            return {
                "success": False,
                "error": str(result.get("error", "비전 인식 실패")),
                "media_source": "image",
                "slot_type": slot_hint or str(result.get("slot_type", "unknown")),
                "extra_slots": [],
                "category": "",
                "summary": "",
                "title": "",
                "content_text": "",
                "confidence": 0.0,
            }
        _normalize_quick_recognition_fields(result)
        slot_type = str(result.get("slot_type", ""))
        logger.info(
            "quick-recognize 결과: slot_type=%s extra_slots=%s title=%s category=%s keys=%s",
            slot_type,
            result.get("extra_slots"),
            str(result.get("title", ""))[:50],
            result.get("category", ""),
            list(result.keys()),
        )

        await _ocr_supplement_quick_result(client, image_bytes_raw, result, ocr_cap)
        if _quick_payload_is_empty(result):
            return {
                "success": False,
                "error": "유효한 제목/본문/요약을 인식하지 못했습니다. 더 선명한 스크린샷을 사용하거나 직접 입력해 주세요.",
                "media_source": "image",
                "slot_type": str(result.get("slot_type", slot_hint or "unknown")),
                "extra_slots": result.get("extra_slots") or [],
                "category": str(result.get("category", "")),
                "summary": str(result.get("summary", "")),
                "title": str(result.get("title", "")),
                "content_text": str(result.get("content_text", "")),
                "confidence": float(result.get("confidence") or 0.0),
            }
        out = {"success": True, **result}
        out["media_source"] = "image"
        return out
    except Exception as e:
        logger.error("quick-recognize 실패: %s", e)
        return {
            "success": False,
            "error": str(e),
            "media_source": "image",
            "slot_type": slot_hint or "unknown",
            "extra_slots": [],
            "category": "",
            "summary": "",
            "title": "",
            "content_text": "",
            "confidence": 0.0,
        }


@router.post("/screenshot/quick-recognize-video")
async def quick_recognize_video(request: Request, file: UploadFile = File(...)):
    """
    영상 업로드 후 AI 빠른 인식을 수행한다. 반환 필드는 /screenshot/quick-recognize 와 동일하다.
    MiMo video_url 전체 분석을 우선 시도하고, 실패/미지원 형식이면 대표 프레임 분석으로 폴백한다.
    @param file - mp4 / webm / quicktime
    """
    if file.content_type and file.content_type not in ALLOWED_VIDEO_MIME:
        raise HTTPException(400, f"지원하지 않는 영상 형식: {file.content_type}")

    video_bytes = await file.read()
    if len(video_bytes) > MAX_VIDEO_SIZE:
        raise HTTPException(400, f"영상은 {MAX_VIDEO_SIZE // (1024 * 1024)}MB를 초과할 수 없습니다")

    mime = (file.content_type or "video/mp4").strip()
    container_ext = MIME_TO_EXT.get(mime, ".mp4")
    client = _get_client()
    quick_max_out = _quick_image_max_out_tokens()
    ocr_cap = _quick_ocr_max_tokens()
    provider = _llm_provider()

    stt_task = asyncio.create_task(transcribe_video_with_whisper(video_bytes, container_ext))

    result: dict = {}
    video_url_mimo: Optional[str] = None
    gemini_full_video_error = ""
    url_diag = get_public_base_url_diagnostics(request)
    try_mimo_video_url = mime in MIMO_VIDEO_MIME and bool(url_diag.get("ok"))
    if provider == "gemini":
        try:
            from app.analysis.video_analyzer import VideoAnalyzer

            analyzer = VideoAnalyzer()
            result = await analyzer.infer_json_from_video_bytes(
                video_bytes,
                mime_type=mime,
                prompt_text=_VIDEO_QUICK_PROMPT,
                system_prompt=(
                    "Return ONLY valid JSON; no markdown fences. "
                    "Field content_text must be VERBATIM subtitle/caption/on-screen text lines "
                    "(and clear voiceover transcription) in time order."
                ),
                max_output_tokens=_env_int(
                    "QUICK_RECOGNIZE_VIDEO_MAX_COMPLETION_TOKENS",
                    4096,
                    min_v=256,
                    max_v=8192,
                ),
                temperature=min(float(os.getenv("LLM_TEMPERATURE", "0.3")), 0.15),
            )
            _coerce_alt_video_schema_to_quick(result)
            logger.info("영상 빠른 인식 Gemini full-video 완료 keys=%s", list(result.keys()))
        except Exception as e:
            logger.warning("영상 빠른 인식 Gemini full-video 실패, 프레임 폴백 시도: %s", e)
            gemini_full_video_error = str(e)
            result = {}

    if not try_mimo_video_url and mime in MIMO_VIDEO_MIME:
        logger.info(
            "video quick-recognize: MiMo video_url 건너뜀. reason=%s, source=%s, base=%s; "
            "운영 환경에서는 MIMO_VIDEO_PUBLIC_BASE_URL 또는 X-Forwarded-* 헤더를 설정하세요.",
            url_diag.get("reason"),
            url_diag.get("source"),
            url_diag.get("base_url"),
        )
    if provider != "gemini" and try_mimo_video_url:
        try:
            video_url_mimo = _store_temp_video_and_build_url(request, video_bytes, mime)
            raw = await _video_url_quick_call(client, video_url_mimo)
            if isinstance(raw, dict):
                result = raw
            logger.info("영상 빠른 인식 video_url 완료 keys=%s", list(result.keys()))
        except Exception as e:
            logger.warning("영상 빠른 인식 video_url 실패, 프레임 폴백 시도: %s", e)
            result = {}

    if not isinstance(result, dict):
        result = {}
    _coerce_alt_video_schema_to_quick(result)

    _normalize_quick_recognition_fields(result)
    _sanitize_video_derived_title(result)
    _sanitize_video_meta_narrative_content(result)

    if video_url_mimo:
        try:
            lines = await _video_url_subtitle_transcript_call(client, video_url_mimo)
            _merge_subtitle_transcript_into_result(result, lines)
        except Exception as e:
            logger.warning("영상 빠른 인식 전사(2차) 실패: %s", e)
        _sanitize_video_derived_title(result)
        _sanitize_video_meta_narrative_content(result)

    frame_jpeg: Optional[bytes] = None
    if _video_subtitle_payload_insufficient(result):
        frame_jpeg = _extract_first_video_frame(video_bytes, container_ext)
        if frame_jpeg:
            try:
                img_bytes, img_mime = _prepare_quick_recognize_image(frame_jpeg)
                fp = _QUICK_PROMPT + (
                    "\n## 영상 대표 프레임 전용 규칙(상위 우선)\n"
                    "입력은 영상 일시정지 프레임이다. 화면 중앙 재생 버튼(UI 장식)은 무시한다.\n"
                    "content_text에는 화면에 보이는 자막/꽃자막/스티커 원문만 작성한다. 여러 줄은 줄바꿈으로 분리한다.\n"
                    "장면 설명문(예: '영상은 ~를 보여준다')은 content_text에 작성하지 않는다. 필요 시 summary 1문장으로 제한한다.\n"
                    "title은 게시 화면 제목란이 보일 때만 채우고, 그렇지 않으면 \"\"로 둔다.\n"
                    "자막/꽃자막이 보이면 slot_type은 content로 판정한다. 텍스트가 없으면 content_text는 \"\"로 둔다.\n"
                    "전체 영상의 음성 전사는 video_url 이해/Whisper 결과로 보완하며, 이 프레임에서는 가시 텍스트 OCR에 집중한다."
                )
                fr = await _vision_call(
                    client, fp, img_bytes, max_out_tokens=quick_max_out, image_mime=img_mime
                )
                if isinstance(fr, dict) and not fr.get("error"):
                    result = fr
                    _normalize_quick_recognition_fields(result, is_video_frame_fallback=True)
                    _sanitize_video_derived_title(result)
                    _sanitize_video_meta_narrative_content(result)
                    logger.info("영상 빠른 인식 프레임 비전 완료 slot_type=%s", result.get("slot_type"))
                elif isinstance(fr, dict) and fr.get("error"):
                    logger.warning("영상 빠른 인식 프레임 비전 실패: %s", fr.get("error"))
            except Exception as e:
                logger.warning("영상 빠른 인식 프레임 비전 실패: %s", e)

    if frame_jpeg is None and (
        not str(result.get("title", "")).strip()
        or not str(result.get("content_text", "")).strip()
        or _content_text_looks_like_video_scene_caption(str(result.get("content_text", "")).strip())
        or _video_title_body_same_short_hook(result)
    ):
        frame_jpeg = _extract_first_video_frame(video_bytes, container_ext)
    if frame_jpeg:
        await _ocr_supplement_quick_result(client, frame_jpeg, result, ocr_cap)

    stt_text = ""
    try:
        _stt_t = float(os.getenv("VIDEO_STT_TIMEOUT_SEC", "240"))
    except ValueError:
        _stt_t = 240.0
    stt_timeout = max(30.0, min(_stt_t, 600.0))
    try:
        stt_text = await asyncio.wait_for(stt_task, timeout=stt_timeout)
    except asyncio.TimeoutError:
        logger.warning("VIDEO_STT: Whisper 대기 타임아웃(%.0fs)", stt_timeout)
        stt_task.cancel()
        try:
            await stt_task
        except asyncio.CancelledError:
            pass
    except Exception as e:
        logger.warning("VIDEO_STT: 병합 전 예외 %s", e)

    _prev_ct_len = len(str(result.get("content_text", "") or ""))
    _merge_stt_into_video_result(result, stt_text)
    _after_ct_len = len(str(result.get("content_text", "") or ""))
    logger.info(
        "VIDEO_STT: 음성 전사 병합 prev_content_len=%s stt_len=%s merged_content_len=%s",
        _prev_ct_len,
        len((stt_text or "").strip()),
        _after_ct_len,
    )
    _stt_env_on = os.getenv("VIDEO_STT_ENABLED", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if not (stt_text or "").strip() and _stt_env_on:
        logger.warning(
            "VIDEO_STT: 음성 전사 결과가 비어 있어 본문은 영상 모델/OCR 결과 위주입니다. "
            "상단 VIDEO_STT 로그(ffmpeg/API/네트워크 설정)를 확인하세요.",
        )

    _sanitize_video_meta_narrative_content(result)

    if _quick_payload_is_empty(result):
        detail_tail = ""
        if gemini_full_video_error:
            detail_tail = f" (Gemini full-video: {gemini_full_video_error[:160]})"
        return {
            "success": False,
            "error": f"영상에서 유효한 텍스트/주제를 인식하지 못했습니다. 다른 구간을 사용하거나 수동 입력하세요.{detail_tail}",
            "media_source": "video",
            "slot_type": "other",
            "extra_slots": [],
            "category": "",
            "summary": "",
            "title": "",
            "content_text": "",
            "confidence": 0.0,
        }

    _sanitize_video_derived_title(result)
    _sanitize_video_meta_narrative_content(result)
    _coerce_video_quick_slot_when_body_present(result)

    logger.info(
        "영상 빠른 인식 최종 결과: slot_type=%s title=%s category=%s",
        result.get("slot_type"),
        str(result.get("title", ""))[:50],
        result.get("category", ""),
    )
    out = {"success": True, **result}
    out["media_source"] = "video"
    return out


@router.post("/screenshot/deep-analyze")
async def deep_analyze(
    scenario: str = Form(...),
    cover: Optional[UploadFile] = File(None),
    content_img: Optional[UploadFile] = File(None),
    profile: Optional[UploadFile] = File(None),
    comments: Optional[UploadFile] = File(None),
    video: Optional[UploadFile] = File(None),
    extra_text: str = Form(""),
):
    """
    전체 심층 분석: 슬롯별 이미지를 업로드하면 다차원 분석을 수행한다.
    @param scenario - 사용 시나리오: pre_publish / post_publish
    @param cover - 커버 스크린샷
    @param content_img - 본문 스크린샷
    @param profile - 프로필 스크린샷
    @param comments - 댓글 스크린샷
    @param video - 영상 파일(선택)
    @param extra_text - 추가 텍스트(링크 자동 제거)
    """
    if scenario not in ("pre_publish", "post_publish"):
        raise HTTPException(400, "scenario는 pre_publish 또는 post_publish여야 합니다")

    cleaned_text = strip_links(extra_text)

    slots: dict[str, bytes] = {}
    for name, upload in [("cover", cover), ("content", content_img), ("profile", profile), ("comments", comments)]:
        if upload:
            if upload.content_type and upload.content_type not in ALLOWED_IMAGE_MIME:
                raise HTTPException(400, f"{SLOT_LABELS[name]} 형식을 지원하지 않습니다: {upload.content_type}")
            data = await upload.read()
            if len(data) > MAX_IMAGE_SIZE:
                raise HTTPException(400, f"{SLOT_LABELS[name]}는 10MB를 초과할 수 없습니다")
            slots[name] = data

    if not slots:
        raise HTTPException(400, "스크린샷을 최소 1장 이상 업로드하세요")

    video_info = None
    if video:
        if video.content_type and video.content_type not in ALLOWED_VIDEO_MIME:
            raise HTTPException(400, f"지원하지 않는 영상 형식: {video.content_type}")
        video_data = await video.read()
        if len(video_data) > MAX_VIDEO_SIZE:
            raise HTTPException(400, f"영상은 {MAX_VIDEO_SIZE // (1024 * 1024)}MB를 초과할 수 없습니다")
        video_info = {
            "filename": video.filename,
            "size_mb": round(len(video_data) / (1024 * 1024), 1),
            "content_type": video.content_type,
        }

    client = _get_client()
    results: dict = {
        "scenario": scenario,
        "slot_count": len(slots),
        "extra_text": cleaned_text,
        "video_info": video_info,
        "analyses": {},
    }

    import asyncio

    tasks: dict[str, object] = {}
    for slot_name, img_bytes in slots.items():
        prompt = DEEP_PROMPTS.get(slot_name, _QUICK_PROMPT)
        if scenario == "post_publish" and slot_name == "comments":
            prompt += "\n댓글의 감성(긍정/중립/부정)과 전환 가능 반응(문의/저장/공유)을 중점 분석하라."
        tasks[slot_name] = _vision_call(client, prompt, img_bytes)

    task_results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for slot_name, task_result in zip(tasks.keys(), task_results):
        if isinstance(task_result, Exception):
            logger.error("deep-analyze %s 실패: %s", slot_name, task_result)
            results["analyses"][slot_name] = {"error": str(task_result)}
        else:
            results["analyses"][slot_name] = task_result

    results["overall"] = _build_overall(results["analyses"], scenario)
    return results


def _build_overall(analyses: dict, scenario: str) -> dict:
    """슬롯별 분석 결과를 종합해 전체 완성도를 계산한다."""
    has_cover = "cover" in analyses and "error" not in analyses["cover"]
    has_content = "content" in analyses and "error" not in analyses["content"]
    has_profile = "profile" in analyses and "error" not in analyses["profile"]
    has_comments = "comments" in analyses and "error" not in analyses["comments"]

    completeness = sum([has_cover, has_content, has_profile, has_comments]) / 4 * 100

    tips: list[str] = []
    if not has_cover:
        tips.append("커버 이미지가 없어 썸네일 흡인력을 평가할 수 없습니다.")
    if not has_content:
        tips.append("본문/캡션 스크린샷이 없어 카피 품질을 평가할 수 없습니다.")
    if scenario == "post_publish" and not has_comments:
        tips.append("게시 후 분석에서는 댓글 스크린샷을 업로드하면 반응 품질 분석 정확도가 올라갑니다.")
    if not has_profile:
        tips.append("프로필 스크린샷을 추가하면 계정 레벨/포지셔닝 분석이 더 정확해집니다.")

    return {
        "completeness": round(completeness),
        "scenario": "게시 전 분석" if scenario == "pre_publish" else "게시 후 분석",
        "tips": tips,
        "slots_analyzed": list(analyses.keys()),
    }


@router.post("/text/strip-links")
async def api_strip_links(text: str = Form("")):
    """
    텍스트의 외부 링크를 제거한다.
    @param text - 원문
    """
    return {"original": text, "cleaned": strip_links(text)}
