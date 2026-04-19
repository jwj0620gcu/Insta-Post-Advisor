"""
Model A 재보정 전 raw 데이터 스키마/품질 검증기.

Usage:
    python3 scripts/model_a_prep/02_validate_dataset.py --input data/instagram_recalibration/raw_posts.csv
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.agents.model_a_contract import (  # noqa: E402
    CATEGORIES,
    FORMATS,
    NUMERIC_RANGE_RULES,
    OPTIONAL_RAW_COLUMNS_COMMON,
    REQUIRED_RAW_COLUMNS_COMMON,
    REQUIRED_RAW_COLUMNS_COMMON_PUBLIC_CRAWL,
    required_columns_for_format,
    required_columns_for_format_public_crawl,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="raw posts csv path")
    p.add_argument(
        "--mode",
        choices=("full", "public-crawl"),
        default="full",
        help="validation mode: full(인사이트 포함) | public-crawl(공개지표 기반)",
    )
    return p.parse_args()


def _as_float(v: str) -> float | None:
    s = (v or "").strip()
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_datetime(v: str) -> bool:
    s = (v or "").strip()
    if not s:
        return False
    # 허용 포맷: ISO8601 우선, 실패 시 common format fallback
    try:
        datetime.fromisoformat(s.replace("Z", "+00:00"))
        return True
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            datetime.strptime(s, fmt)
            return True
        except ValueError:
            continue
    return False


def _normalize_format(v: str) -> str:
    t = (v or "").strip().lower()
    if t in ("reel", "reels", "video", "short", "shorts", "clip", "clips"):
        return "reels"
    if t in ("carousel", "album", "multi", "gallery"):
        return "carousel"
    if t in ("single", "image", "photo", "feed"):
        return "single"
    return t


def main() -> int:
    args = _parse_args()
    csv_path = Path(args.input)
    mode = args.mode
    if not csv_path.exists():
        print(f"[error] input file not found: {csv_path}")
        return 1

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        required_common = (
            REQUIRED_RAW_COLUMNS_COMMON
            if mode == "full"
            else REQUIRED_RAW_COLUMNS_COMMON_PUBLIC_CRAWL
        )
        required_for_format = (
            required_columns_for_format
            if mode == "full"
            else required_columns_for_format_public_crawl
        )

        missing_common = [c for c in required_common if c not in headers]
        if missing_common:
            print(f"[error] missing common columns: {missing_common}")
            return 1

        total = 0
        errors = 0
        category_counts = {k: 0 for k in CATEGORIES}
        format_counts = {k: 0 for k in FORMATS}

        for idx, row in enumerate(reader, start=2):
            total += 1
            category = (row.get("category") or "").strip()
            content_format = _normalize_format(row.get("format") or "")

            if category not in CATEGORIES:
                print(f"[error][line {idx}] invalid category: {category!r}")
                errors += 1
            else:
                category_counts[category] += 1

            if content_format not in FORMATS:
                print(f"[error][line {idx}] invalid format: {content_format!r}")
                errors += 1
                continue
            format_counts[content_format] += 1

            if not _parse_datetime(row.get("created_at") or ""):
                print(f"[error][line {idx}] invalid created_at: {row.get('created_at')!r}")
                errors += 1

            # 포맷별 필수 컬럼값 존재 여부
            for col in required_for_format(content_format):
                if mode == "public-crawl" and col in {"caption"}:
                    # public-crawl: 무캡션 포스트 허용
                    continue
                if (row.get(col) or "").strip() == "":
                    print(f"[error][line {idx}] required value missing for format={content_format}: {col}")
                    errors += 1

            # 수치 범위 검증
            for col, rule in NUMERIC_RANGE_RULES.items():
                if col not in headers:
                    continue
                val = _as_float(row.get(col) or "")
                if val is None:
                    continue
                if val < rule.min_value or val > rule.max_value:
                    print(
                        f"[error][line {idx}] out-of-range {col}={val} "
                        f"(expected {rule.min_value}..{rule.max_value})"
                    )
                    errors += 1

            # logical checks
            reach = _as_float(row.get("reach") or "") if "reach" in headers else None
            impressions = _as_float(row.get("impressions") or "") if "impressions" in headers else None
            followers = _as_float(row.get("followers") or "")
            if reach is not None and impressions is not None and impressions < reach:
                print(f"[error][line {idx}] impressions({impressions}) < reach({reach})")
                errors += 1
            if followers is not None and followers < 0:
                print(f"[error][line {idx}] followers must be >= 0")
                errors += 1

    print(f"[summary] mode={mode}, rows={total}, errors={errors}")
    print(f"[summary] categories={category_counts}")
    print(f"[summary] formats={format_counts}")

    if mode == "public-crawl":
        # optional metrics availability (warn only)
        optional_availability = {
            col: (col in headers)
            for col in (
                *OPTIONAL_RAW_COLUMNS_COMMON,
                "reach",
                "impressions",
                "saves",
                "shares",
                "watch_3s_rate",
                "watch_completion_rate",
                "carousel_swipe_rate",
                "profile_visits",
            )
        }
        print(f"[summary] optional_metric_columns_present={optional_availability}")

    # 최소 샘플 기준 (재보정 시작 게이트)
    min_per_format = 30
    insufficient = [f for f, c in format_counts.items() if c < min_per_format]
    if insufficient:
        print(
            f"[warn] low sample for formats {insufficient} "
            f"(need >= {min_per_format} each before recalibration)"
        )

    return 1 if errors > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
