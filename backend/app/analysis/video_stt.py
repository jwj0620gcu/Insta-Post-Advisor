"""
영상 음성(STT) 전사 모듈.
비디오 오디오 트랙을 WAV로 추출한 뒤 OpenAI 호환 `/v1/audio/transcriptions`를 호출한다.

주의:
- 여기서는 TTS가 아니라 ASR(음성 -> 텍스트) 처리다.
- ffmpeg 설치 및 PATH 등록이 필요하다.
- `OPENAI_WHISPER_API_KEY`, `OPENAI_WHISPER_BASE_URL`를 올바르게 설정해야 한다.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger("insta-advisor.video_stt")


def _stt_enabled() -> bool:
    # 기본 활성화: 유효한 ASR 설정이 있으면 수행. VIDEO_STT_ENABLED=0 으로 명시 비활성화 가능.
    v = os.getenv("VIDEO_STT_ENABLED", "1").strip().lower()
    return v in ("1", "true", "yes", "on")


def _resolve_whisper_client_config() -> tuple[Optional[str], Optional[str]]:
    """
    @returns (api_key, base_url), 사용 불가 시 (None, None)
    """
    whisper_key = (os.getenv("OPENAI_WHISPER_API_KEY") or "").strip()
    explicit = (os.getenv("OPENAI_WHISPER_BASE_URL") or "").strip().rstrip("/")

    if explicit:
        # 제3자/공식 ASR base URL 사용 시 전용 Key 필수. MiMo OPENAI_API_KEY로 대체 금지.
        if not whisper_key:
            logger.info(
                "VIDEO_STT: OPENAI_WHISPER_BASE_URL이 설정되어 있습니다. .env에 OPENAI_WHISPER_API_KEY를 설정하세요.",
            )
            return None, None
        return whisper_key, explicit

    key = whisper_key or (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return None, None

    main = (os.getenv("OPENAI_BASE_URL") or "").strip().lower()
    if "xiaomimimo" in main or "mimo-v2.com" in main:
        logger.info(
            "VIDEO_STT: OPENAI_BASE_URL이 MiMo로 설정되어 있습니다. "
            "OPENAI_WHISPER_BASE_URL / OPENAI_WHISPER_API_KEY를 별도로 설정하세요 "
            "(예: https://api.openai.com/v1, https://api.siliconflow.cn/v1).",
        )
        return None, None
    if "generativelanguage.googleapis.com" in main:
        logger.info(
            "VIDEO_STT: OPENAI_BASE_URL이 Gemini(OpenAI 호환)로 설정되어 있어 "
            "/audio/transcriptions 경로를 사용하지 않습니다. "
            "STT가 필요하면 OPENAI_WHISPER_BASE_URL / OPENAI_WHISPER_API_KEY를 별도 설정하세요.",
        )
        return None, None

    base = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip().rstrip("/")
    return key, base


def _probe_video_duration_seconds(video_path: str) -> Optional[float]:
    """ffprobe로 영상 길이(초)를 조회한다."""
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            timeout=20,
            check=False,
        )
        if proc.returncode != 0:
            return None
        raw = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
        if not raw:
            return None
        dur = float(raw)
        if dur <= 0:
            return None
        return dur
    except Exception:
        return None


def _extract_wav_segment(video_path: str, *, start_sec: float, clip_sec: float) -> bytes:
    """
    영상에서 16kHz mono WAV 오디오 구간을 추출한다.
    @returns 실패 시 빈 bytes
    """
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{max(start_sec, 0):.3f}",
            "-i",
            video_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-t",
            f"{max(clip_sec, 1.0):.3f}",
            wav_path,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=max(120, int(clip_sec * 1.5)),
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="replace")[:400]
            logger.warning("VIDEO_STT: ffmpeg 구간 추출 실패 rc=%s %s", proc.returncode, err)
            return b""
        with open(wav_path, "rb") as wf:
            out = wf.read()
        return out
    except FileNotFoundError:
        logger.warning("VIDEO_STT: ffmpeg를 찾을 수 없습니다. 설치 후 PATH에 추가하세요.")
        return b""
    except subprocess.TimeoutExpired:
        logger.warning("VIDEO_STT: ffmpeg 구간 추출 타임아웃")
        return b""
    except Exception as e:
        logger.warning("VIDEO_STT: 구간 추출 예외 %s", e)
        return b""
    finally:
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass


def _extract_wav_chunks_from_video_bytes(video_bytes: bytes, container_suffix: str) -> list[bytes]:
    """
    ffmpeg로 영상 오디오를 여러 16kHz mono WAV 구간으로 분할한다.
    단일 파일 과대 업로드 거부를 피하기 위해 구간 단위 전사를 사용한다.
    @returns WAV 구간 목록. 실패 시 빈 리스트(예: ffmpeg 없음, 오디오 없음)
    """
    suffix = container_suffix if container_suffix.startswith(".") else f".{container_suffix}"
    max_total_sec = int(os.getenv("VIDEO_STT_MAX_AUDIO_SECONDS", "3600"))
    max_total_sec = max(60, min(max_total_sec, 14400))
    seg_sec = int(os.getenv("VIDEO_STT_SEGMENT_SECONDS", "480"))
    seg_sec = max(30, min(seg_sec, 1200))

    video_path = ""
    chunks: list[bytes] = []
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as vf:
            vf.write(video_bytes)
            video_path = vf.name

        duration = _probe_video_duration_seconds(video_path)
        if duration is None:
            # 길이 탐지 실패 시 상한값 기준으로 1회 이상 시도
            duration = float(max_total_sec)
        target_total = min(duration, float(max_total_sec))
        if duration > max_total_sec:
            logger.info(
                "VIDEO_STT: 영상 길이 %.1fs가 상한 %ss를 초과해 초과 구간은 전사하지 않습니다",
                duration,
                max_total_sec,
            )

        seg_count = max(1, int((target_total + seg_sec - 1) // seg_sec))
        for idx in range(seg_count):
            start_sec = idx * seg_sec
            remain = target_total - start_sec
            if remain <= 0:
                break
            clip_sec = min(seg_sec, remain)
            wav = _extract_wav_segment(video_path, start_sec=start_sec, clip_sec=clip_sec)
            if not wav:
                continue
            if len(wav) > 24 * 1024 * 1024:
                logger.warning(
                    "VIDEO_STT: 구간 %s WAV가 24MB를 초과했습니다. VIDEO_STT_SEGMENT_SECONDS 축소를 권장합니다",
                    idx + 1,
                )
            chunks.append(wav)
        return chunks
    except Exception as e:
        logger.warning("VIDEO_STT: 오디오 트랙 추출 예외 %s", e)
        return []
    finally:
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
            except OSError:
                pass


def _join_transcript_parts(parts: list[str]) -> str:
    """다중 전사 조각을 병합하고 경량 중복 제거를 수행한다."""
    out: list[str] = []
    for part in parts:
        text = (part or "").strip()
        if not text:
            continue
        if not out:
            out.append(text)
            continue
        prev = out[-1]
        if text in prev:
            continue
        if prev in text:
            out[-1] = text
            continue
        out.append(text)
    return "\n".join(out).strip()


async def _transcribe_single_wav(
    client,
    *,
    model: str,
    wav: bytes,
    timeout_sec: float,
    language: Optional[str],
) -> str:
    """
    단일 WAV 구간을 전사한다.
    우선 verbose_json을 시도하고 미지원 시 기본 포맷으로 자동 폴백한다.
    """
    base_kwargs: dict = {
        "model": model,
        "timeout": timeout_sec,
    }
    if language:
        base_kwargs["language"] = language

    prefer_verbose = os.getenv("VIDEO_STT_PREFER_VERBOSE_JSON", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    if prefer_verbose:
        try:
            buf = io.BytesIO(wav)
            buf.name = "audio.wav"
            resp = await client.audio.transcriptions.create(
                **base_kwargs,
                file=buf,
                response_format="verbose_json",
            )
            text = _transcription_text_from_response(resp)
            if text:
                return text
        except Exception as e:
            logger.info("VIDEO_STT: verbose_json 미지원으로 기본 포맷 폴백: %s", e)

    buf = io.BytesIO(wav)
    buf.name = "audio.wav"
    resp = await client.audio.transcriptions.create(**base_kwargs, file=buf)
    return _transcription_text_from_response(resp)


async def transcribe_video_with_whisper(video_bytes: bytes, container_suffix: str) -> str:
    """
    비동기 파이프라인: 스레드풀 WAV 추출 + AsyncOpenAI Whisper 전사.
    @returns 전사 텍스트. 실패/비활성화 시 빈 문자열
    """
    if not _stt_enabled():
        return ""

    key, base = _resolve_whisper_client_config()
    if not key or not base:
        return ""

    model = (os.getenv("WHISPER_MODEL") or "whisper-1").strip()

    chunks = await asyncio.to_thread(_extract_wav_chunks_from_video_bytes, video_bytes, container_suffix)
    if not chunks:
        logger.warning(
            "VIDEO_STT: WAV 구간이 비어 전사 API를 호출하지 않았습니다(ffmpeg/오디오 트랙/stderr 로그 확인).",
        )
        return ""

    import httpx
    from openai import AsyncOpenAI

    _stt_http_timeout = float(os.getenv("VIDEO_STT_TIMEOUT_SEC", "240"))
    _stt_http_timeout = max(60.0, min(_stt_http_timeout, 600.0))
    http_client = httpx.AsyncClient(
        proxy=None,
        trust_env=False,
        timeout=httpx.Timeout(_stt_http_timeout, connect=60.0),
    )
    try:
        client = AsyncOpenAI(api_key=key, base_url=base, http_client=http_client)
        # 미설정 시 기본 언어 ko. 빈 문자열을 명시하면 language 파라미터를 보내지 않는다.
        _lr = os.getenv("VIDEO_STT_LANGUAGE")
        if _lr is None:
            lang = "ko"
        else:
            lang = _lr.strip() or None
        texts: list[str] = []
        total = len(chunks)
        for idx, wav in enumerate(chunks, start=1):
            try:
                text = await _transcribe_single_wav(
                    client,
                    model=model,
                    wav=wav,
                    timeout_sec=_stt_http_timeout,
                    language=lang,
                )
            except Exception as e:
                logger.warning("VIDEO_STT: 구간 전사 실패 chunk=%s/%s err=%s", idx, total, e)
                text = ""
            if text:
                texts.append(text)
                logger.info("VIDEO_STT: 구간 전사 성공 chunk=%s/%s len=%s", idx, total, len(text))
            else:
                logger.warning("VIDEO_STT: 구간 전사 결과가 비어 있음 chunk=%s/%s", idx, total)

        merged = _join_transcript_parts(texts)
        if merged:
            logger.info("VIDEO_STT: 전체 전사 성공 chunks=%s total_len=%s model=%s", total, len(merged), model)
        else:
            logger.warning("VIDEO_STT: 전체 전사 결과가 비어 있습니다. ASR 모델/오디오 내용을 확인하세요.")
        return merged
    except Exception as e:
        logger.warning("VIDEO_STT: 전사 API 실패 %s", e)
        return ""
    finally:
        await http_client.aclose()


def _transcription_text_from_response(resp: object) -> str:
    """
    OpenAI SDK 또는 호환 JSON 전사 응답에서 순수 텍스트를 추출한다.
    @param resp - Transcription 객체 또는 호환 구조
    @returns 앞뒤 공백 제거된 전사 텍스트
    """
    if resp is None:
        return ""
    segments = getattr(resp, "segments", None)
    if isinstance(segments, list):
        lines = [
            str((seg or {}).get("text", "")).strip()
            for seg in segments
            if isinstance(seg, dict) and str((seg or {}).get("text", "")).strip()
        ]
        if lines:
            return "\n".join(lines).strip()
    t = getattr(resp, "text", None)
    if isinstance(t, str) and t.strip():
        return t.strip()
    dump = getattr(resp, "model_dump", None)
    if callable(dump):
        try:
            d = dump()
            if isinstance(d, dict):
                segs = d.get("segments")
                if isinstance(segs, list):
                    lines = [
                        str((seg or {}).get("text", "")).strip()
                        for seg in segs
                        if isinstance(seg, dict) and str((seg or {}).get("text", "")).strip()
                    ]
                    if lines:
                        return "\n".join(lines).strip()
                tx = d.get("text")
                if isinstance(tx, str) and tx.strip():
                    return tx.strip()
        except Exception:
            pass
    if isinstance(resp, dict):
        segs = resp.get("segments")
        if isinstance(segs, list):
            lines = [
                str((seg or {}).get("text", "")).strip()
                for seg in segs
                if isinstance(seg, dict) and str((seg or {}).get("text", "")).strip()
            ]
            if lines:
                return "\n".join(lines).strip()
        tx = resp.get("text")
        if isinstance(tx, str) and tx.strip():
            return tx.strip()
    return ""
