"""
Model A 재보정을 위한 데이터/평가 계약(Contract).

목적:
- 재보정 전에 카테고리/포맷/지표 기준을 고정해 데이터 수집-학습-서빙 간 드리프트를 막는다.
- 프론트/백엔드/학습 스크립트가 동일한 키를 사용하도록 단일 소스로 제공한다.
"""
from __future__ import annotations

from dataclasses import dataclass

FEATURE_CONTRACT_VERSION = "v1.1.0"

# 재보정 대상 카테고리 (프론트 CategoryPicker 및 research_data와 동일 키 사용)
CATEGORIES: tuple[str, ...] = (
    "food",
    "fashion",
    "fitness",
    "business",
    "lifestyle",
    "travel",
    "education",
    "shop",
)

# 인스타 포맷 축
FORMATS: tuple[str, ...] = ("reels", "carousel", "single")

# 포맷별 주 타깃 지표 (학습 label 우선순위)
TARGET_METRICS_BY_FORMAT: dict[str, tuple[str, ...]] = {
    # Reels: retention + share 중심
    "reels": (
        "watch_3s_rate",
        "watch_completion_rate",
        "shares",
        "saves",
        "engagement_rate",
    ),
    # Carousel: save/swipe 중심
    "carousel": (
        "saves",
        "carousel_swipe_rate",
        "shares",
        "engagement_rate",
    ),
    # Single image: saves/profile_visit 중심
    "single": (
        "saves",
        "profile_visits",
        "shares",
        "engagement_rate",
    ),
}

# 공통 원천 컬럼 (full mode: 인사이트 포함)
REQUIRED_RAW_COLUMNS_COMMON: tuple[str, ...] = (
    "post_id",
    "created_at",
    "category",
    "format",
    "caption",
    "hashtags_count",
    "media_count",
    "followers",
    "reach",
    "impressions",
    "likes",
    "comments",
    "saves",
    "shares",
)

# public-crawl mode: 화면/공개 정보 기반 최소 필수 컬럼
REQUIRED_RAW_COLUMNS_COMMON_PUBLIC_CRAWL: tuple[str, ...] = (
    "post_id",
    "created_at",
    "category",
    "format",
    "caption",
    "hashtags_count",
    "media_count",
    "followers",
    "likes",
    "comments",
)

# 선택 수집 컬럼 (있으면 품질/프록시 정확도 향상)
OPTIONAL_RAW_COLUMNS_COMMON: tuple[str, ...] = (
    "views",  # reels 조회수 등
)

# 포맷별 추가 필수 컬럼 (full mode)
REQUIRED_RAW_COLUMNS_BY_FORMAT: dict[str, tuple[str, ...]] = {
    "reels": ("watch_3s_rate", "watch_completion_rate"),
    "carousel": ("carousel_swipe_rate",),
    "single": ("profile_visits",),
}

# 포맷별 추가 필수 컬럼 (public-crawl mode)
REQUIRED_RAW_COLUMNS_BY_FORMAT_PUBLIC_CRAWL: dict[str, tuple[str, ...]] = {
    "reels": (),
    "carousel": (),
    "single": (),
}


@dataclass(frozen=True)
class RangeRule:
    min_value: float
    max_value: float


# 수치 컬럼 기본 범위 (품질 검증용)
NUMERIC_RANGE_RULES: dict[str, RangeRule] = {
    "hashtags_count": RangeRule(0, 30),
    "media_count": RangeRule(1, 20),
    # 글로벌 브랜드/메가 계정 포함 public-crawl 데이터 대응
    "followers": RangeRule(0, 2_000_000_000),
    "reach": RangeRule(0, 100_000_000),
    "impressions": RangeRule(0, 100_000_000),
    "likes": RangeRule(0, 50_000_000),
    "comments": RangeRule(0, 5_000_000),
    "saves": RangeRule(0, 10_000_000),
    "shares": RangeRule(0, 10_000_000),
    "watch_3s_rate": RangeRule(0, 100),
    "watch_completion_rate": RangeRule(0, 100),
    "carousel_swipe_rate": RangeRule(0, 100),
    "profile_visits": RangeRule(0, 10_000_000),
}


def is_valid_category(category: str) -> bool:
    return category in CATEGORIES


def is_valid_format(content_format: str) -> bool:
    return content_format in FORMATS


def required_columns_for_format(content_format: str) -> tuple[str, ...]:
    return REQUIRED_RAW_COLUMNS_COMMON + REQUIRED_RAW_COLUMNS_BY_FORMAT.get(content_format, ())


def required_columns_for_format_public_crawl(content_format: str) -> tuple[str, ...]:
    return (
        REQUIRED_RAW_COLUMNS_COMMON_PUBLIC_CRAWL
        + REQUIRED_RAW_COLUMNS_BY_FORMAT_PUBLIC_CRAWL.get(content_format, ())
    )
