"""
오디언스 시뮬레이터 Agent
인스타그램 한국 유저의 첫 반응과 댓글을 시뮬레이션한다.
"""
from __future__ import annotations

import json

from app.agents.base_agent import BaseAgent
from app.agents.prompts.user_sim_agent import SYSTEM_PROMPT
from app.agents.research_data import build_data_prompt_for_agent, CATEGORY_KR


class UserSimAgent(BaseAgent):
    """한국 인스타 유저 반응 및 댓글 시뮬레이션"""

    agent_name = "인스타 중독 유저"
    system_prompt = SYSTEM_PROMPT

    def build_user_message(
        self,
        title: str,
        content: str,
        category: str,
        tags: list[str],
    ) -> str:
        """시뮬레이션할 게시물 정보 구성"""
        cat_kr = CATEGORY_KR.get(category, category)

        msg = f"""## 진단 대상 인스타 게시물
- **카테고리**: {cat_kr}
- **제목/첫 문장**: {title}
- **해시태그**: {json.dumps(tags, ensure_ascii=False)}
- **캡션 본문**:
{content if content else '（본문 없음 — 제목과 커버만 있는 게시물）'}

한국 인스타그램 사용자 유형별로 이 {cat_kr} 게시물을 보았을 때의 반응을 시뮬레이션하고,
실제 댓글 스타일로 댓글 5~8개를 생성하세요."""
        msg += build_data_prompt_for_agent("user_sim", category)
        return msg

    async def diagnose(self, **kwargs) -> dict:
        """오디언스 시뮬레이션 실행"""
        msg = self.build_user_message(**kwargs)
        return await self.call_llm(msg)
