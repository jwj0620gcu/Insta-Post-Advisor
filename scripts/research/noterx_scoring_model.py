#!/usr/bin/env python3
"""
NoteRx 콘텐츠 평가 모델 (Model A) — 독립 실행 가능한 프로그램
874개의 실제 Instagram 게시글 데이터로 훈련, 이중 트랙 분석 (전통 통계 + LLM).

Usage:
    # 단일 게시글 평가
    python noterx_scoring_model.py --title "5분만에 이 방법 익히기" --content "오늘 알려드릴게요..." --category food --tags 5 --images 6

    # CSV 일괄 평가
    python noterx_scoring_model.py --csv input.csv --output scored.csv

    # 모델 파라미터 출력
    python noterx_scoring_model.py --show-params

연구 방법:
    Track A: Spearman 상관관계 + 선형 회귀 + K-Means 클러스터링 + Kruskal-Wallis 검정
    Track B: LLM 콘텐츠 패턴 분석 + 커버 비주얼 분석 + 태그 전략 분석
    Model A: 회귀 계수 기반 가중치 평가 모델, 카테고리별 파라미터 최적화
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# 모델 파라미터 (874개의 실제 데이터로 훈련됨)
# ═══════════════════════════════════════════════════════════════

MODEL_PARAMS = {
    "food": {
        "weights": {"title_quality": 0.573, "content_quality": 0.132, "visual_quality": 0.086, "tag_strategy": 0.097, "engagement_potential": 0.111},
        "title_length": {"min": 11, "max": 19, "viral_avg": 18.3},
        "content_length": {"min": 105, "max": 342},
        "tag_count": {"min": 4, "max": 8, "best": 6},
        "image_count": {"min": 2, "max": 10},
        "baseline": {"avg_engagement": 33462, "median": 7333, "viral_threshold": 112965, "sample_size": 183},
        "r_squared": 0.106,
    },
    "fashion": {
        "weights": {"title_quality": 0.395, "content_quality": 0.125, "visual_quality": 0.250, "tag_strategy": 0.058, "engagement_potential": 0.172},
        "title_length": {"min": 11, "max": 20, "viral_avg": 14.0},
        "content_length": {"min": 92, "max": 224},
        "tag_count": {"min": 4, "max": 8, "best": 6},
        "image_count": {"min": 2, "max": 10},
        "baseline": {"avg_engagement": 7507, "median": 2069, "viral_threshold": 18037, "sample_size": 278},
        "r_squared": 0.017,
    },
    "tech": {
        "weights": {"title_quality": 0.411, "content_quality": 0.125, "visual_quality": 0.103, "tag_strategy": 0.095, "engagement_potential": 0.267},
        "title_length": {"min": 12, "max": 20, "viral_avg": 17.5},
        "content_length": {"min": 87, "max": 517},
        "tag_count": {"min": 4, "max": 8, "best": 6},
        "image_count": {"min": 1, "max": 6},
        "baseline": {"avg_engagement": 1275, "median": 175, "viral_threshold": 3325, "sample_size": 235},
        "r_squared": 0.177,
    },
    "travel": {
        "weights": {"title_quality": 0.376, "content_quality": 0.050, "visual_quality": 0.120, "tag_strategy": 0.312, "engagement_potential": 0.142},
        "title_length": {"min": 11, "max": 20, "viral_avg": 14.3},
        "content_length": {"min": 123, "max": 737},
        "tag_count": {"min": 4, "max": 8, "best": 6},
        "image_count": {"min": 4, "max": 14},
        "baseline": {"avg_engagement": 16563, "median": 4538, "viral_threshold": 39426, "sample_size": 130},
        "r_squared": 0.138,
    },
    "lifestyle": {
        "weights": {"title_quality": 0.407, "content_quality": 0.083, "visual_quality": 0.071, "tag_strategy": 0.277, "engagement_potential": 0.162},
        "title_length": {"min": 10, "max": 20, "viral_avg": 19.4},
        "content_length": {"min": 24, "max": 148},
        "tag_count": {"min": 4, "max": 8, "best": 6},
        "image_count": {"min": 1, "max": 8},
        "baseline": {"avg_engagement": 8038, "median": 773, "viral_threshold": 17097, "sample_size": 48},
        "r_squared": 0.396,
    },
    "beauty": {
        "weights": {"title_quality": 0.40, "content_quality": 0.15, "visual_quality": 0.20, "tag_strategy": 0.10, "engagement_potential": 0.15},
        "title_length": {"min": 10, "max": 20, "viral_avg": 16.0},
        "content_length": {"min": 100, "max": 400},
        "tag_count": {"min": 4, "max": 8, "best": 6},
        "image_count": {"min": 3, "max": 9},
        "baseline": {"avg_engagement": 5000, "median": 1500, "viral_threshold": 15000, "sample_size": 0},
        "r_squared": None,
    },
    "fitness": {
        "weights": {"title_quality": 0.35, "content_quality": 0.15, "visual_quality": 0.15, "tag_strategy": 0.15, "engagement_potential": 0.20},
        "title_length": {"min": 10, "max": 22, "viral_avg": 16.0},
        "content_length": {"min": 80, "max": 500},
        "tag_count": {"min": 4, "max": 8, "best": 6},
        "image_count": {"min": 2, "max": 8},
        "baseline": {"avg_engagement": 4000, "median": 1000, "viral_threshold": 12000, "sample_size": 0},
        "r_squared": None,
    },
    "home": {
        "weights": {"title_quality": 0.35, "content_quality": 0.15, "visual_quality": 0.20, "tag_strategy": 0.15, "engagement_potential": 0.15},
        "title_length": {"min": 10, "max": 20, "viral_avg": 15.0},
        "content_length": {"min": 100, "max": 500},
        "tag_count": {"min": 4, "max": 8, "best": 6},
        "image_count": {"min": 4, "max": 12},
        "baseline": {"avg_engagement": 6000, "median": 2000, "viral_threshold": 18000, "sample_size": 0},
        "r_squared": None,
    },
}


# ═══════════════════════════════════════════════════════════════
# 특성 추출
# ═══════════════════════════════════════════════════════════════

def detect_emoji(text: str) -> bool:
    return bool(re.search(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        "\U0001F900-\U0001F9FF\U00002702-\U000027B0✨🔥💚‼️⭐📸📊👍]",
        text or ""
    ))


def count_hooks(title: str) -> int:
    hooks = 0
    if re.search(r'\d+', title): hooks += 1
    if re.search(r'[！!？?]', title): hooks += 1
    if re.search(r'[｜|]', title): hooks += 1
    if re.search(r'[✨🔥‼️⭐💯]', title): hooks += 1
    if re.search(r'(必|绝了|太|超|巨|神仙|宝藏|救命)', title): hooks += 1
    return hooks


@dataclass
class NoteFeatures:
    title: str = ""
    content: str = ""
    category: str = "lifestyle"
    tag_count: int = 0
    image_count: int = 0

    @property
    def title_length(self) -> int:
        return len(self.title)

    @property
    def content_length(self) -> int:
        return len(self.content)

    @property
    def has_numbers(self) -> bool:
        return bool(re.search(r'\d+', self.title))

    @property
    def has_emoji(self) -> bool:
        return detect_emoji(self.title + self.content)

    @property
    def hook_count(self) -> int:
        return count_hooks(self.title)


# ═══════════════════════════════════════════════════════════════
# 평가 엔진
# ═══════════════════════════════════════════════════════════════

def range_score(value: float, opt_min: float, opt_max: float, base: float = 80) -> float:
    """값이 최적 범위 내에 있으면 높은 점수, 범위 밖이면 감점"""
    if opt_min <= value <= opt_max:
        mid = (opt_min + opt_max) / 2
        half = (opt_max - opt_min) / 2 + 1
        return base + (100 - base) * (1 - abs(value - mid) / half)
    elif value < opt_min:
        return max(20, base * value / max(opt_min, 1))
    else:
        return max(40, base - (value - opt_max) * 2)


def score_note(features: NoteFeatures) -> dict:
    """
    게시글 하나를 다차원으로 평가합니다.

    Returns:
        {
            "total_score": float,           # 총점 0-100
            "dimensions": {                  # 각 차원 점수
                "title_quality": float,
                "content_quality": float,
                "visual_quality": float,
                "tag_strategy": float,
                "engagement_potential": float,
            },
            "diagnosis": [str, ...],         # 진단 조언
            "percentile_estimate": str,      # 예상 백분위
        }
    """
    cat = features.category
    if cat not in MODEL_PARAMS:
        cat = "lifestyle"
    params = MODEL_PARAMS[cat]
    w = params["weights"]

    # ── 제목 품질 ──
    tl = params["title_length"]
    title_score = range_score(features.title_length, tl["min"], tl["max"])
    title_score += features.has_numbers * 5
    title_score += min(features.hook_count, 3) * 3
    title_score += features.has_emoji * 2
    title_score = min(title_score, 100)

    # ── 콘텐츠 품질 ──
    cl = params["content_length"]
    content_score = range_score(features.content_length, cl["min"], cl["max"], 85)
    content_score = min(content_score, 100)

    # ── 비주얼 품질 (이미지 수 기반, 이미지 분석 없을 때의 근사치) ──
    ic = params["image_count"]
    visual_score = range_score(features.image_count, ic["min"], ic["max"])
    visual_score = min(visual_score, 100)

    # ── 태그 전략 ──
    tc = params["tag_count"]
    tag_score = max(0, 100 - abs(features.tag_count - tc["best"]) * 10)

    # ── 인터랙션 잠재력 (종합 신호) ──
    engagement_signals = 0
    if features.title_length >= tl["min"]: engagement_signals += 25
    if features.has_numbers: engagement_signals += 15
    if features.hook_count >= 2: engagement_signals += 20
    if tc["min"] <= features.tag_count <= tc["max"]: engagement_signals += 20
    if ic["min"] <= features.image_count <= ic["max"]: engagement_signals += 20
    engagement_score = min(engagement_signals, 100)

    # ── 가중치 합산 ──
    dimensions = {
        "title_quality": round(title_score, 1),
        "content_quality": round(content_score, 1),
        "visual_quality": round(visual_score, 1),
        "tag_strategy": round(tag_score, 1),
        "engagement_potential": round(engagement_score, 1),
    }

    total = sum(dimensions[k] * w[k] for k in w)
    total = min(round(total, 1), 100)

    # ── 진단 조언 ──
    diagnosis = []
    if features.title_length < tl["min"]:
        diagnosis.append(f"제목이 너무 짧습니다({features.title_length}자). {tl['min']}-{tl['max']}자를 권장합니다.")
    elif features.title_length > tl["max"]:
        diagnosis.append(f"제목이 너무 깁니다({features.title_length}자). {tl['max']}자 이내로 줄이세요.")
    if not features.has_numbers:
        diagnosis.append("제목에 숫자가 없습니다. 숫자를 추가하면 클릭률이 올라갑니다.")
    if features.hook_count == 0:
        diagnosis.append("제목에 훅 요소가 없습니다 (숫자/이모지/느낌표/핫 키워드)")
    if features.content_length < cl["min"]:
        diagnosis.append(f"본문이 너무 짧습니다({features.content_length}자). {cl['min']}-{cl['max']}자를 권장합니다.")
    if features.tag_count < tc["min"]:
        diagnosis.append(f"태그가 너무 적습니다({features.tag_count}개). {tc['min']}-{tc['max']}개를 권장합니다.")
    elif features.tag_count > tc["max"]:
        diagnosis.append(f"태그가 너무 많습니다({features.tag_count}개). {tc['max']}개 이내로 줄이세요.")
    if features.image_count < ic["min"]:
        diagnosis.append(f"이미지가 너무 적습니다({features.image_count}장). {ic['min']}-{ic['max']}장을 권장합니다.")

    if not diagnosis:
        diagnosis.append("모든 파라미터가 최적 범위 내에 있습니다. 계속 유지하세요!")

    # ── 백분위 예상 ──
    bl = params["baseline"]
    if total >= 85:
        pct = "상위 10% (인기 게시글 잠재력)"
    elif total >= 75:
        pct = "상위 25% (우수 콘텐츠)"
    elif total >= 65:
        pct = "중간 수준 (50%)"
    else:
        pct = "중간 이하, 최적화 권장"

    return {
        "total_score": total,
        "dimensions": dimensions,
        "weights": w,
        "diagnosis": diagnosis,
        "percentile_estimate": pct,
        "baseline": bl,
    }


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def show_params():
    print("NoteRx Model A — 카테고리별 평가 파라미터")
    print("=" * 60)
    print(f"훈련 데이터: 874개의 실제 Instagram 게시글 (5개 카테고리 데이터 있음)")
    print(f"방법: Spearman 상관관계 + 선형 회귀 + K-Means 클러스터링")
    print()

    for cat, p in MODEL_PARAMS.items():
        n = p["baseline"]["sample_size"]
        r2 = p["r_squared"]
        print(f"── {cat} ({n} samples, R²={r2}) ──")
        print(f"  가중치: {json.dumps(p['weights'], indent=2)}")
        print(f"  제목 길이: {p['title_length']['min']}-{p['title_length']['max']} 자")
        print(f"  본문 길이: {p['content_length']['min']}-{p['content_length']['max']} 자")
        print(f"  태그 수: {p['tag_count']['min']}-{p['tag_count']['max']} (최적 {p['tag_count']['best']})")
        print(f"  이미지 수: {p['image_count']['min']}-{p['image_count']['max']} 장")
        print(f"  기준 인터랙션: avg={p['baseline']['avg_engagement']}, median={p['baseline']['median']}")
        print()


def score_single(args):
    features = NoteFeatures(
        title=args.title or "",
        content=args.content or "",
        category=args.category,
        tag_count=args.tags,
        image_count=args.images,
    )
    result = score_note(features)

    print(f"\n{'='*50}")
    print(f"NoteRx 게시글 진단 보고서")
    print(f"{'='*50}")
    print(f"카테고리: {features.category}")
    print(f"제목: {features.title[:50]}{'...' if len(features.title)>50 else ''}")
    print(f"\n총점: {result['total_score']:.1f}/100  ({result['percentile_estimate']})")
    print(f"\n차원별 점수:")
    for dim, score in result["dimensions"].items():
        w = result["weights"][dim]
        bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
        print(f"  {dim:22s} {bar} {score:5.1f} (×{w:.3f})")
    print(f"\n진단 조언:")
    for d in result["diagnosis"]:
        print(f"  • {d}")
    print(f"\n기준선 데이터 ({features.category}):")
    bl = result["baseline"]
    print(f"  평균 인터랙션: {bl['avg_engagement']}, 중간값: {bl['median']}, 인기 기준: {bl['viral_threshold']}")


def score_csv(args):
    with open(args.csv, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    results = []
    for row in rows:
        features = NoteFeatures(
            title=row.get("title", row.get("게시글제목", "")),
            content=row.get("content", row.get("게시글내용", "")),
            category=row.get("category", row.get("카테고리", "lifestyle")),
            tag_count=int(row.get("tag_count", row.get("태그수", 0)) or 0),
            image_count=int(row.get("image_count", row.get("이미지수", 0)) or 0),
        )
        result = score_note(features)
        results.append({
            "title": features.title[:50],
            "category": features.category,
            "total_score": result["total_score"],
            **{f"dim_{k}": v for k, v in result["dimensions"].items()},
            "percentile": result["percentile_estimate"],
            "top_diagnosis": result["diagnosis"][0] if result["diagnosis"] else "",
        })

    out_path = args.output or "scored_output.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=results[0].keys())
        w.writeheader()
        w.writerows(results)
    print(f"평가 완료: {len(results)} 개 → {out_path}")


def main():
    parser = argparse.ArgumentParser(description="NoteRx 콘텐츠 평가 모델 (Model A)")
    parser.add_argument("--title", help="게시글 제목")
    parser.add_argument("--content", help="게시글 본문", default="")
    parser.add_argument("--category", default="lifestyle", choices=list(MODEL_PARAMS.keys()))
    parser.add_argument("--tags", type=int, default=5, help="태그 수")
    parser.add_argument("--images", type=int, default=4, help="이미지 수")
    parser.add_argument("--csv", help="일괄 평가 CSV 파일")
    parser.add_argument("--output", help="출력 CSV 경로")
    parser.add_argument("--show-params", action="store_true", help="모델 파라미터 표시")
    parser.add_argument("--json", action="store_true", help="JSON 형식으로 출력")
    args = parser.parse_args()

    if args.show_params:
        show_params()
    elif args.csv:
        score_csv(args)
    elif args.title:
        if args.json:
            features = NoteFeatures(
                title=args.title, content=args.content,
                category=args.category, tag_count=args.tags, image_count=args.images,
            )
            print(json.dumps(score_note(features), ensure_ascii=False, indent=2))
        else:
            score_single(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
