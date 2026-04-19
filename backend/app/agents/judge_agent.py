"""
종합 심사관 Agent
모든 에이전트 의견을 통합해 최종 진단 보고서를 생성한다.
"""
from __future__ import annotations

import json
import os

from app.agents.base_agent import BaseAgent
from app.agents.prompts.judge_agent import SYSTEM_PROMPT
from app.agents.research_data import build_data_prompt_for_agent


class JudgeAgent(BaseAgent):
    """종합 심사관 — 최종 진단 보고서 생성"""

    agent_name = "종합 심사관"
    system_prompt = SYSTEM_PROMPT

    def build_user_message(
        self,
        title: str,
        category: str,
        agent_opinions: list[dict],
        debate_records: list[dict] | None = None,
    ) -> str:
        """모든 에이전트 의견 취합"""
        opinions_text = ""
        for i, op in enumerate(agent_opinions, 1):
            opinions_text += f"""
### 전문가 {i}: {op.get('agent_name', 'Unknown')}
- **평가 차원**: {op.get('dimension', '')}
- **점수**: {op.get('score', 0)}
- **문제점**: {json.dumps(op.get('issues', []), ensure_ascii=False)}
- **개선안**: {json.dumps(op.get('suggestions', []), ensure_ascii=False)}
- **판단 근거**: {op.get('reasoning', '')}
"""

        debate_text = ""
        if debate_records:
            debate_text = "\n## 전문가 토론 기록\n"
            for record in debate_records:
                debate_text += f"""
**{record.get('agent_name', '')}의 토론 의견:**
- 동의: {json.dumps(record.get('agreements', []), ensure_ascii=False)}
- 반박: {json.dumps(record.get('disagreements', []), ensure_ascii=False)}
- 보완: {json.dumps(record.get('additions', []), ensure_ascii=False)}
"""

        msg = f"""## 진단 대상 인스타 게시물
- **카테고리**: {category}
- **제목/첫 문장**: {title}

## 각 전문가 진단 의견
{opinions_text}
{debate_text}

위 모든 전문가 의견과 토론 기록을 종합하여 최종 진단 보고서를 작성하세요."""
        msg += build_data_prompt_for_agent("judge", category)
        return msg

    async def diagnose(self, **kwargs) -> dict:
        """종합 심사 실행 (JSON이 길어 최대 토큰 확보)"""
        msg = self.build_user_message(**kwargs)
        return await self.call_llm(
            msg,
            max_tokens=int(os.getenv("JUDGE_MAX_COMPLETION_TOKENS", "6144")),
        )
