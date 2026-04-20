"""
데이터 기반 모듈 — Insta-Advisor (인스타그램 버전)

학습 데이터 출처:
  - 96개 실제 인스타그램 게시물 (2026년 3-4월, 8개 카테고리 × 12개)
    data/instagram_recalibration/modela_ready_weak.csv
  - 계정 규모: 메가브랜드(2.4M~298M 팔로워) → 중소 계정 스케일 조정 적용
  - 포맷별 ER: carousel avg=0.2445 > reels avg=0.1633 > single avg=0.0402
  - 보조 출처: Social Insider, Hootsuite, Sprout Social 2026 벤치마크

함수 시그니처:
  pre_score(title, content, category, tag_count, image_count)
  dimensions 키: title_quality / content_quality / visual_quality / tag_strategy / engagement_potential
"""
from __future__ import annotations

import re
from typing import Optional

# =============================================================================
# 바이럴 예시 캡션 (한국 인스타 스타일)
# =============================================================================

VIRAL_TITLES: dict[str, list[str]] = {
    "food": [
        "여기 진짜 숨은 맛집인데... 공유해도 되나 고민됨",
        "3,900원에 이 퀄리티? 솔직히 반칙",
        "엄마 레시피 공개) 이거 하나면 반찬 끝",
    ],
    "fashion": [
        "키 158 현실 코디 5가지 (통통녀 ver)",
        "요즘 이 조합 모르면 손해",
        "3만원대로 분위기 바뀌는 봄 코디",
    ],
    "fitness": [
        "하루 10분, 2주만에 라인 달라짐",
        "헬스 3년차가 초보때 알았으면 좋았을 것",
        "거북목 교정 루틴 5분 컷",
    ],
    "business": [
        "광고비 0원으로 문의 30건 받은 방법",
        "소상공인 인스타 운영, 이거부터 하세요",
        "매출 올린 릴스 문법 3가지",
    ],
    "lifestyle": [
        "자취 7년차가 남긴 생활 꿀팁",
        "퇴사 6개월차, 현실적으로 느낀 점",
        "아이랑 하루가 쉬워진 루틴 공유",
    ],
    "travel": [
        "서울 근교 당일치기, 여긴 무조건 저장",
        "오사카 3박4일 경비 총정리",
        "사람 적은 인생뷰 스팟 공개",
    ],
    "education": [
        "저장 필수) 직장인 재테크 시작 가이드",
        "영어 공부 10년 해도 안 늘던 이유",
        "세금 환급 5단계 한 번에 정리",
    ],
    "shop": [
        "광고 아님) 6개월 써보고 남기는 후기",
        "올영 세일 전에 봐야 할 추천템",
        "2만원대로 삶의 질 올라간 아이템",
    ],
}

REAL_COMMENTS: dict[str, list[str]] = {
    "food": [
        "여기 어디예요? 위치 부탁드려요",
        "저장해둘게요 주말에 가봄",
        "가격대 어느 정도예요?",
        "광고 같긴 한데 궁금하긴 함",
    ],
    "fashion": [
        "정보 감사합니다 링크 있을까요?",
        "사이즈 참고 가능할까요?",
        "저장완. 이 코디 그대로 입어봐야지",
        "현실은 저 핏 안 나올 듯 ㅋㅋ",
    ],
    "fitness": [
        "무릎 안 좋은 사람도 가능한가요?",
        "오운완 인증하고 갑니다",
        "3일 하고 포기한 1인...",
        "효과 있으면 후기 남길게요",
    ],
    "business": [
        "DM 드려도 될까요?",
        "소규모 매장에도 적용 가능해요?",
        "바로 실행해볼게요 감사합니다",
        "케바케 아닐까요?",
    ],
    "lifestyle": [
        "공감돼요 진짜",
        "힐링된다...",
        "이런 글 더 써주세요",
        "좋은 말인데 현실은 다름",
    ],
    "travel": [
        "교통편 알려주실 수 있나요?",
        "숙소 이름 궁금해요",
        "저장해두고 다음 여행 때 가볼게요",
        "사진 보정값도 공유 가능해요?",
    ],
    "education": [
        "이건 진짜 저장각",
        "한 번에 정리돼서 좋네요",
        "더 자세한 내용도 보고 싶어요",
        "이미 아는 내용이긴 해요",
    ],
    "shop": [
        "구매 링크 있을까요?",
        "써본 사람인데 이거 좋음",
        "가격 대비 어떤가요?",
        "협찬 여부 궁금합니다",
    ],
}

