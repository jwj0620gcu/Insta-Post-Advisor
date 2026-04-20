"""
Step 11: 최종 연구 보고서 생성
모든 분석 결과를 집계하고 LLM을 호출하여 완전한 연구 보고서 + 스토리텔링 서술을 생성합니다.

Usage:
    python scripts/research/11_final_report.py
"""
from __future__ import annotations

import json
import asyncio
import sys
from pathlib import Path
from datetime import datetime

import httpx
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).parent))
from config import OUTPUT_DIR, STATS_DIR, LLM_DIR, CHARTS_DIR, API_KEY, API_BASE, MODEL_PRO


def get_client() -> AsyncOpenAI:
    http_client = httpx.AsyncClient(proxy=None, trust_env=False, timeout=httpx.Timeout(300.0, connect=30.0))
    return AsyncOpenAI(api_key=API_KEY, base_url=API_BASE, http_client=http_client)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


REPORT_PROMPT = """당신은 데이터 과학 연구원으로, 해커톤 경진대회 프로젝트의 연구 보고서를 작성 중입니다.
이 보고서는 전문적인 깊이를 갖추면서도 스토리텔링이 있어야 합니다 — PPT와 데모에서 사용 가능해야 합니다.

## 연구 배경

InstaRx NoteRx는 Instagram 게시글 진단 플랫폼입니다. 실제 Instagram 게시글 데이터를 수집하여
「전통 통계 분석 + LLM 심층 분석」 이중 트랙 방식으로 정량 평가 모델을 구축했습니다.

## 입력 데이터

### Model A 평가 모델
{model_a}

### 모델 검증 결과
{validation}

### 사용자 페르소나 (Model B, 있을 경우)
{personas}

### 통계 발견 요약
{stats_summary}

## 요구사항

**한국어 연구 보고서**를 Markdown 형식으로 작성하세요. 포함 항목:

1. **연구 개요** (100자): 표본 수, 방법, 핵심 발견
2. **방법론** (200자): 이중 트랙 분석이 어떻게 상호 보완하는지
3. **핵심 발견** (카테고리별 단락, 각 100-150자):
   - 가장 중요한 2-3가지 발견
   - 구체적인 수치 근거
   - 반직관적 결론 (있을 경우)
4. **정량 평가 기준**: 카테고리별 「황금 파라미터」 표
5. **모델 검증**: 정확도, 상관관계, 신뢰도 분석
6. **사용자 페르소나 연구** (데이터 있을 경우)
7. **한계점** (솔직하지만 간결하게)
8. **스토리텔링 마무리**: 이 연구의 가치를 한두 문장으로 요약 —
   "AI의 직감이 아니라 데이터로 말한다"

각 발견에는 **PPT에서 바로 사용 가능한 핵심 문구**를 `> ` 인용 형식으로 표기하세요.

보고서 목표 독자: 해커톤 심사위원 (기획자, 개발자, 투자자).
"""


async def main():
    print("=" * 60)
    print("Step 11: 최종 연구 보고서")
    print("=" * 60)

    model_a = load_json(OUTPUT_DIR / "model_a_scoring.json")
    validation = load_json(OUTPUT_DIR / "model_validation.json")
    personas = load_json(LLM_DIR / "user_personas.json")
    desc_stats = load_json(STATS_DIR / "descriptive_stats.json")

    # 통계 요약 간소화
    stats_summary = {}
    for cat, d in desc_stats.items():
        stats_summary[cat] = {
            "total": d.get("total", 0),
            "viral_count": d.get("viral_count", 0),
            "avg_engagement": d.get("engagement", {}).get("mean", 0),
            "image_vs_video": d.get("image_vs_video", {}),
        }

    prompt = REPORT_PROMPT.format(
        model_a=json.dumps(model_a, ensure_ascii=False, indent=1)[:3000],
        validation=json.dumps(validation, ensure_ascii=False, indent=1)[:1500],
        personas=json.dumps(
            {k: {"persona_count": len(v.get("personas", []))} for k, v in personas.items()},
            ensure_ascii=False, indent=1
        ) if personas else "댓글 데이터 없음, 페르소나 연구는 추가 데이터 대기 중",
        stats_summary=json.dumps(stats_summary, ensure_ascii=False, indent=1)[:1500],
    )

    client = get_client()
    print("mimo-v2-pro 호출하여 연구 보고서 생성 중...")

    try:
        response = await client.chat.completions.create(
            model=MODEL_PRO,
            messages=[
                {"role": "system", "content": "당신은 데이터 과학 연구원입니다. Markdown 형식의 연구 보고서를 출력하세요."},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=6000,
        )
        report_text = response.choices[0].message.content

        # 헤더 메타 정보 추가
        header = f"""---
title: NoteRx 데이터 연구 보고서
date: {datetime.now().strftime('%Y-%m-%d')}
method: 전통 통계 (Track A) + LLM 심층 분석 (Track B)
model: {MODEL_PRO}
---

"""

        # 차트 참조 추가
        charts = list(CHARTS_DIR.glob("*.png"))
        if charts:
            chart_section = "\n\n---\n\n## 부록: 연구 차트\n\n"
            for c in sorted(charts):
                chart_section += f"### {c.stem}\n\n![{c.stem}](../../data/research_output/charts/{c.name})\n\n"
            report_text += chart_section

        out = OUTPUT_DIR / "final_research_report.md"
        out.write_text(header + report_text)
        print(f"\n보고서 생성 완료: {out}")
        print(f"보고서 길이: {len(report_text)} 자")

    except Exception as e:
        print(f"보고서 생성 실패: {e}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
