"""
API 라우트 정의
"""
from fastapi import APIRouter

from app.api.diagnose import router as diagnose_router
from app.api.baseline_api import router as baseline_router
from app.api.comments_api import router as comments_router
from app.api.history_api import router as history_router
from app.api.screenshot_api import router as screenshot_router
from app.api.optimize_api import router as optimize_router

router = APIRouter()


@router.get("/health")
async def api_health():
    """경량 헬스체크: Vite 프록시를 통한 백엔드 연결 가능 여부만 확인한다."""
    return {"ok": True, "service": "instarx-api"}


router.include_router(diagnose_router, tags=["diagnose"])
router.include_router(baseline_router, tags=["baseline"])
router.include_router(comments_router, tags=["comments"])
# history_router disabled — #58 fix: history is local-only (IndexedDB), server endpoints were a data leak
# router.include_router(history_router, tags=["history"])
router.include_router(screenshot_router, tags=["screenshot"])
router.include_router(optimize_router, tags=["optimize"])