# =============================================================================
# Model A 카테고리 파라미터
# 실제 데이터(96개 인스타 게시물) 기반 도출
#
# weights 키 (5차원):
#   title_quality      ← 후킹력 (첫 줄, 첫 이미지, 첫 3초 스크롤 저지력)
#   content_quality    ← 캡션 품질 (정보 밀도, CTA 구성)
#   visual_quality     ← 시각 완성도 (이미지/영상 품질, 색감, 구도)
#   tag_strategy       ← 해시태그 + 포맷 전략 (2026 기준 3-5개 최적)
#   engagement_potential ← 전환 잠재력 (저장/DM/구매 유도력)
#
# baseline 단위:
#   avg/median/viral_threshold: 인스타 engagement_proxy_count (likes+comments+saves+shares)
#   watch_3s_rate_avg: 릴스 첫 3초 리텐션 % (실제 측정값)
#   carousel_swipe_rate_avg: 캐러셀 스와이프율 % (실제 측정값)
#   fmt_er_reels/carousel: 포맷별 engagement_proxy_rate (실제 측정값)
# =============================================================================

MODEL_PARAMS: dict[str, dict] = {
    # ── food ──────────────────────────────────────────────────────────────────
    # 캐러셀 ER 0.38 > 릴스 0.13 (캐러셀 3배 우세)
    # 캡션 짧음 (med=45자), 시각이 핵심, 3초 리텐션 보통(17.2%)
    # → 시각+후킹이 중요, 정보 밀도 낮아도 됨
    "food": {
        "weights": {
            "title_quality": 0.28,        # 후킹력: 첫 이미지+첫 줄
            "content_quality": 0.12,      # 캡션: 짧아도 OK, CTA만 있으면 됨
            "visual_quality": 0.30,       # 시각: 음식 = 비주얼이 핵심
            "tag_strategy": 0.10,
            "engagement_potential": 0.20, # 저장/위치태그/댓글 유도
        },
        "title_length": {"min": 10, "max": 40, "viral_avg": 22.0},
        "content_length": {"min": 20, "max": 310},
        "tag_count": {"min": 3, "max": 7, "best": 5},
        "image_count": {"min": 1, "max": 10},
        "baseline": {
            "avg_engagement": 6231,
            "median": 4200,
            "viral_threshold": 25000,
            "sample_size": 12,
            "watch_3s_rate_avg": 17.2,
            "carousel_swipe_rate_avg": 57.7,
            "fmt_er_carousel": 0.38,
            "fmt_er_reels": 0.13,
            "best_post_hours": [12, 18, 19, 20],
            "recommended_formats": ["carousel", "reels"],
        },
    },

    # ── fashion ───────────────────────────────────────────────────────────────
    # 릴스 ER 0.034 > 캐러셀 0.020 (릴스 소폭 우세)
    # 3초 리텐션 높음(23.1%), 캡션 중간(med=116자), 시각이 절대적
    # → 후킹+시각이 매우 중요, 텍스트 영향 낮음 (R²≈0.02)
    "fashion": {
        "weights": {
            "title_quality": 0.25,        # 후킹력: 첫 컷 + 첫 줄
            "content_quality": 0.08,      # 캡션: 시각이 모든 걸 설명
            "visual_quality": 0.38,       # 시각: 패션 카테고리 최고 가중치
            "tag_strategy": 0.08,
            "engagement_potential": 0.21,
        },
        "title_length": {"min": 8, "max": 32, "viral_avg": 18.0},
        "content_length": {"min": 20, "max": 294},
        "tag_count": {"min": 3, "max": 7, "best": 5},
        "image_count": {"min": 1, "max": 10},
        "baseline": {
            "avg_engagement": 13418,
            "median": 8000,
            "viral_threshold": 50000,
            "sample_size": 12,
            "watch_3s_rate_avg": 23.1,
            "carousel_swipe_rate_avg": 56.4,
            "fmt_er_reels": 0.034,
            "fmt_er_carousel": 0.020,
            "best_post_hours": [11, 12, 18, 19, 20],
            "recommended_formats": ["reels", "carousel"],
        },
    },

    # ── fitness ───────────────────────────────────────────────────────────────
    # 캐러셀 ER 0.32 > 릴스 0.10 (캐러셀 3배 우세), 단 전체 ER 최고 수준
    # 3초 리텐션 높음(23.9%), 캡션 중간(med=148자)
    # → 시각+전환(비포/애프터 루틴)이 핵심, 바이럴 잠재력 높음
    "fitness": {
        "weights": {
            "title_quality": 0.22,
            "content_quality": 0.18,      # 루틴 설명, 방법론 중요
            "visual_quality": 0.22,       # 비포/애프터, 운동 시연
            "tag_strategy": 0.10,
            "engagement_potential": 0.28, # 저장률 높은 카테고리 (루틴 저장)
        },
        "title_length": {"min": 10, "max": 38, "viral_avg": 20.0},
        "content_length": {"min": 50, "max": 342},
        "tag_count": {"min": 3, "max": 7, "best": 5},
        "image_count": {"min": 1, "max": 10},
        "baseline": {
            "avg_engagement": 14932,
            "median": 8500,
            "viral_threshold": 60000,
            "sample_size": 12,
            "watch_3s_rate_avg": 23.9,
            "carousel_swipe_rate_avg": 55.9,
            "fmt_er_carousel": 0.32,
            "fmt_er_reels": 0.10,
            "best_post_hours": [6, 7, 12, 18, 19],
            "recommended_formats": ["carousel", "reels"],
        },
    },

    # ── business ──────────────────────────────────────────────────────────────
    # 릴스 ER 0.055 > 캐러셀 0.022, 캡션 매우 짧음(med=37자)
    # 3초 리텐션 낮음(11.1%), 전환(문의/구매)이 KPI
    # → 전환 잠재력이 가장 중요한 카테고리
    "business": {
        "weights": {
            "title_quality": 0.20,        # 후킹: 짧은 캡션의 첫 줄이 전부
            "content_quality": 0.22,      # 핵심 정보+CTA
            "visual_quality": 0.08,       # 시각 비중 낮음 (아이디어/정보 중심)
            "tag_strategy": 0.08,
            "engagement_potential": 0.42, # 소상공인 최우선 KPI: 문의/전환
        },
        "title_length": {"min": 10, "max": 40, "viral_avg": 24.0},
        "content_length": {"min": 15, "max": 254},
        "tag_count": {"min": 2, "max": 6, "best": 4},
        "image_count": {"min": 1, "max": 10},
        "baseline": {
            "avg_engagement": 212,
            "median": 120,
            "viral_threshold": 1500,
            "sample_size": 12,
            "watch_3s_rate_avg": 11.1,
            "carousel_swipe_rate_avg": 53.0,
            "fmt_er_reels": 0.055,
            "fmt_er_carousel": 0.022,
            "best_post_hours": [9, 10, 12, 18, 19],
            "recommended_formats": ["reels", "carousel"],
        },
    },

    # ── lifestyle ─────────────────────────────────────────────────────────────
    # 캐러셀 ER 2.17 > 릴스 0.57 (캐러셀 4배 이상 우세) — 데이터 최고 ER
    # 3초 리텐션 최고(26.3%), 캡션 중간(med=104자)
    # → 공감+감성 후킹이 핵심, 저장율/공유율 매우 높음
    "lifestyle": {
        "weights": {
            "title_quality": 0.28,        # 공감 유발 첫 줄
            "content_quality": 0.20,      # 감성 스토리텔링
            "visual_quality": 0.18,       # 분위기 중요하지만 텍스트도 큰 역할
            "tag_strategy": 0.10,
            "engagement_potential": 0.24, # 저장+공유 유도
        },
        "title_length": {"min": 10, "max": 42, "viral_avg": 19.0},
        "content_length": {"min": 30, "max": 426},
        "tag_count": {"min": 3, "max": 7, "best": 5},
        "image_count": {"min": 1, "max": 10},
        "baseline": {
            "avg_engagement": 8720,
            "median": 5000,
            "viral_threshold": 35000,
            "sample_size": 12,
            "watch_3s_rate_avg": 26.3,
            "carousel_swipe_rate_avg": 63.0,
            "fmt_er_carousel": 2.17,
            "fmt_er_reels": 0.57,
            "best_post_hours": [12, 13, 19, 20, 21],
            "recommended_formats": ["carousel", "reels"],
        },
    },

    # ── travel ────────────────────────────────────────────────────────────────
    # 릴스 ER 0.10 > 캐러셀 0.04, 캡션 매우 길음(med=520자)
    # 3초 리텐션 중간(14.4%), 캐러셀 스와이프율 최고(66.5%)
    # → 정보+시각 혼합, 긴 캡션으로 저장 유도
    "travel": {
        "weights": {
            "title_quality": 0.22,
            "content_quality": 0.18,      # 긴 캡션이 효과적 (여행 정보)
            "visual_quality": 0.30,       # 풍경 사진이 핵심
            "tag_strategy": 0.12,         # 지역 해시태그 중요
            "engagement_potential": 0.18, # 저장(나중에 가볼 곳) 유도
        },
        "title_length": {"min": 10, "max": 48, "viral_avg": 23.0},
        "content_length": {"min": 80, "max": 932},
        "tag_count": {"min": 3, "max": 7, "best": 5},
        "image_count": {"min": 3, "max": 10},
        "baseline": {
            "avg_engagement": 403,
            "median": 250,
            "viral_threshold": 3000,
            "sample_size": 12,
            "watch_3s_rate_avg": 14.4,
            "carousel_swipe_rate_avg": 66.5,
            "fmt_er_reels": 0.10,
            "fmt_er_carousel": 0.04,
            "best_post_hours": [11, 12, 19, 20, 21],
            "recommended_formats": ["reels", "carousel"],
        },
    },

    # ── education ─────────────────────────────────────────────────────────────
    # 캐러셀 ER 0.21 > 릴스 0.06, 캡션 매우 길음(med=430자)
    # 3초 리텐션 중간(13.7%), 캐러셀 스와이프율 좋음(59%)
    # → 정보 밀도+구조가 최우선, 저장률이 핵심 KPI
    "education": {
        "weights": {
            "title_quality": 0.20,        # 후킹: 호기심/실용성 어필
            "content_quality": 0.35,      # 정보 밀도: 교육 카테고리 최우선
            "visual_quality": 0.10,       # 인포그래픽 수준이면 충분
            "tag_strategy": 0.10,
            "engagement_potential": 0.25, # 저장각 콘텐츠 → 저장률 높음
        },
        "title_length": {"min": 12, "max": 50, "viral_avg": 28.0},
        "content_length": {"min": 100, "max": 646},
        "tag_count": {"min": 2, "max": 6, "best": 4},
        "image_count": {"min": 1, "max": 12},
        "baseline": {
            "avg_engagement": 1083,
            "median": 600,
            "viral_threshold": 8000,
            "sample_size": 12,
            "watch_3s_rate_avg": 13.7,
            "carousel_swipe_rate_avg": 59.0,
            "fmt_er_carousel": 0.21,
            "fmt_er_reels": 0.06,
            "best_post_hours": [7, 8, 12, 19, 20],
            "recommended_formats": ["carousel"],
        },
    },

    # ── shop ──────────────────────────────────────────────────────────────────
    # 캐러셀 ER 0.24 > 릴스 0.01 (캐러셀이 압도적)
    # 3초 리텐션 낮음(11.1%), 캐러셀 스와이프율 낮음(43.9%)
    # → 제품 신뢰도+구매 전환이 핵심
    "shop": {
        "weights": {
            "title_quality": 0.24,        # 첫 컷에서 제품 어필
            "content_quality": 0.16,      # 솔직 후기 + 구매 CTA
            "visual_quality": 0.26,       # 제품 사진 퀄리티
            "tag_strategy": 0.08,
            "engagement_potential": 0.26, # 구매 전환+저장 유도
        },
        "title_length": {"min": 10, "max": 40, "viral_avg": 22.0},
        "content_length": {"min": 60, "max": 221},
        "tag_count": {"min": 2, "max": 5, "best": 3},
        "image_count": {"min": 1, "max": 10},
        "baseline": {
            "avg_engagement": 1003,
            "median": 300,
            "viral_threshold": 8000,
            "sample_size": 12,
            "watch_3s_rate_avg": 11.1,
            "carousel_swipe_rate_avg": 43.9,
            "fmt_er_carousel": 0.24,
            "fmt_er_reels": 0.01,
            "best_post_hours": [10, 11, 19, 20, 21],
            "recommended_formats": ["carousel"],
        },
    },
}

