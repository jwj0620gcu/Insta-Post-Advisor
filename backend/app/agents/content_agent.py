"""
콘텐츠 분석 Agent
문구 구조, 정보 밀도, 가독성을 분석한다.
"""
import json

from app.agents.base_agent import BaseAgent
from app.agents.prompts.content_agent import SYSTEM_PROMPT
from app.agents.research_data import build_data_prompt_for_agent


class ContentAgent(BaseAgent):
    """게시물 문구 품질 분석"""

    agent_name = "후킹 전문가"
    system_prompt = SYSTEM_PROMPT

    def build_user_message(
        self,
        title: str,
        content: str,
        category: str,
        title_analysis: dict,
        content_analysis: dict,
        baseline_comparison: dict,
    ) -> str:
        """게시물/분석값/Baseline을 포함한 메시지를 생성한다."""
        comparisons = baseline_comparison.get("comparisons", {})

        msg = f"""## 진단 대상 인스타 게시물
- **카테고리**: {category}
- **제목/첫 문장**: {title}
- **캡션 본문**: {content if content else '（본문 없음）'}

## 제목 분석 데이터
- 글자 수: {title_analysis.get('length', 0)}
- 키워드: {json.dumps(title_analysis.get('keywords', []), ensure_ascii=False)}
- 감정어: {json.dumps(title_analysis.get('emotion_words', []), ensure_ascii=False)}
- 후킹 요소 수: {title_analysis.get('hook_count', 0)}

## 본문 분석 데이터
- 글자 수: {content_analysis.get('length', 0)}
- 문단 수: {content_analysis.get('paragraph_count', 0)}
- 평균 문장 길이: {content_analysis.get('avg_sentence_length', 0)}
- 가독성 점수: {content_analysis.get('readability_score', 0)}
- 정보 밀도: {content_analysis.get('info_density', 0)}

## Baseline 비교 ({category})
- 바이럴 평균 제목 길이: {comparisons.get('title_length', {}).get('viral_avg', 'N/A')}
- 카테고리 평균 제목 길이: {comparisons.get('title_length', {}).get('category_avg', 'N/A')}
- 길이 판정: {comparisons.get('title_length', {}).get('verdict', 'N/A')}

위 데이터를 기준으로 인스타그램 맥락의 실행형 진단을 작성하세요."""
        msg += build_data_prompt_for_agent("content", category)
        return msg

    async def diagnose(self, **kwargs) -> dict:
        """콘텐츠 진단 실행"""
        msg = self.build_user_message(**kwargs)
        return await self.call_llm(msg)
