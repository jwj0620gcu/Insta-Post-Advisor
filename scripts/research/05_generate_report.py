"""
Step 5: 종합 보고서 생성
Track A 통계 결과 + Track B LLM 분석 결과를 합쳐 LLM에 전달하여 최종 해석 후 연구 보고서를 생성합니다.

Usage:
    python scripts/research/05_generate_report.py
"""
import json
import asyncio
import sys
from pathlib import Path
from datetime import datetime

import httpx
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    STATS_DIR, LLM_DIR, OUTPUT_DIR,
    API_KEY, API_BASE, MODEL_PRO, ALL_CATEGORIES,
)


def get_client() -> AsyncOpenAI:
    http_client = httpx.AsyncClient(proxy=None, trust_env=False, timeout=httpx.Timeout(180.0, connect=30.0))
    return AsyncOpenAI(api_key=API_KEY, base_url=API_BASE, http_client=http_client)


def load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


REPORT_PROMPT = """당신은 노련한 소셜 미디어 데이터 과학자입니다. 아래 통계 분석 및 LLM 분석 결과를 바탕으로 완전한 연구 보고서를 작성하세요.

## 요구사항
1. 데이터를 단순히 반복하지 말고, **각 발견의 실제 의미를 해석**하세요
2. **반직관적 결론**에 특히 주목하세요
3. 각 카테고리에 대해 **구체적이고 실행 가능한 「황금 파라미터」 추천**을 제시하세요
4. 카테고리 간 차이를 비교하여 **카테고리 공통 규칙**과 **카테고리별 특이 규칙**을 찾으세요
5. 데이터 한계를 지적하세요

## 출력 형식 (Markdown)

# Instagram 게시글 데이터 연구 보고서

## 1. 연구 개요
（표본 수, 카테고리 범위, 분석 방법）

## 2. 핵심 발견
（가장 중요한 5-8가지 발견, 각각 데이터 근거 포함）

## 3. 카테고리별 심층 분석
（각 카테고리 소절: 특성 프로파일 + 인기 게시글의 비밀 + 황금 파라미터）

## 4. 커버 비주얼 연구
（LLM 비주얼 분석 기반 발견）

## 5. 콘텐츠 패턴 연구
（제목 패턴 + 콘텐츠 구조 + 감성 기조）

## 6. 태그 전략 연구
（최적 전략 + 카테고리 차이）

## 7. 게시 타이밍 연구
（최적 시간대 + 요일 효과）

## 8. 정량 평가 기준
（카테고리별 추천 파라미터 표）

## 9. 한계점 및 전망

---

## 입력 데이터

### 기술 통계
{descriptive_stats}

### 상관관계 분석
{correlation}

### 회귀 분석
{regression}

### 카테고리 차이
{category_comparison}

### 최적 게시 시간대
{best_hours}

### 클러스터 분석
{clusters}

### 커버 비주얼 분석（LLM）
{cover_analysis_summary}

### 콘텐츠 패턴 분석（LLM）
{content_patterns}

### 태그 전략 분석（LLM）
{tag_analysis}
"""


def summarize_cover_analysis(cover_data: dict) -> dict:
    """커버 분석 결과를 요약하여 과도한 데이터 전달을 방지합니다"""
    summary = {}
    for cat, items in cover_data.items():
        if not items:
            continue
        styles = {}
        tones = {}
        face_count = 0
        text_overlay_count = 0
        avg_quality = 0
        avg_appeal = 0

        for item in items:
            s = item.get("cover_style", "unknown")
            styles[s] = styles.get(s, 0) + 1
            t = item.get("color_tone", "unknown")
            tones[t] = tones.get(t, 0) + 1
            if item.get("has_face"):
                face_count += 1
            if item.get("text_overlay"):
                text_overlay_count += 1
            avg_quality += item.get("visual_quality", 0)
            avg_appeal += item.get("click_appeal", 0)

        n = len(items)
        summary[cat] = {
            "analyzed": n,
            "top_styles": dict(sorted(styles.items(), key=lambda x: -x[1])[:5]),
            "top_tones": dict(sorted(tones.items(), key=lambda x: -x[1])[:3]),
            "face_rate": round(face_count / n * 100, 1),
            "text_overlay_rate": round(text_overlay_count / n * 100, 1),
            "avg_visual_quality": round(avg_quality / n, 2),
            "avg_click_appeal": round(avg_appeal / n, 2),
        }
    return summary


