"""
OCR 처리 모듈
멀티모달 모델로 스크린샷의 제목/본문/태그를 추출한다.
"""

from __future__ import annotations

import json
import logging
import os
import re

from app.agents.base_agent import (
    _bytes_to_image_data_url,
    _is_mimo_openai_compat,
    _parse_json_from_llm_text,
)

logger = logging.getLogger("insta-advisor.ocr")


def _salvage_ocr_json_fragment(text: str) -> dict | None:
    """
    max_tokens로 JSON이 잘린 경우 title/content/tags를 가능한 만큼 복구.
    """
    title = ""
    content = ""
    tags: list[str] = []

    tm = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if tm:
        title = tm.group(1)

    cm = re.search(r'"content"\s*:\s*"', text)
    if cm:
        rest = text[cm.end() :]
        parts: list[str] = []
        i = 0
        esc = False
        while i < len(rest):
            c = rest[i]
            if esc:
                parts.append(c)
                esc = False
                i += 1
                continue
            if c == "\\":
                esc = True
                i += 1
                continue
            if c == '"':
                break
            parts.append(c)
            i += 1
        content = "".join(parts)

    tags_m = re.search(r'"tags"\s*:\s*\[', text)
    if tags_m:
        slice_start = tags_m.end()
        bracket = text[slice_start : slice_start + 800]
        for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', bracket):
            tags.append(m.group(1))

    if title.strip() or content.strip() or tags:
        return {"title": title.strip(), "content": content.strip(), "tags": tags}
    return None


class OCRProcessor:
    """스크린샷 텍스트 핵심 필드 추출기."""

    async def extract_text(
        self,
        image_bytes: bytes,
        client=None,
        *,
        max_tokens_override: int | None = None,
    ) -> dict:
        if client is None:
            return self._fallback_result()

        data_url = _bytes_to_image_data_url(image_bytes)
        ocr_model = os.getenv("LLM_MODEL_OMNI", "gpt-4o")

        try:
            msg_body: list | str = [
                {
                    "type": "text",
                    "text": "스크린샷 의미를 기준으로 제목/본문 요점/태그를 추출해줘. 불필요한 UI 텍스트는 제외해줘.",
                },
                {"type": "image_url", "image_url": {"url": data_url}},
            ]
            kwargs = {
                "model": ocr_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "너는 인스타 게시물 스크린샷 필드 추출기다. "
                            "화면 의미를 먼저 이해하고 핵심 필드만 추출해라. "
                            "보이지 않으면 비워두고 추측하지 마라. "
                            "content에는 실제 확인 가능한 텍스트 요점만 적고, 길게 설명하지 마라. "
                            "tags가 없으면 []로 반환해라. "
                            'JSON만 출력: {"title": "...", "content": "...", "tags": []}'
                        ),
                    },
                    {"role": "user", "content": msg_body},
                ],
            }
            env_cap = int(os.getenv("LLM_OCR_MAX_TOKENS", "2048"))
            if max_tokens_override is not None:
                env_cap = min(max(env_cap, max_tokens_override), 8192)

            if _is_mimo_openai_compat():
                kwargs["max_completion_tokens"] = min(env_cap, 8192)
            else:
                kwargs["max_tokens"] = min(env_cap, 8192)

            response = await client.chat.completions.create(**kwargs)
            raw = response.choices[0].message.content or ""
            clean = raw.strip()
            if not clean:
                logger.debug("OCR 모델이 빈 응답 반환")
                return self._fallback_result()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            try:
                parsed = json.loads(clean)
            except json.JSONDecodeError:
                try:
                    parsed = _parse_json_from_llm_text(clean)
                except json.JSONDecodeError:
                    salvaged = _salvage_ocr_json_fragment(clean)
                    if salvaged:
                        logger.info(
                            "OCR JSON 일부 복구 성공: title_len=%s content_len=%s",
                            len(salvaged.get("title", "")),
                            len(salvaged.get("content", "")),
                        )
                        return salvaged
                    logger.warning("OCR 결과 JSON 파싱 실패: %r", clean[:240])
                    return self._fallback_result()

            if not isinstance(parsed, dict):
                return self._fallback_result()
            return parsed

        except Exception as e:
            logger.warning("OCR 추출 실패: %s", e)
            return self._fallback_result()

    def _fallback_result(self) -> dict:
        return {"title": "", "content": "", "tags": []}