# 카테고리 한국어명
CATEGORY_KR = {
    "food": "맛집/카페",
    "fashion": "패션/뷰티",
    "fitness": "운동/건강",
    "business": "사업/마케팅",
    "lifestyle": "일상/육아",
    "travel": "여행",
    "education": "정보/교육",
    "shop": "쇼핑/리뷰",
}



# =============================================================================
# 특징 추출 유틸
# =============================================================================

def _detect_emoji(text: str) -> bool:
    return bool(re.search(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        r"\U0001F900-\U0001F9FF\U00002702-\U000027B0\u2728\U0001F525\U0001F49A\u203C\u2B50]",
        text or "",
    ))


def _count_hooks(text: str) -> int:
    """캡션 첫 줄의 후킹 요소 개수를 센다."""
    hooks = 0
    if re.search(r'\d+', text): hooks += 1                              # 숫자
    if re.search(r'[!?]{2,}|[！？]{2,}', text): hooks += 1             # 강조 부호
    if re.search(r'[\U0001F525\u2728\u203C\u2B50\U0001F4AF]', text): hooks += 1  # 강조 이모지
    if re.search(r'(진짜|꼭|무조건|대박|미쳤|레전드|역대급|충격|꿀팁|솔직)', text): hooks += 1  # 한국어 후킹어
    if re.search(r'(저장|DM|댓글|팔로우)', text): hooks += 1            # CTA
    return hooks


