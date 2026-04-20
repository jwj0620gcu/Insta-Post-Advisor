"""
Video analysis module.
OpenAI-compatible 멀티모달 모델을 사용해 영상의 핵심 장면/훅/리스크를 추출한다.
"""
from __future__ import annotations

import json
import logging
import os
import asyncio
from typing import Optional

import httpx

from app.agents.base_agent import (
    _get_client,
    _is_mimo_openai_compat,
    _llm_provider,
    _parse_json_from_llm_text,
)
from app.analysis.mimo_video import build_mimo_video_url_content_part

logger = logging.getLogger("insta-advisor.video_analyzer")


class VideoAnalyzer:
    """Analyze video semantics for Instagram diagnosis."""

    @staticmethod
    def _gemini_key() -> str:
        return (os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()

    @staticmethod
    def _is_gemini_provider() -> bool:
        return _llm_provider() == "gemini"

    async def _gemini_upload_video(self, client: httpx.AsyncClient, video_bytes: bytes, mime_type: str) -> tuple[str, Optional[str]]:
        """
        Gemini Files API로 비디오를 업로드하고 (file_uri, file_name)을 반환한다.
        """
        api_key = self._gemini_key()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다")

        start_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={api_key}"
        start_headers = {
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(len(video_bytes)),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json",
        }
        start_body = {"file": {"display_name": "insta-advisor_video_input"}}
        start_resp = await client.post(start_url, headers=start_headers, json=start_body)
        if start_resp.status_code >= 400:
            try:
                payload = start_resp.json() if start_resp.text else {}
            except Exception:
                payload = {"raw": (start_resp.text or "")[:500]}
            msg = self._extract_error_message_from_payload(payload)
            raise RuntimeError(msg or f"Gemini upload start 실패 ({start_resp.status_code})")
        upload_url = start_resp.headers.get("x-goog-upload-url") or start_resp.headers.get("X-Goog-Upload-URL")
        if not upload_url:
            raise RuntimeError("Gemini Files API resumable upload URL을 받지 못했습니다")

        upload_headers = {
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
            "Content-Type": mime_type,
        }
        upload_resp = await client.post(upload_url, headers=upload_headers, content=video_bytes)
        if upload_resp.status_code >= 400:
            try:
                payload = upload_resp.json() if upload_resp.text else {}
            except Exception:
                payload = {"raw": (upload_resp.text or "")[:500]}
            msg = self._extract_error_message_from_payload(payload)
            raise RuntimeError(msg or f"Gemini upload finalize 실패 ({upload_resp.status_code})")
        payload = upload_resp.json() if upload_resp.text else {}
        file_info = payload.get("file", {}) if isinstance(payload, dict) else {}
        file_uri = str(file_info.get("uri", "")).strip()
        file_name = str(file_info.get("name", "")).strip() or None
        if not file_uri:
            raise RuntimeError("Gemini Files API 업로드 응답에서 file.uri를 찾지 못했습니다")
        return file_uri, file_name

    async def _gemini_wait_file_active(self, client: httpx.AsyncClient, file_name: Optional[str]) -> None:
        """
        Gemini 비디오 파일 처리 상태를 ACTIVE까지 대기한다.
        """
        if not file_name:
            return
        api_key = self._gemini_key()
        if not api_key:
            return
        max_wait = max(5.0, float(os.getenv("GEMINI_VIDEO_FILE_MAX_WAIT_SEC", "90")))
        poll_sec = max(0.5, float(os.getenv("GEMINI_VIDEO_FILE_POLL_SEC", "2.0")))
        url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={api_key}"
        waited = 0.0
        while waited <= max_wait:
            payload = await self._request_json_or_raise(client, "GET", url)
            file_info = payload.get("file", payload) if isinstance(payload, dict) else {}
            state = str((file_info or {}).get("state", "")).upper()
            if state in ("ACTIVE", "READY"):
                return
            if state in ("FAILED", "ERROR"):
                msg = str((file_info or {}).get("error", "")) or "Gemini 파일 처리 실패"
                raise RuntimeError(msg)
            await asyncio.sleep(poll_sec)
            waited += poll_sec
        raise RuntimeError(f"Gemini 비디오 파일 처리 대기 시간 초과 ({int(max_wait)}s)")

    async def _gemini_delete_file(self, client: httpx.AsyncClient, file_name: Optional[str]) -> None:
        """
        업로드한 임시 파일 정리(실패해도 무시).
        """
        if not file_name:
            return
        api_key = self._gemini_key()
        if not api_key:
            return
        # file_name 예: files/abc123
        url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={api_key}"
        try:
            await client.delete(url)
        except Exception:
            logger.debug("Gemini 임시 파일 삭제 실패: %s", file_name)

    async def _gemini_generate_text_from_file(
        self,
        client: httpx.AsyncClient,
        *,
        file_uri: str,
        mime_type: str,
        prompt_text: str,
        system_prompt: Optional[str],
        model: str,
        max_output_tokens: int,
        temperature: float,
    ) -> str:
        """
        Gemini generateContent 호출로 텍스트 응답을 얻는다.
        """
        api_key = self._gemini_key()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다")
        model_name = (model or "gemini-2.5-flash-lite").strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        body: dict = {
            "contents": [
                {
                    "parts": [
                        {"file_data": {"mime_type": mime_type, "file_uri": file_uri}},
                        {"text": prompt_text},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max(256, min(int(max_output_tokens), 8192)),
            },
        }
        if system_prompt and system_prompt.strip():
            body["system_instruction"] = {"parts": [{"text": system_prompt.strip()}]}

        payload = await self._request_json_or_raise(client, "POST", url, json=body)
        candidates = payload.get("candidates") if isinstance(payload, dict) else None
        if not isinstance(candidates, list) or not candidates:
            raise RuntimeError("Gemini 응답에 candidates가 없습니다")

        texts: list[str] = []
        for cand in candidates:
            content = cand.get("content", {}) if isinstance(cand, dict) else {}
            parts = content.get("parts", []) if isinstance(content, dict) else []
            if not isinstance(parts, list):
                continue
            for p in parts:
                if isinstance(p, dict) and isinstance(p.get("text"), str):
                    texts.append(p["text"])
        out = "\n".join(t for t in texts if t and t.strip()).strip()
        if not out:
            raise RuntimeError("Gemini 응답 텍스트가 비어 있습니다")
        return out

    async def infer_json_from_video_bytes(
        self,
        video_bytes: bytes,
        *,
        mime_type: str,
        prompt_text: str,
        system_prompt: Optional[str] = None,
        model_override: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> dict:
        """
        Gemini provider일 때 비디오 바이트로 JSON 응답을 추출한다.
        """
        if not self._is_gemini_provider():
            raise RuntimeError("Gemini provider가 아니므로 infer_json_from_video_bytes를 사용할 수 없습니다")

        model = model_override or os.getenv("LLM_MODEL_OMNI", "gemini-2.5-flash-lite")
        max_out = max_output_tokens or int(os.getenv("LLM_MAX_COMPLETION_TOKENS", "2048"))
        temp = float(os.getenv("LLM_TEMPERATURE", "0.2")) if temperature is None else float(temperature)

        timeout_sec = float(os.getenv("GEMINI_VIDEO_ANALYZE_TIMEOUT_SEC", "180"))
        http_timeout = httpx.Timeout(timeout_sec, connect=30.0)
        async with httpx.AsyncClient(timeout=http_timeout) as client:
            file_name: Optional[str] = None
            try:
                file_uri, file_name = await self._gemini_upload_video(client, video_bytes, mime_type)
                await self._gemini_wait_file_active(client, file_name)
                raw = await self._gemini_generate_text_from_file(
                    client,
                    file_uri=file_uri,
                    mime_type=mime_type,
                    prompt_text=prompt_text,
                    system_prompt=system_prompt,
                    model=model,
                    max_output_tokens=max_out,
                    temperature=temp,
                )
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = _parse_json_from_llm_text(raw)
                if not isinstance(parsed, dict):
                    raise RuntimeError("Gemini 비디오 분석 결과가 JSON object가 아닙니다")
                return parsed
            finally:
                await self._gemini_delete_file(client, file_name)

    async def analyze(
        self,
        video_data_url: str,
        *,
        prompt_hint: str = "",
        fps: Optional[float] = None,
        media_resolution: Optional[str] = None,
    ) -> dict:
        """
        Analyze one video and return structured summary for downstream diagnosis.
        @param fps - override MIMO_VIDEO_FPS (video_url.fps)
        @param media_resolution - override MIMO_VIDEO_MEDIA_RESOLUTION
        """
        # Gemini provider는 video_url 대신 Files API(비디오 바이트) 경로를 사용해야 한다.
        if self._is_gemini_provider():
            raise RuntimeError("Gemini provider에서는 analyze(video_data_url) 대신 analyze_bytes(...)를 사용하세요")

        client = _get_client()
        model = os.getenv("LLM_MODEL_OMNI", "gpt-4o")
        sys_prompt = (
            "You are a strict JSON video analysis engine. "
            "Return ONLY valid JSON without markdown fences."
        )
        user_prompt = (
            "Analyze the uploaded Instagram video and return JSON with fields: "
            "summary (string), "
            "scene_keywords (array of <=8 strings), "
            "cover_suggestion (string), "
            "has_face (boolean), "
            "shot_style (string), "
            "risk_or_limitations (array of strings). "
            "If confidence is low, still return best-effort values."
        )
        if prompt_hint.strip():
            user_prompt += f" Additional context: {prompt_hint.strip()}"

        video_part = build_mimo_video_url_content_part(video_data_url)
        if fps is not None:
            video_part["video_url"]["fps"] = max(0.1, min(float(fps), 10.0))
        if media_resolution is not None and media_resolution in ("default", "max"):
            video_part["media_resolution"] = media_resolution

        kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {
                    "role": "user",
                    "content": [
                        video_part,
                        {"type": "text", "text": user_prompt},
                    ],
                },
            ],
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.3")),
        }
        max_out = int(os.getenv("LLM_MAX_COMPLETION_TOKENS", "1024"))
        if _is_mimo_openai_compat():
            kwargs["max_completion_tokens"] = max_out
        else:
            kwargs["max_tokens"] = max_out

        resp = await client.chat.completions.create(**kwargs)
        raw = (resp.choices[0].message.content or "").strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = _parse_json_from_llm_text(raw)

        usage = getattr(resp, "usage", None)
        if usage:
            parsed["_meta"] = {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "model": resp.model,
            }

        parsed.setdefault("summary", "")
        parsed.setdefault("scene_keywords", [])
        parsed.setdefault("cover_suggestion", "")
        parsed.setdefault("has_face", False)
        parsed.setdefault("shot_style", "")
        parsed.setdefault("risk_or_limitations", [])
        return parsed

    async def analyze_bytes(
        self,
        video_bytes: bytes,
        *,
        mime_type: str,
        prompt_hint: str = "",
    ) -> dict:
        """
        Gemini provider용 비디오 바이트 분석.
        """
        if not self._is_gemini_provider():
            raise RuntimeError("analyze_bytes는 Gemini provider 전용입니다")
        user_prompt = (
            "Analyze the uploaded Instagram video and return JSON with fields: "
            "summary (string), "
            "scene_keywords (array of <=8 strings), "
            "cover_suggestion (string), "
            "has_face (boolean), "
            "shot_style (string), "
            "risk_or_limitations (array of strings). "
            "If confidence is low, still return best-effort values."
        )
        if prompt_hint.strip():
            user_prompt += f" Additional context: {prompt_hint.strip()}"
        system_prompt = "Return ONLY valid JSON without markdown fences."
        parsed = await self.infer_json_from_video_bytes(
            video_bytes,
            mime_type=mime_type,
            prompt_text=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
        )
        parsed.setdefault("summary", "")
        parsed.setdefault("scene_keywords", [])
        parsed.setdefault("cover_suggestion", "")
        parsed.setdefault("has_face", False)
        parsed.setdefault("shot_style", "")
        parsed.setdefault("risk_or_limitations", [])
        return parsed
    @staticmethod
    def _extract_error_message_from_payload(payload: object) -> str:
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict):
                msg = str(err.get("message", "")).strip()
                if msg:
                    return msg
            msg = str(payload.get("message", "")).strip()
            if msg:
                return msg
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, dict):
                err = first.get("error")
                if isinstance(err, dict):
                    msg = str(err.get("message", "")).strip()
                    if msg:
                        return msg
        return ""

    async def _request_json_or_raise(self, client: httpx.AsyncClient, method: str, url: str, **kwargs) -> dict:
        resp = await client.request(method, url, **kwargs)
        text = (resp.text or "").strip()
        payload: object
        try:
            payload = resp.json() if text else {}
        except Exception:
            payload = {"raw": text[:500]}

        if resp.status_code >= 400:
            msg = self._extract_error_message_from_payload(payload) or f"HTTP {resp.status_code}"
            raise RuntimeError(msg)
        if isinstance(payload, dict):
            return payload
        raise RuntimeError("Gemini 응답이 object JSON이 아닙니다")
