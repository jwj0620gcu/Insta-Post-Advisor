"""
Agent 기반 클래스
LLM 호출, 프롬프트 템플릿, 구조화 출력 파싱을 캡슐화.
flash(빠른) / pro(전문) / omni(멀티모달) 3계층 모델 지원.
OpenAI 호환 게이트웨이(Claude, GPT, MiMo 등) 지원.
"""
import json
import os
import logging
import re
import asyncio
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv


def _load_env_files() -> None:
    """
    실제 `.env` 파일만 로드한다. `.env.example`은 런타임에 절대 사용하지 않는다.

    로드 순서 및 override:
    - 저장소 루트 `.env` (override=False, 누락 키만 보강)
    - `backend/.env` (override=True, backend 설정 우선)
    - 현재 작업 디렉터리와 상위 디렉터리의 `.env` (override=True, 로컬 오버라이드용)
    """
    current = Path(__file__).resolve()
    backend_root = current.parents[2]
    repo_root = current.parents[3]
    candidates: list[tuple[Path, bool]] = [
        (repo_root / ".env", False),
        (backend_root / ".env", True),
        (Path.cwd() / ".env", True),
        (Path.cwd().parent / ".env", True),
    ]
    seen: set[Path] = set()
    for p, override in candidates:
        if p.name == ".env.example":
            continue
        rp = p.resolve()
        if rp in seen:
            continue
        if not rp.is_file():
            continue
        seen.add(rp)
        load_dotenv(rp, override=override)


_load_env_files()

logger = logging.getLogger("instarx.agent")

MODEL_FAST = os.getenv("LLM_MODEL_FAST", "gpt-4o-mini")
MODEL_PRO = os.getenv("LLM_MODEL_PRO", "gpt-4o")
MODEL_OMNI = os.getenv("LLM_MODEL_OMNI", "gpt-4o")


def _llm_provider() -> str:
    return (os.getenv("LLM_PROVIDER") or "openai").strip().lower()


def _is_mimo_openai_compat() -> bool:
    """
    MiMo OpenAPI(OpenAI 호환) 모드로 파라미터를 처리할지 판단한다.
    OPENAI_COMPAT=mimo 또는 BASE_URL/모델명으로 자동 추론한다.
    """
    if _llm_provider() == "anthropic":
        return False
    if os.getenv("OPENAI_COMPAT", "").strip().lower() == "mimo":
        return True
    base = (os.getenv("OPENAI_BASE_URL") or "").lower()
    if "xiaomimimo.com" in base or "mimo-v2.com" in base:
        return True
    model = (os.getenv("LLM_MODEL") or "").lower()
    return model.startswith("mimo-")


def _resolve_openai_base_url() -> Optional[str]:
    """
    OpenAI 호환 게이트웨이 base_url을 해석한다.
    OPENAI_BASE_URL에 API Key를 잘못 넣은 경우 경고를 출력한다.
    """
    provider = _llm_provider()
    raw = (os.getenv("OPENAI_BASE_URL") or "").strip()
    if raw.startswith("sk-") and len(raw) > 30:
        logger.warning(
            "OPENAI_BASE_URL 값이 API Key처럼 보입니다. 키는 OPENAI_API_KEY에 넣고, "
            "OPENAI_BASE_URL에는 게이트웨이 주소(예: https://api.xiaomimimo.com/v1)를 설정하세요."
        )
        raw = ""
    if raw:
        return raw.rstrip("/")
    # Anthropic/Gemini providers are routed via OpenAI-compatible client endpoints.
    if provider == "anthropic":
        return "https://api.anthropic.com/v1"
    if provider == "gemini":
        return "https://generativelanguage.googleapis.com/v1beta/openai"
    if _is_mimo_openai_compat():
        return "https://api.xiaomimimo.com/v1"
    return None


