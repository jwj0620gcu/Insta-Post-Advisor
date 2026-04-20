"""
Step 8: 콘텐츠 평가 모델 구축 (Model A)
전통 통계 + LLM 분석 결과를 합쳐 카테고리별 평가 파라미터와 가중치를 생성합니다.

Usage:
    python scripts/research/08_build_scoring_model.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from config import STATS_DIR, LLM_DIR, OUTPUT_DIR, ALL_CATEGORIES


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def compute_optimal_range(values: list[float], viral_values: list[float]) -> dict:
    """인기 게시글 분포에서 최적 파라미터 범위를 추출합니다"""
    if not viral_values:
        viral_values = values
    arr = np.array(viral_values)
    return {
        "min": round(float(np.percentile(arr, 20)), 1),
        "max": round(float(np.percentile(arr, 80)), 1),
        "sweet_spot": round(float(np.median(arr)), 1),
    }


def main():
    print("=" * 60)
    print("Step 8: 콘텐츠 평가 모델 구축 (Model A)")
    print("=" * 60)

    desc_stats = load_json(STATS_DIR / "descriptive_stats.json")
    regression = load_json(STATS_DIR / "regression_results.json")
    content_patterns = load_json(LLM_DIR / "content_patterns.json")
    tag_analysis = load_json(LLM_DIR / "tag_analysis.json")
    cover_analysis = load_json(LLM_DIR / "cover_analysis_all.json")

    model_a = {}

    for cat in ALL_CATEGORIES:
        if cat not in desc_stats:
            continue

        d = desc_stats[cat]
        reg = regression.get(cat, {})
        coefs = reg.get("coefficients", {})
        cp = content_patterns.get(cat, {})
        ta = tag_analysis.get(cat, {})

        # 회귀 계수로부터 각 차원 가중치 도출 (정규화)
        raw_weights = {
            "title_quality": abs(coefs.get("title_length", 0.1)) + abs(coefs.get("has_numbers", 0.05)) + abs(coefs.get("title_hook_count", 0.05)),
            "content_quality": abs(coefs.get("content_length", 0.1)),
            "visual_quality": 0.2,  # 기본 가중치, LLM 분석 후 조정
            "tag_strategy": abs(coefs.get("tag_count", 0.1)),
            "engagement_potential": abs(coefs.get("has_emoji", 0.05)) + abs(coefs.get("image_count", 0.05)),
        }
        total = sum(raw_weights.values()) or 1
        weights = {k: round(v / total, 3) for k, v in raw_weights.items()}

        # 커버 분석으로 visual_quality 가중치 조정
        if cat in (cover_analysis or {}):
            covers = cover_analysis[cat]
            if covers:
                avg_appeal = np.mean([c.get("click_appeal", 5) for c in covers])
                # 커버 품질 분산이 크면 비주얼 차원이 중요함을 의미
                appeal_std = np.std([c.get("click_appeal", 5) for c in covers])
                if appeal_std > 2:
                    weights["visual_quality"] = min(weights["visual_quality"] * 1.5, 0.35)

        # 最优参数区间
        scoring_params = {
            "title_length": {
                "optimal": {
                    "min": d.get("title_length", {}).get("p25", 10),
                    "max": d.get("title_length", {}).get("p75", 25),
                },
                "viral_avg": d.get("viral_vs_normal", {}).get("title_length", {}).get("viral_mean", 18),
            },
            "tag_count": {
                "optimal": ta.get("optimal_tag_count", {"min": 4, "max": 8, "best": 6}),
            },
            "content_length": {
                "optimal": {
                    "min": d.get("content_length", {}).get("p25", 100),
                    "max": d.get("content_length", {}).get("p75", 600),
                },
            },
            "image_count": {
                "optimal": {
                    "min": d.get("image_count", {}).get("p25", 3),
                    "max": d.get("image_count", {}).get("p75", 9),
                },
            },
        }

        # LLM이 발견한 콘텐츠 패턴
        title_patterns = cp.get("title_patterns", [])
        content_structure = cp.get("content_structure", [])

        model_a[cat] = {
            "weights": weights,
            "scoring_params": scoring_params,
            "baseline": {
                "avg_engagement": d.get("engagement", {}).get("mean", 0),
                "median_engagement": d.get("engagement", {}).get("median", 0),
                "viral_threshold": d.get("engagement", {}).get("p90", 0),
                "viral_rate": round(d.get("viral_count", 0) / max(d.get("total", 1), 1) * 100, 1),
                "sample_size": d.get("total", 0),
            },
            "regression_r_squared": reg.get("r_squared", 0),
            "title_patterns": title_patterns[:5],
            "content_structure": content_structure[:3],
            "top_tags": ta.get("top_tags", [])[:10],
        }

        print(f"  [{cat}] weights={weights}, R²={reg.get('r_squared', 'N/A')}")

    # 저장
    out = OUTPUT_DIR / "model_a_scoring.json"
    out.write_text(json.dumps(model_a, ensure_ascii=False, indent=2))
    print(f"\nModel A 저장 완료: {out}")
    print(f"{len(model_a)}개 카테고리 적용")


if __name__ == "__main__":
    main()
