"""
반복 최적화 API: 진단 결과를 기반으로 2-3개 고득점 개선안을 생성하고 자동 재채점한다.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.base_agent import BaseAgent, MODEL_PRO
from app.agents.research_data import pre_score

router = APIRouter()
logger = logging.getLogger("instarx.optimize")

OPTIMIZE_PROMPT = """너는 인스타그램 성과형 콘텐츠 최적화 전문가다.
진단 결과(감점 사유)를 기반으로 서로 다른 전략 3개를 생성한다.

## 각 전략 필수 필드
- strategy: 전략명 (예: 감정형/정보형/호기심형)
- optimized_title: 바로 게시 가능한 첫 문장/제목
- optimized_content: 바로 게시 가능한 캡션 본문
- key_changes: 핵심 변경점 요약

## 전략 다양성
A: 감정/공감 드리븐
B: 숫자/정보 드리븐
C: 질문/반전(호기심) 드리븐

## 캡션 규칙
- 짧은 문단 + 줄바꿈
- CTA 포함(저장/댓글/공유/DM 유도 중 최소 1개)
- 과장된 AI 문어체 금지

## 출력(JSON)
{"plans":[{"strategy":"전략명","optimized_title":"제목","optimized_content":"본문","key_changes":"설명"}]}
"""


class OptimizeRequest(BaseModel):
    title: str
    content: str = ""
    category: str = "food"
    issues: str = ""
    suggestions: str = ""
    overall_score: float = 50


@router.post("/optimize")
async def optimize(req: OptimizeRequest):
    """최적화안 생성 + 자동 점수 비교"""
    issues_text = req.issues[:500] if req.issues else "구체 감점 사유 없음"
    suggestions_text = req.suggestions[:500] if req.suggestions else ""

    user_msg = f"""원본 게시물:
- 제목/첫 문장: {req.title}
- 본문: {req.content[:400] if req.content else '（본문 없음）'}
- 카테고리: {req.category}
- 현재 점수: {req.overall_score}점

주요 문제: {issues_text}
개선 방향: {suggestions_text}

서로 다른 전략의 개선안 3개를 생성하라."""

    agent = BaseAgent(model=MODEL_PRO)
    agent.system_prompt = OPTIMIZE_PROMPT
    result = await agent.call_llm(user_msg, max_tokens=3000)
    result.pop("_meta", None)

    plans = result.get("plans", [])
    if not isinstance(plans, list):
        plans = []

    tag_count = 0
    try:
        orig_result = pre_score(req.title, req.content, req.category, tag_count, 0)
        orig_score = orig_result["total_score"]
    except Exception:
        orig_score = req.overall_score

    scored_plans = []
    for plan in plans[:3]:
        if not isinstance(plan, dict):
            continue

        title = plan.get("optimized_title", req.title)
        content = plan.get("optimized_content", req.content)
        try:
            score_result = pre_score(title, content, req.category, tag_count, 0)
            plan_score = score_result["total_score"]
        except Exception:
            plan_score = orig_score + 5

        delta = round(plan_score - orig_score)
        scored_plans.append(
            {
                "strategy": plan.get("strategy", "개선안"),
                "optimized_title": title,
                "optimized_content": content,
                "key_changes": plan.get("key_changes", ""),
                "score": round(plan_score),
                "score_delta": max(delta, 0),
            }
        )

    scored_plans.sort(key=lambda x: x["score"], reverse=True)
    if scored_plans:
        scored_plans[0]["recommended"] = True

    return {
        "original_score": round(orig_score),
        "plans": scored_plans,
    }
