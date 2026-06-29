"""
공유 rate limiter.
비용이 큰 LLM/STT 엔드포인트(진단, 영상 인식 등)의 남용을 막아
무료 티어 쿼터 소진과 비용 폭증을 방지한다.

한도는 환경변수로 조정 가능:
- RATE_LIMIT_DIAGNOSE (기본 "10/minute") — 진단/영상 인식 등 무거운 호출
- RATE_LIMIT_LIGHT    (기본 "30/minute") — 댓글 생성 등 가벼운 호출
"""
import os

from slowapi import Limiter
from starlette.requests import Request


def _client_key(request: Request) -> str:
    """
    실제 클라이언트 IP를 키로 사용한다.
    Render 등 리버스 프록시 뒤에서는 X-Forwarded-For의 첫 IP가 실제 클라이언트다.
    """
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "anonymous"


limiter = Limiter(key_func=_client_key)

DIAGNOSE_LIMIT = os.getenv("RATE_LIMIT_DIAGNOSE", "10/minute")
LIGHT_LIMIT = os.getenv("RATE_LIMIT_LIGHT", "30/minute")