def _range_score(value: float, opt_min: float, opt_max: float, base: float = 80) -> float:
    """값이 최적 범위 내에 있을수록 높은 점수."""
    if opt_min <= value <= opt_max:
        mid = (opt_min + opt_max) / 2
        half = (opt_max - opt_min) / 2 + 1
        return base + (100 - base) * (1 - abs(value - mid) / half)
    elif value < opt_min:
        return max(20, base * value / max(opt_min, 1))
    else:
        return max(40, base - (value - opt_max) * 2)


# =============================================================================
# Model A 사전 평가 (LLM 없이 <50ms)
# pre_score(title, content, category, tag_count, image_count)
# =============================================================================

def pre_score(
    title: str,
    content: str,
    category: str,
    tag_count: int = 0,
    image_count: int = 0,
) -> dict:
    """
    Model A 사전 평가.
    인스타 맥락: title → 캡션 첫 줄, content → 캡션 본문.
    """
    p = MODEL_PARAMS.get(category, MODEL_PARAMS["lifestyle"])
    w = p["weights"]

    # 캡션 전체 (첫 줄 + 본문)
    caption = (title + "\n" + content).strip() if content else title
    first_line = title or caption.split("\n")[0]

    # ── title_quality (후킹력) ──────────────────────────────────────────────
    tl = p["title_length"]
    hook_score = _range_score(len(first_line), tl["min"], tl["max"])
    hook_score += min(_count_hooks(first_line), 3) * 8
    if _detect_emoji(first_line):
        hook_score += 4
    hook_score = min(hook_score, 100)

    # ── content_quality (캡션 품질) ────────────────────────────────────────
    cl = p["content_length"]
    content_score = min(_range_score(len(caption), cl["min"], cl["max"], 85), 100)
    if re.search(r'(저장|DM|댓글|팔로우|링크|프로필|문의)', caption):
        content_score += 5
    if caption.count("\n") >= 2:
        content_score += 5
    content_score = min(content_score, 100)

    # ── visual_quality (이미지 수 기반) ────────────────────────────────────
    ic = p["image_count"]
    visual_score = min(_range_score(image_count, ic["min"], ic["max"]), 100)

    # ── tag_strategy (해시태그) ────────────────────────────────────────────
    tc = p["tag_count"]
    tag_score = max(0, 100 - abs(tag_count - tc["best"]) * 15)
    if tag_count == 0:
        tag_score = max(tag_score, 25)
    elif tag_count > 15:
        tag_score = max(15, tag_score - (tag_count - 15) * 5)

    # ── engagement_potential (전환 잠재력) ─────────────────────────────────
    eng_score = 40.0
    if re.search(r'(링크|프로필|DM|주문|예약|구매|할인|무료|이벤트)', caption):
        eng_score += 20
    if re.search(r'(후기|리뷰|솔직|사용기|비교)', caption):
        eng_score += 15
    if re.search(r'(어디|가격|얼마|위치|매장|정보)', caption):
        eng_score += 10
    if re.search(r'\d+[만원%]+', caption):
        eng_score += 10
    if len(first_line) > 5:
        eng_score += 5
    eng_score = min(eng_score, 100)

    dims = {
        "title_quality": round(hook_score, 1),
        "content_quality": round(content_score, 1),
        "visual_quality": round(visual_score, 1),
        "tag_strategy": round(tag_score, 1),
        "engagement_potential": round(eng_score, 1),
    }

    total = min(round(sum(dims[k] * w[k] for k in w), 1), 100)

    bl = p["baseline"]
    if total >= 85:
        level = "상위 10% (바이럴 가능성 높음)"
    elif total >= 75:
        level = "상위 25% (우수 콘텐츠)"
    elif total >= 65:
        level = "중위 수준"
    else:
        level = "중위 이하, 개선 권장"

    return {
        "total_score": total,
        "dimensions": dims,
        "weights": w,
        "level": level,
        "baseline": bl,
        "category": category,
        "category_kr": CATEGORY_KR.get(category, category),
    }


