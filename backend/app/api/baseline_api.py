"""
Baseline 조회 API
"""
from fastapi import APIRouter

from app.baseline.comparator import BaselineComparator

router = APIRouter()


@router.get("/baseline/{category}")
async def get_baseline(category: str):
    """
    지정 카테고리의 baseline 통계 요약을 조회한다.

    @param category - 카테고리 식별자 (food / fashion / tech)
    """
    comparator = BaselineComparator()
    stats = comparator.get_category_stats(category)
    return stats
