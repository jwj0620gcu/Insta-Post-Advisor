"""
시뮬레이션 댓글 생성 API
flash 모델로 인스타 반응(댓글/답글/논쟁)을 빠르게 생성한다.
"""
import logging
import os
import random

from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.base_agent import BaseAgent, MODEL_FAST

router = APIRouter()
logger = logging.getLogger("insta-advisor.comments")

COMMENT_PROMPT = """너는 인스타그램 댓글 시뮬레이터다. 한국 인스타 댓글 톤으로 생성한다.

## 핵심 규칙
- AI 티 나는 문어체 금지
- 실제 사용자 말투 사용(짧은 반응, 질문, 경험 공유, 의심/반박)
- 칭찬만 하지 말고 일부 비판/의심도 포함

## 생성 규칙
1. 짧은 댓글/중간 댓글/긴 댓글을 혼합
2. 최소 1개 의심/비판 댓글 포함
3. 최소 2개는 replies(대댓글) 포함
4. 각 댓글 필드: username, comment, sentiment, likes, time_ago, ip_location
5. 필요시 is_author=true 작성자 댓글 1개 허용

## JSON 형식
{"comments":[{"username":"닉네임","comment":"내용","sentiment":"positive/negative/neutral","likes":12,"time_ago":"3시간 전","ip_location":"서울","is_author":false,"replies":[동일 구조]}]}

주댓글 5-6개, 그중 2-3개는 replies 포함."""


class GenerateCommentsRequest(BaseModel):
    title: str
    content: str = ""
    category: str = "food"
    existing_count: int = 0


def _fallback_comments(req: GenerateCommentsRequest) -> list[dict]:
    """LLM 실패/쿼터 초과 시 사용할 기본 댓글 샘플."""
    seed = abs(hash((req.title[:50], req.category, req.existing_count))) % (2**32)
    rng = random.Random(seed)

    category_hint = {
        "food": "맛집 포인트",
        "fashion": "스타일 포인트",
        "tech": "기능 포인트",
        "travel": "여행 포인트",
        "beauty": "뷰티 포인트",
        "fitness": "운동 포인트",
        "business": "운영 포인트",
        "lifestyle": "일상 포인트",
        "education": "정보 포인트",
        "shop": "구매 포인트",
    }.get(req.category, "핵심 포인트")
    t = (req.title or "이 게시물").strip()[:30]
    prefix = f"{t} {category_hint}".strip()

    base = [
        {
            "username": "햇살유저",
            "comment": f"{prefix}가 확실하네요. 저장하고 참고할게요!",
            "sentiment": "positive",
            "likes": rng.randint(6, 24),
            "time_ago": "방금",
            "ip_location": "서울",
            "is_author": False,
            "replies": [
                {
                    "username": "질문러",
                    "comment": "혹시 초보도 따라 할 수 있나요?",
                    "sentiment": "neutral",
                    "likes": rng.randint(0, 9),
                    "time_ago": "방금",
                    "ip_location": "경기",
                    "is_author": False,
                }
            ],
        },
        {
            "username": "솔직후기",
            "comment": "좋아 보이는데 실제 체감은 어떨지 궁금해요.",
            "sentiment": "neutral",
            "likes": rng.randint(2, 12),
            "time_ago": "2분 전",
            "ip_location": "인천",
            "is_author": False,
            "replies": [],
        },
        {
            "username": "팩폭장인",
            "comment": "광고 느낌이 좀 있어서 근거를 더 보여주면 좋겠어요.",
            "sentiment": "negative",
            "likes": rng.randint(1, 8),
            "time_ago": "4분 전",
            "ip_location": "대전",
            "is_author": False,
            "replies": [
                {
                    "username": "햇살유저",
                    "comment": "저는 꽤 도움이 됐어요. 관점 차이인 듯!",
                    "sentiment": "neutral",
                    "likes": rng.randint(0, 7),
                    "time_ago": "3분 전",
                    "ip_location": "서울",
                    "is_author": False,
                }
            ],
        },
        {
            "username": "메모중",
            "comment": "핵심만 짧게 정리해줘서 보기 편하네요.",
            "sentiment": "positive",
            "likes": rng.randint(4, 18),
            "time_ago": "6분 전",
            "ip_location": "부산",
            "is_author": False,
            "replies": [],
        },
        {
            "username": "궁금해요",
            "comment": "다음에는 비교 사례도 같이 올려주세요!",
            "sentiment": "neutral",
            "likes": rng.randint(1, 10),
            "time_ago": "9분 전",
            "ip_location": "광주",
            "is_author": False,
            "replies": [],
        },
    ]
    return base


@router.post("/generate-comments")
async def generate_comments(req: GenerateCommentsRequest):
    """flash 모델로 추가 시뮬레이션 댓글 생성"""
    category_names = {
        "food": "맛집/카페",
        "fashion": "패션/뷰티",
        "tech": "테크",
        "travel": "여행",
        "beauty": "뷰티",
        "fitness": "운동/건강",
        "business": "사업/마케팅",
        "lifestyle": "일상",
        "education": "정보/교육",
        "shop": "쇼핑/리뷰",
    }
    cat_name = category_names.get(req.category, req.category)

    user_msg = f"""게시물 정보:
- 카테고리: {cat_name}
- 제목: {req.title}
- 본문: {req.content[:300] if req.content else '（본문 없음）'}

기존 댓글은 {req.existing_count}개다. 중복 없이 새로운 댓글을 만들어라.
이미 댓글이 많다면 일부는 논쟁형/반박형 replies로 구성해라."""

    comments: list = []
    try:
        agent = BaseAgent(model=MODEL_FAST)
        agent.system_prompt = COMMENT_PROMPT
        max_tokens = int(os.getenv("COMMENTS_MAX_TOKENS", "1200"))
        result = await agent.call_llm(user_msg, max_tokens=max(256, min(max_tokens, 2000)))
        result.pop("_meta", None)
        comments = result.get("comments", [])
    except Exception as e:
        logger.warning("generate-comments failed, fallback comments used: %s", e)
        comments = []
    if not isinstance(comments, list) or not comments:
        comments = _fallback_comments(req)

    formatted = []
    for c in comments:
        if not isinstance(c, dict):
            continue

        replies = []
        for r in c.get("replies", []):
            if isinstance(r, dict):
                replies.append(
                    {
                        "username": r.get("username", "인스타 유저"),
                        "comment": r.get("comment", ""),
                        "sentiment": r.get("sentiment", "neutral"),
                        "likes": int(r.get("likes", 0)) if r.get("likes") is not None else 0,
                        "time_ago": r.get("time_ago", "방금"),
                        "ip_location": r.get("ip_location", ""),
                        "is_author": bool(r.get("is_author", False)),
                    }
                )

        formatted.append(
            {
                "username": c.get("username", "인스타 유저"),
                "comment": c.get("comment", ""),
                "sentiment": c.get("sentiment", "neutral"),
                "likes": int(c.get("likes", 0)) if c.get("likes") is not None else 0,
                "time_ago": c.get("time_ago", "방금"),
                "ip_location": c.get("ip_location", ""),
                "is_author": bool(c.get("is_author", False)),
                "replies": replies,
            }
        )

    return {"comments": formatted}