def _resolve_openai_api_key() -> str:
    provider = _llm_provider()
    if provider == "anthropic":
        return (os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    if provider == "gemini":
        return (os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def _get_client():
    """로컬 프록시를 우회하는 OpenAI 호환 API 클라이언트를 생성한다."""
    import httpx
    from openai import AsyncOpenAI
    http_client = httpx.AsyncClient(
        proxy=None,
        trust_env=False,
        timeout=httpx.Timeout(120.0, connect=30.0),
    )
    return AsyncOpenAI(
        api_key=_resolve_openai_api_key(),
        base_url=_resolve_openai_base_url(),
        http_client=http_client,
    )


def _normalize_llm_output_for_json(raw: str) -> str:
    """
    추론 모델이 앞에 붙이는 thinking 블록을 제거해 JSON 파싱을 안정화한다.
    """
    t = str(raw).strip()
    # 마지막 닫힘 태그 뒤 본문만 사용(thinking 앞, JSON 뒤 가정)
    split_markers = (
        "</redacted_reasoning>",
        "</redacted_thinking>",
        "</think>",
    )
    for pat in split_markers:
        if pat.lower() in t.lower():
            parts = re.split(re.escape(pat), t, flags=re.IGNORECASE)
            t = parts[-1].strip()
    t = re.sub(r"<redacted_reasoning>[\s\S]*?</redacted_reasoning>", "", t, flags=re.IGNORECASE)
    t = re.sub(r"<redacted_thinking>[\s\S]*?</redacted_thinking>", "", t, flags=re.IGNORECASE)
    return t.strip()


def _parse_json_from_llm_text(raw: Optional[str]) -> dict:
    """
    모델 출력에서 최상위 object JSON을 파싱한다.
    thinking 태그, 코드펜스, 앞뒤 노이즈를 허용한다.
    """
    if not raw or not str(raw).strip():
        raise json.JSONDecodeError("empty", "", 0)
    text = _normalize_llm_output_for_json(str(raw).strip())

    # 1) ``` / ```json 코드블록 추출
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    elif text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)

    # 2) 전체 문자열을 JSON으로 바로 파싱
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and len(obj) > 0:
            return obj
    except json.JSONDecodeError:
        pass

    # 3) 가능한 '{' 시작점마다 raw_decode 시도(초반 예시 JSON 회피)
    decoder = json.JSONDecoder()
    brace_starts = [i for i, c in enumerate(text) if c == "{"]
    last_err: Optional[Exception] = None
    for start in brace_starts[:16]:
        try:
            obj, _end = decoder.raw_decode(text, start)
        except json.JSONDecodeError as e:
            last_err = e
            continue
        if isinstance(obj, dict) and len(obj) > 0:
            return obj
    if last_err is not None:
        logger.warning(
            "JSON raw_decode 모두 실패(LLM_MAX_COMPLETION_TOKENS / JUDGE_MAX_COMPLETION_TOKENS 상향 검토): %s",
            last_err,
        )
    raise json.JSONDecodeError("no valid json object in output", text, 0)


def _bytes_to_image_data_url(image_bytes: bytes) -> str:
    """
    매직 바이트로 MIME을 판별해 OpenAI/MiMo 호환 data URL(image_url)을 생성한다.
    """
    import base64

    if not image_bytes:
        raise ValueError("image_bytes is empty")
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    if image_bytes.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif len(image_bytes) > 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        mime = "image/webp"
    elif image_bytes[:6] in (b"GIF87a", b"GIF89a"):
        mime = "image/gif"
    else:
        mime = "image/jpeg"
    return f"data:{mime};base64,{b64}"


def _should_retry_openai_without_json_format(exc: BaseException) -> bool:
    """일부 게이트웨이는 response_format=json_object를 지원하지 않아 제외 재시도한다."""
    msg = str(exc).lower()
    if "response_format" in msg or "json_object" in msg:
        return True
    code = getattr(exc, "status_code", None)
    if code is None and hasattr(exc, "response"):
        code = getattr(getattr(exc, "response", None), "status_code", None)
    return code in (400, 422)


def _is_rate_limit_error(exc: BaseException) -> bool:
    """429/RESOURCE_EXHAUSTED/quota 계열 오류를 감지한다."""
    msg = str(exc).lower()
    if "resource_exhausted" in msg or "quota" in msg or "rate limit" in msg:
        return True
    code = getattr(exc, "status_code", None)
    if code is None and hasattr(exc, "response"):
        code = getattr(getattr(exc, "response", None), "status_code", None)
    return code == 429


def _retry_after_seconds_from_error(exc: BaseException) -> float:
    """
    에러 메시지에서 retry 힌트를 파싱한다.
    예: "Please retry in 914.627272ms."
    """
    msg = str(exc)
    m_ms = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)\s*ms", msg, re.IGNORECASE)
    if m_ms:
        return max(0.2, float(m_ms.group(1)) / 1000.0)
    m_s = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)\s*s", msg, re.IGNORECASE)
    if m_s:
        return max(0.2, float(m_s.group(1)))
    return float(os.getenv("LLM_RATE_LIMIT_BACKOFF_SEC", "1.2"))