# =============================================================================
# 에이전트용 데이터 기반 프롬프트 조각
# =============================================================================

def build_data_prompt_for_agent(agent_type: str, category: str, content_format: str = "single_image") -> str:
    """
    에이전트와 카테고리에 맞는 데이터 기반 프롬프트 조각을 생성한다.
    시스템 프롬프트 뒤에 이어 붙인다.
    """
    p = MODEL_PARAMS.get(category, MODEL_PARAMS["lifestyle"])
    w = p["weights"]
    bl = p["baseline"]
    kr = CATEGORY_KR.get(category, category)
    hours = ", ".join(f"{h}시" for h in bl["best_post_hours"])
    rec_fmts = bl.get("recommended_formats", ["carousel"])
    rec_fmt_str = " > ".join(f"{f}(ER {bl.get(f'fmt_er_{f}', '?'):.3f})" if bl.get(f'fmt_er_{f}') else f for f in rec_fmts)

    viral = VIRAL_TITLES.get(category, VIRAL_TITLES.get("lifestyle", []))
    comments = REAL_COMMENTS.get(category, REAL_COMMENTS.get("lifestyle", []))

    if agent_type == "content":
        viral_str = " / ".join(f'"{t}"' for t in viral[:3])
        return (
            f"\n\n## 실제 데이터 기반 진단 기준 ({kr}, n={bl['sample_size']})\n"
            f"- 캡션 최적 길이: {p['content_length']['min']}-{p['content_length']['max']}자\n"
            f"- 캡션 품질 가중치: {w['content_quality']:.0%} (5개 차원 중 {'최우선' if w['content_quality'] >= 0.30 else '중요'})\n"
            f"- 캡션 첫 125자는 '더 보기' 클릭 전 노출 — 이 안에 핵심을 담아야 함\n"
            f"- 권장 포맷: {rec_fmt_str}\n"
            f"- 평균 인게이지먼트: {bl['avg_engagement']:,}회, 바이럴 기준: {bl['viral_threshold']:,}회\n"
            f"\n**바이럴 캡션 참고** (이 톤+문체로 개선안 작성):\n{viral_str}\n"
        )

    elif agent_type == "visual":
        w3s = bl.get("watch_3s_rate_avg")
        swipe = bl.get("carousel_swipe_rate_avg")
        return (
            f"\n\n## 실제 데이터 기반 진단 기준 ({kr})\n"
            f"- 이미지 최적 수: {p['image_count']['min']}-{p['image_count']['max']}장\n"
            f"- 시각 품질 가중치: {w['visual_quality']:.0%}"
            f"{'  (패션: 시각이 전부 — 텍스트 영향력 R²≈0.02)' if category == 'fashion' else ''}\n"
            + (f"- 릴스 평균 3초 리텐션: {w3s:.1f}% (60% 이상이면 도달 범위 5-10배)\n" if w3s else "")
            + (f"- 캐러셀 평균 스와이프율: {swipe:.1f}% (높을수록 장수 콘텐츠 효과적)\n" if swipe else "")
            + f"- 색 대비 높은 첫 이미지가 스크롤 저지력을 크게 높임\n"
        )

    elif agent_type == "growth":
        er_carousel = bl.get("fmt_er_carousel", 0)
        er_reels = bl.get("fmt_er_reels", 0)
        fmt_insight = f"캐러셀(ER {er_carousel:.3f}) > 릴스(ER {er_reels:.3f})" if er_carousel > er_reels \
                      else f"릴스(ER {er_reels:.3f}) > 캐러셀(ER {er_carousel:.3f})"
        return (
            f"\n\n## 실제 데이터 기반 진단 기준 ({kr})\n"
            f"- 해시태그 최적 수: {p['tag_count']['min']}-{p['tag_count']['max']}개 (최적 {p['tag_count']['best']}개)\n"
            f"  릴스 3-5개, 피드/캐러셀 5-7개 최적 (2026 기준)\n"
            f"  5개 초과 시 알고리즘이 '저의도 콘텐츠'로 분류 위험\n"
            f"- 해시태그 전략 가중치: {w['tag_strategy']:.0%}\n"
            f"- 최적 게시 시간: {hours}\n"
            f"- 포맷 ER 비교 ({kr} 실측): {fmt_insight}\n"
            f"- 권장 포맷 순위: {' > '.join(rec_fmts)}\n"
        )

    elif agent_type == "user_sim":
        comments_str = "\n".join(f'  - "{c}"' for c in comments[:4])
        return (
            f"\n\n## 한국 인스타 오디언스 데이터 ({kr})\n"
            f"- 한국 인스타 유저 유형: 정보추구형/공감형/의심형(광고 아님?)/구경형/구매의향형/불만형\n"
            f"- 저장과 공유가 좋아요보다 알고리즘 가중치 3배 (2026 기준)\n"
            f"- {'패션은 짧은 감탄+사이즈 질문 댓글 많음' if category == 'fashion' else '맛집은 위치/가격 질문이 핵심' if category == 'food' else '교육 콘텐츠는 저장+감사 댓글 비중 높음' if category == 'education' else '일반 한국 인스타 댓글 패턴 따름'}\n"
            f"\n**한국 인스타 실제 댓글 톤 참고**:\n{comments_str}\n"
            f"댓글은 자연스러운 한국어. 이모지·줄임말·ㅋㅋ/ㅠㅠ·구어체를 사용하고 AI 투 금지."
        )

    elif agent_type == "judge":
        w_str = ", ".join(f"{k}({v:.0%})" for k, v in sorted(w.items(), key=lambda x: -x[1]))
        viral_str = " / ".join(f'"{t}"' for t in viral[:3])
        er_carousel = bl.get("fmt_er_carousel", 0)
        er_reels = bl.get("fmt_er_reels", 0)
        return (
            f"\n\n## 실제 데이터 기반 평가 기준 ({kr}, n={bl['sample_size']})\n"
            f"- 평가 가중치 우선순위: {w_str}\n"
            f"- 평균 인게이지먼트: {bl['avg_engagement']:,}회, 바이럴 기준: {bl['viral_threshold']:,}회\n"
            f"- 포맷별 실측 ER: 캐러셀={er_carousel:.3f}, 릴스={er_reels:.3f}\n"
            f"- 권장 포맷: {' > '.join(rec_fmts)}, 최적 게시 시간: {hours}\n"
            f"\n**바이럴 캡션 참고** (개선안 작성 시 이 톤):\n{viral_str}\n"
            f"- optimized_title(개선 캡션 첫 줄)은 한국 인스타 인기 게시물처럼: 구어체, 감정, 호기심 유발\n"
            f"- optimized_content(개선 캡션 본문)은 짧은 단락, 이모지 구분, 결말 CTA\n"
            f"- 가중치에 따라 총점 산출 후 바이럴 기준과 비교 필수"
        )

    return ""
