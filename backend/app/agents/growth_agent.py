"""
트렌드 에이전트
지금 한국 인스타그램에서 바이럴되는 콘텐츠 패턴과의 적합도를 분석한다.
"""
from __future__ import annotations

import json

from app.agents.base_agent import BaseAgent
from app.agents.prompts.growth_agent import SYSTEM_PROMPT
from app.agents.research_data import build_data_prompt_for_agent, MODEL_PARAMS


class GrowthAgent(BaseAgent):
    """인스타그램 트렌드 적합성 분석"""

    agent_name = "트렌드 에이전트"
    system_prompt = SYSTEM_PROMPT

    def build_user_message(
        self,
        title: str,
        content: str,
        category: str,
        tags: list[str],
        baseline_comparison: dict,
    ) -> str:
        """카테고리 트렌드 데이터 기반 메시지 생성"""
        comparisons = baseline_comparison.get("comparisons", {})
        params = MODEL_PARAMS.get(category, {})
        baseline = params.get("baseline", {})

        recommended_formats = baseline.get("recommended_formats", [])
        fmt_er_carousel = baseline.get("fmt_er_carousel", "N/A")
        fmt_er_reels = baseline.get("fmt_er_reels", "N/A")
        watch_3s = baseline.get("watch_3s_rate_avg", "N/A")
        best_hours = baseline.get("best_post_hours", [])

        tag_rel = comparisons.get("tag_relevance", {})
        top_tags = tag_rel.get("top_tags_in_category", [])

        msg = f"""## 진단 대상 인스타 게시물
- **카테고리**: {category}
- **제목/첫 문장**: {title}
- **본문 요약**: {content[:200] if content else '（본문 없음）'}
- **사용 해시태그**: {json.dumps(tags, ensure_ascii=False)}

## 이 카테고리 트렌드 벤치마크
- 추천 포맷: {recommended_formats}
- 캐러셀 평균 ER: {fmt_er_carousel} / 릴스 평균 ER: {fmt_er_reels}
- 릴스 첫 3초 리텐션 평균: {watch_3s}%
- 최적 게시 시간대: {best_hours}
- 카테고리 인기 해시태그 Top10: {json.dumps(top_tags, ensure_ascii=False)}

위 트렌드 데이터를 기준으로, 이 게시물이 지금 한국 인스타 트렌드를 타고 있는지 진단하세요.
포맷 선택, 콘텐츠 패턴, 키워드 트렌드 관점에서 구체적으로 분석하세요."""
        msg += build_data_prompt_for_agent("growth", category)
        return msg

    async def diagnose(self, **kwargs) -> dict:
        """트렌드 진단 실행"""
        msg = self.build_user_message(**kwargs)
        return await self.call_llm(msg)