async def main():
    print("=" * 60)
    print("Step 5: 종합 보고서 생성")
    print("=" * 60)

    # 모든 분석 결과 로드
    desc_stats = load_json(STATS_DIR / "descriptive_stats.json")
    correlation = load_json(STATS_DIR / "correlation_matrix.json")
    regression = load_json(STATS_DIR / "regression_results.json")
    cat_cmp = load_json(STATS_DIR / "category_comparison.json")
    best_hours = load_json(STATS_DIR / "best_publish_hours.json")
    clusters = load_json(STATS_DIR / "cluster_profiles.json")
    cover_all = load_json(LLM_DIR / "cover_analysis_all.json")
    content_patterns = load_json(LLM_DIR / "content_patterns.json")
    tag_analysis = load_json(LLM_DIR / "tag_analysis.json")

    # 커버 데이터 요약
    cover_summary = summarize_cover_analysis(cover_all)

    # 상관관계 데이터 간소화 (engagement와의 상관관계만 보존)
    corr_simplified = {}
    if correlation and "engagement" in correlation:
        for k, v in correlation["engagement"].items():
            if k != "engagement":
                corr_simplified[k] = v

    prompt = REPORT_PROMPT.format(
        descriptive_stats=json.dumps(desc_stats, ensure_ascii=False, indent=1)[:3000],
        correlation=json.dumps(corr_simplified, ensure_ascii=False, indent=1),
        regression=json.dumps(regression, ensure_ascii=False, indent=1),
        category_comparison=json.dumps(cat_cmp, ensure_ascii=False, indent=1),
        best_hours=json.dumps(best_hours, ensure_ascii=False, indent=1),
        clusters=json.dumps(clusters, ensure_ascii=False, indent=1),
        cover_analysis_summary=json.dumps(cover_summary, ensure_ascii=False, indent=1),
        content_patterns=json.dumps(content_patterns, ensure_ascii=False, indent=1)[:3000],
        tag_analysis=json.dumps(tag_analysis, ensure_ascii=False, indent=1)[:2000],
    )

    print("mimo-v2-pro 호출하여 최종 보고서 생성 중...")
    client = get_client()
    try:
        response = await client.chat.completions.create(
            model=MODEL_PRO,
            messages=[
                {"role": "system", "content": "당신은 데이터 과학 연구원으로, 데이터 분석을 가독성 높은 연구 보고서로 변환하는 데 뛰어납니다. 한국어로 작성하세요."},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=8000,
        )
        report_text = response.choices[0].message.content

        # 메타 정보 추가
        header = f"""---
생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M')}
데이터 출처: NoteRx 연구 데이터베이스
분석 방법: 전통 통계 (Track A) + LLM 심층 분석 (Track B)
모델: {MODEL_PRO}
---

"""
        report = header + report_text

        out = OUTPUT_DIR / "final_report.md"
        out.write_text(report)
        print(f"\n보고서 생성 완료: {out}")
        print(f"보고서 길이: {len(report_text)} 자")

    except Exception as e:
        print(f"보고서 생성 실패: {e}")

    # 정량 평가 파라미터 생성
    print("\n정량 평가 파라미터 생성 중...")
    scoring_params = {}
    for cat in ALL_CATEGORIES:
        if cat not in desc_stats:
            continue
        d = desc_stats[cat]
        reg_cat = regression.get(cat, {})
        coefs = reg_cat.get("coefficients", {})

        # 기술 통계 및 회귀 계수로부터 최적 파라미터 도출
        scoring_params[cat] = {
            "scoring_params": {
                "title_length": {
                    "optimal_range": [
                        int(d.get("title_length", {}).get("p25", 10)),
                        int(d.get("title_length", {}).get("p75", 30)),
                    ],
                    "weight": round(abs(coefs.get("title_length", 0.1)), 3),
                },
                "tag_count": {
                    "optimal_range": [
                        int(d.get("tag_count", {}).get("p25", 3)),
                        int(d.get("tag_count", {}).get("p75", 8)),
                    ],
                    "weight": round(abs(coefs.get("tag_count", 0.1)), 3),
                },
                "has_numbers": {
                    "bonus": 5,
                    "weight": round(abs(coefs.get("has_numbers", 0.05)), 3),
                },
                "content_length": {
                    "optimal_range": [
                        int(d.get("content_length", {}).get("p25", 100)),
                        int(d.get("content_length", {}).get("p75", 500)),
                    ],
                    "weight": round(abs(coefs.get("content_length", 0.1)), 3),
                },
                "image_count": {
                    "optimal_range": [
                        int(d.get("image_count", {}).get("p25", 1)),
                        int(d.get("image_count", {}).get("p75", 9)),
                    ],
                    "weight": round(abs(coefs.get("image_count", 0.05)), 3),
                },
            },
            "baseline": {
                "avg_engagement": d.get("engagement", {}).get("mean", 0),
                "viral_threshold": d.get("engagement", {}).get("p90", 0),
                "viral_rate": round(d.get("viral_count", 0) / max(d.get("total", 1), 1) * 100, 1),
            },
        }

    out = OUTPUT_DIR / "scoring_params.json"
    out.write_text(json.dumps(scoring_params, ensure_ascii=False, indent=2))
    print(f"평가 파라미터: {out}")

    await client.close()

    print("\n" + "=" * 60)
    print("Step 5 완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