class BaseAgent:
    """모든 진단 에이전트의 공통 베이스 클래스."""

    agent_name: str = "BaseAgent"
    system_prompt: str = ""

    def __init__(self, model: Optional[str] = None):
        self.model = model or MODEL_PRO
        self.client = _get_client()

    async def call_llm(
        self,
        user_message: str,
        system_override: Optional[str] = None,
        model_override: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> dict:
        sys_prompt = system_override or self.system_prompt
        if model_override:
            self.model = model_override

        return await self._call_openai(sys_prompt, user_message, max_tokens=max_tokens)

    async def _call_openai(self, sys_prompt: str, user_message: str, max_tokens: int = 2048) -> dict:
        """OpenAI 호환 호출(MiMo 포함) + JSON 모드 호환 처리."""
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_message},
        ]
        mimo = _is_mimo_openai_compat()
        max_out = max_tokens or int(os.getenv("LLM_MAX_COMPLETION_TOKENS", "2048"))
        skip_json_mode = os.getenv("LLM_SKIP_JSON_RESPONSE_FORMAT", "").strip() in ("1", "true", "yes")

        async def _create(with_json_object: bool):
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": float(os.getenv("LLM_TEMPERATURE", "0")),
            }
            # seed for reproducibility (if supported by provider)
            seed_val = os.getenv("LLM_SEED", "")
            if seed_val:
                kwargs["seed"] = int(seed_val)
            if mimo:
                kwargs["max_completion_tokens"] = max_out
            else:
                kwargs["max_tokens"] = max_out
            if with_json_object and not skip_json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            return await self.client.chat.completions.create(**kwargs)

        response = None
        last_err: Optional[BaseException] = None
        attempts: list[bool] = []
        if not skip_json_mode:
            attempts.append(True)
        attempts.append(False)
        rate_limit_retries = max(0, int(os.getenv("LLM_RATE_LIMIT_RETRIES", "2")))

        for use_json in attempts:
            rl_retry = 0
            while True:
                try:
                    response = await _create(with_json_object=use_json)
                    break
                except Exception as e:
                    last_err = e
                    if use_json and _should_retry_openai_without_json_format(e):
                        logger.info("게이트웨이가 response_format=json_object를 지원하지 않아 해당 파라미터 없이 재시도: %s", e)
                        break
                    if _is_rate_limit_error(e) and rl_retry < rate_limit_retries:
                        wait_s = _retry_after_seconds_from_error(e)
                        rl_retry += 1
                        logger.warning(
                            "Rate limit 감지, %.2fs 대기 후 재시도 (%d/%d): %s",
                            wait_s, rl_retry, rate_limit_retries, e,
                        )
                        await asyncio.sleep(wait_s)
                        continue
                    logger.warning("OpenAI 호출 실패: %s", e)
                    return self._error_response(str(e))
            if response is not None:
                break

        if response is None:
            return self._error_response(str(last_err) if last_err else "LLM 응답 없음")

        try:
            raw = response.choices[0].message.content
            try:
                result = json.loads(raw or "")
            except json.JSONDecodeError:
                result = _parse_json_from_llm_text(raw)
            if not isinstance(result, dict):
                logger.warning("LLM 응답의 최상위 타입이 object가 아님: %s", str(raw)[:400])
                return self._error_response("LLM이 JSON object가 아닌 값을 반환했습니다(기대값: {...})")
            usage = response.usage
            if usage:
                result["_meta"] = {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "model": response.model,
                }
            return result
        except json.JSONDecodeError:
            logger.warning("LLM 원본 출력(비 JSON): %s", (raw or "")[:500])
            return self._error_response("LLM이 JSON 형식이 아닌 내용을 반환했습니다")
        except Exception as e:
            logger.warning("LLM 응답 파싱 실패: %s", e)
            return self._error_response(str(e))

    async def call_llm_vision(
        self,
        text_message: str,
        image_bytes: bytes,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> dict:
        """
        멀티모달 모델(MODEL_OMNI)로 이미지를 분석한다.
        image_bytes는 JPEG/PNG/WebP 등 원본 바이트여야 한다.
        """
        sys_prompt = system_prompt or self.system_prompt
        mimo = _is_mimo_openai_compat()
        max_out = max_tokens or int(os.getenv("LLM_MAX_COMPLETION_TOKENS", "2048"))
        skip_json_mode = os.getenv("LLM_SKIP_JSON_RESPONSE_FORMAT", "").strip() in ("1", "true", "yes")
        temp = float(os.getenv("LLM_TEMPERATURE", "0"))
        data_url = _bytes_to_image_data_url(image_bytes)

        async def _create(with_json_object: bool):
            kwargs: dict = {
                "model": MODEL_OMNI,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": text_message},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
                "temperature": temp,
            }
            if mimo:
                kwargs["max_completion_tokens"] = max_out
            else:
                kwargs["max_tokens"] = max_out
            if with_json_object and not skip_json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            return await self.client.chat.completions.create(**kwargs)

        response = None
        last_err: Optional[BaseException] = None
        attempts: list[bool] = []
        if not skip_json_mode:
            attempts.append(True)
        attempts.append(False)
        rate_limit_retries = max(0, int(os.getenv("LLM_RATE_LIMIT_RETRIES", "2")))

        for use_json in attempts:
            rl_retry = 0
            while True:
                try:
                    response = await _create(with_json_object=use_json)
                    break
                except Exception as e:
                    last_err = e
                    if use_json and _should_retry_openai_without_json_format(e):
                        logger.info("멀티모달 게이트웨이가 response_format=json_object를 지원하지 않아 파라미터 없이 재시도: %s", e)
                        break
                    if _is_rate_limit_error(e) and rl_retry < rate_limit_retries:
                        wait_s = _retry_after_seconds_from_error(e)
                        rl_retry += 1
                        logger.warning(
                            "멀티모달 rate limit 감지, %.2fs 대기 후 재시도 (%d/%d): %s",
                            wait_s, rl_retry, rate_limit_retries, e,
                        )
                        await asyncio.sleep(wait_s)
                        continue
                    logger.warning("멀티모달 호출 실패: %s", e)
                    return self._error_response(str(e))
            if response is not None:
                break

        if response is None:
            return self._error_response(str(last_err) if last_err else "멀티모달 LLM 응답 없음")

        raw: Optional[str] = None
        try:
            raw = response.choices[0].message.content
            try:
                result = json.loads((raw or "").strip())
            except json.JSONDecodeError:
                result = _parse_json_from_llm_text(raw)
            if not isinstance(result, dict):
                return self._error_response("멀티모달 모델이 JSON object가 아닌 값을 반환했습니다")
            usage = response.usage
            if usage:
                result["_meta"] = {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                    "model": response.model,
                }
            return result
        except json.JSONDecodeError:
            logger.warning("멀티모달 원본 출력(비 JSON): %s", (raw or "")[:800])
            return self._error_response("멀티모달 모델이 JSON 형식이 아닌 내용을 반환했습니다")
        except Exception as e:
            logger.warning("멀티모달 응답 파싱 실패: %s", e)
            return self._error_response(str(e))

    def _error_response(self, error_msg: str) -> dict:
        lower_msg = (error_msg or "").lower()
        suggestions = ["잠시 후 다시 시도해주세요"]
        if "invalid api key" in lower_msg or "invalid_key" in lower_msg or "401" in lower_msg:
            if _llm_provider() == "anthropic":
                suggestions = [
                    "Anthropic API Key가 유효하지 않습니다. `ANTHROPIC_API_KEY` 값을 확인하세요.",
                    "Anthropic 모드에서는 `ANTHROPIC_API_KEY`를 우선 사용하며, 없을 때만 `OPENAI_API_KEY`를 fallback으로 읽습니다.",
                ]
            elif _llm_provider() == "gemini":
                suggestions = [
                    "Gemini API Key가 유효하지 않습니다. Google AI Studio에서 발급한 키를 `GEMINI_API_KEY`에 설정하세요.",
                    "Gemini OpenAI 호환 엔드포인트는 AI Studio API 키를 요구합니다(일반적으로 `AIza...` 형태).",
                ]
            else:
                suggestions = [
                    "API Key가 유효하지 않습니다. OPENAI_API_KEY가 올바른지, 만료되지 않았는지 확인하세요.",
                    "키는 `backend/.env`를 기준으로 합니다. `.env.example`은 템플릿이므로 설정 소스로 사용하지 마세요.",
                ]
        if _llm_provider() == "gemini" and "multiple authentication credentials received" in lower_msg:
            suggestions = [
                "Gemini 인증이 중복/불일치 상태입니다. `backend/.env`에는 `GEMINI_API_KEY`만 유효한 값으로 두세요.",
                "현재 값이 Gemini API 키 형식이 아닐 수 있습니다. Google AI Studio에서 새 API 키를 발급해 교체하세요.",
            ]
        return {
            "agent_name": self.agent_name,
            "dimension": "error",
            "score": 0,
            "issues": [f"진단 오류: {error_msg}"],
            "suggestions": suggestions,
            "reasoning": f"Error: {error_msg}",
        }

    def build_user_message(self, **kwargs) -> str:
        raise NotImplementedError
