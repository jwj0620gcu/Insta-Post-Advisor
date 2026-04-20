"""
Step 9: 강화된 Agent 프롬프트 생성
Model A (평가 파라미터) + Model B (사용자 페르소나)를 기반으로 데이터 기반 프롬프트를 생성합니다.

Usage:
    python scripts/research/09_generate_prompts.py
"""
from __future__ import annotations

import json
import asyncio
import sys
from pathlib import Path

import httpx
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).parent))
from config import OUTPUT_DIR, LLM_DIR, API_KEY, API_BASE, MODEL_PRO, ALL_CATEGORIES


def get_client() -> AsyncOpenAI:
    http_client = httpx.AsyncClient(proxy=None, trust_env=False, timeout=httpx.Timeout(180.0, connect=30.0))
    return AsyncOpenAI(api_key=API_KEY, base_url=API_BASE, http_client=http_client)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


PROMPT_GEN_TEMPLATE = """당신은 AI 시스템 설계 전문가입니다. 아래 데이터 연구 성과를 바탕으로 Instagram 게시글 진단 시스템의 각 Agent에 최적화된 프롬프트 조각을 생성하세요.

## 데이터 연구 성과 ({category} 카테고리)

### 정량 평가 파라미터
{scoring_params}

### 콘텐츠 패턴 발견
{content_patterns}

### 사용자 페르소나 (있을 경우)
{personas}

## 요구사항

아래 5개 Agent에 대해 각각 「데이터 주입 프롬프트」(200-300자)를 생성하세요. 기존 system prompt 뒤에 이어 붙여 Agent의 진단 정확도를 높이는 데 활용됩니다:

1. **ContentAgent (콘텐츠 분석가)**: 제목 패턴, 콘텐츠 구조, 최적 파라미터 주입
2. **VisualAgent (비주얼 진단가)**: 커버 스타일 분포, 최적 비주얼 파라미터 주입
3. **GrowthAgent (성장 전략가)**: 태그 전략, 게시 시간대, 인터랙션 데이터 주입
4. **UserSimAgent (사용자 시뮬레이터)**: 사용자 페르소나, 댓글 스타일 템플릿 주입
5. **JudgeAgent (종합 심판)**: 평가 가중치, 기준선 데이터 주입

JSON으로 출력:
{{
  "content_agent_data_prompt": "...",
  "visual_agent_data_prompt": "...",
  "growth_agent_data_prompt": "...",
  "user_sim_agent_data_prompt": "...",
  "judge_agent_data_prompt": "..."
}}
"""


async def main():
    print("=" * 60)
    print("Step 9: 강화된 Agent 프롬프트 생성")
    print("=" * 60)

    model_a = load_json(OUTPUT_DIR / "model_a_scoring.json")
    personas = load_json(LLM_DIR / "user_personas.json")

    if not model_a:
        print("Model A를 찾을 수 없습니다. 먼저 08_build_scoring_model.py를 실행하세요.")
        return

    client = get_client()
    all_prompts = {}

    for cat in ALL_CATEGORIES:
        if cat not in model_a:
            continue

        scoring = model_a[cat]
        cat_personas = personas.get(cat, {})

        prompt = PROMPT_GEN_TEMPLATE.format(
            category=cat,
            scoring_params=json.dumps(scoring, ensure_ascii=False, indent=1)[:2000],
            content_patterns=json.dumps({
                "title_patterns": scoring.get("title_patterns", []),
                "content_structure": scoring.get("content_structure", []),
                "top_tags": scoring.get("top_tags", []),
            }, ensure_ascii=False, indent=1),
            personas=json.dumps(cat_personas, ensure_ascii=False, indent=1)[:1500] if cat_personas else "댓글 데이터 없음",
        )

        print(f"  [{cat}] 프롬프트 생성 중...")
        try:
            response = await client.chat.completions.create(
                model=MODEL_PRO,
                messages=[
                    {"role": "system", "content": "당신은 AI 시스템 설계 전문가입니다. JSON만 출력하세요."},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=3000,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(raw)
            all_prompts[cat] = result
            print(f"    {len(result)}개 Agent 프롬프트 생성")
        except Exception as e:
            print(f"    실패: {e}")

    out = OUTPUT_DIR / "enhanced_agent_prompts.json"
    out.write_text(json.dumps(all_prompts, ensure_ascii=False, indent=2))
    print(f"\n프롬프트 저장 완료: {out}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
