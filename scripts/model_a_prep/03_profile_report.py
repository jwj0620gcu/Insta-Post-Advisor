"""
Model A 재보정 전 데이터 프로파일 리포트 생성기.

Usage:
    python3 scripts/model_a_prep/03_profile_report.py \
      --input data/instagram_recalibration/raw_posts.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.agents.model_a_contract import (  # noqa: E402
    FEATURE_CONTRACT_VERSION,
    CATEGORIES,
    FORMATS,
    NUMERIC_RANGE_RULES,
    OPTIONAL_RAW_COLUMNS_COMMON,
    REQUIRED_RAW_COLUMNS_COMMON,
    REQUIRED_RAW_COLUMNS_COMMON_PUBLIC_CRAWL,
    REQUIRED_RAW_COLUMNS_BY_FORMAT,
    REQUIRED_RAW_COLUMNS_BY_FORMAT_PUBLIC_CRAWL,
    required_columns_for_format,
    required_columns_for_format_public_crawl,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="raw posts csv path")
    parser.add_argument(
        "--mode",
        choices=("full", "public-crawl"),
        default="full",
        help="profile mode: full(인사이트 포함) | public-crawl(공개지표 기반)",
    )
    parser.add_argument(
        "--out-dir",
        default="data/instagram_recalibration/reports",
        help="output directory for json/md report",
    )
    return parser.parse_args()


def _as_float(v: str) -> float | None:
    s = (v or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_dt(v: str) -> datetime | None:
    s = (v or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _normalize_format(v: str) -> str:
    t = (v or "").strip().lower()
    if t in ("reel", "reels", "video", "short", "shorts", "clip", "clips"):
        return "reels"
    if t in ("carousel", "album", "multi", "gallery"):
        return "carousel"
    if t in ("single", "image", "photo", "feed"):
        return "single"
    return t


def _bucket_followers(v: float | None) -> str:
    if v is None:
        return "unknown"
    if v < 1_000:
        return "0-1k"
    if v < 10_000:
        return "1k-10k"
    if v < 100_000:
        return "10k-100k"
    return "100k+"


def main() -> int:
    args = _parse_args()
    input_path = Path(args.input)
    mode = args.mode
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"[error] input file not found: {input_path}")
        return 1

    with input_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    total = len(rows)
    now = datetime.now(timezone.utc)
    last_90d_cutoff = now - timedelta(days=90)

    # Coverage
    category_counts = {c: 0 for c in CATEGORIES}
    format_counts = {fmt: 0 for fmt in FORMATS}
    matrix = {c: {fmt: 0 for fmt in FORMATS} for c in CATEGORIES}

    # Missing and quality stats
    required_common = (
        REQUIRED_RAW_COLUMNS_COMMON
        if mode == "full"
        else REQUIRED_RAW_COLUMNS_COMMON_PUBLIC_CRAWL
    )
    required_by_format = (
        REQUIRED_RAW_COLUMNS_BY_FORMAT
        if mode == "full"
        else REQUIRED_RAW_COLUMNS_BY_FORMAT_PUBLIC_CRAWL
    )
    required_for_format = (
        required_columns_for_format
        if mode == "full"
        else required_columns_for_format_public_crawl
    )

    all_relevant_cols = list(required_common)
    for cols in required_by_format.values():
        for col in cols:
            if col not in all_relevant_cols:
                all_relevant_cols.append(col)
    for col in OPTIONAL_RAW_COLUMNS_COMMON:
        if col not in all_relevant_cols:
            all_relevant_cols.append(col)
    missing_counts = {col: 0 for col in all_relevant_cols}
    invalid_range_counts = {col: 0 for col in NUMERIC_RANGE_RULES}
    invalid_datetime = 0
    invalid_impressions_vs_reach = 0
    per_format_required_missing = {fmt: 0 for fmt in FORMATS}

    # Temporal/follower stats
    created_at_list: list[datetime] = []
    within_90d = 0
    follower_buckets = {"0-1k": 0, "1k-10k": 0, "10k-100k": 0, "100k+": 0, "unknown": 0}

    for row in rows:
        category = (row.get("category") or "").strip().lower()
        content_format = _normalize_format(row.get("format") or "")

        if category in category_counts:
            category_counts[category] += 1
        if content_format in format_counts:
            format_counts[content_format] += 1
        if category in matrix and content_format in matrix.get(category, {}):
            matrix[category][content_format] += 1

        # Missing
        for col in all_relevant_cols:
            if (row.get(col) or "").strip() == "":
                missing_counts[col] += 1

        # Format-specific required missing
        if content_format in FORMATS:
            for col in required_for_format(content_format):
                if (row.get(col) or "").strip() == "":
                    per_format_required_missing[content_format] += 1

        # Datetime
        dt = _parse_dt(row.get("created_at") or "")
        if dt is None:
            invalid_datetime += 1
        else:
            created_at_list.append(dt)
            if dt >= last_90d_cutoff:
                within_90d += 1

        # Numeric range
        for col, rule in NUMERIC_RANGE_RULES.items():
            val = _as_float(row.get(col) or "")
            if val is None:
                continue
            if val < rule.min_value or val > rule.max_value:
                invalid_range_counts[col] += 1

        # Logical check
        reach = _as_float(row.get("reach") or "") if "reach" in headers else None
        impressions = _as_float(row.get("impressions") or "") if "impressions" in headers else None
        if reach is not None and impressions is not None and impressions < reach:
            invalid_impressions_vs_reach += 1

        # Followers bucket
        followers = _as_float(row.get("followers") or "")
        follower_buckets[_bucket_followers(followers)] += 1

    def _pct(n: int, d: int) -> float:
        if d <= 0:
            return 0.0
        return round(n * 100.0 / d, 2)

    category_covered = sum(1 for _, cnt in category_counts.items() if cnt > 0)
    format_covered = sum(1 for _, cnt in format_counts.items() if cnt > 0)

    oldest = min(created_at_list).isoformat() if created_at_list else None
    newest = max(created_at_list).isoformat() if created_at_list else None

    # optional metric availability
    optional_metrics = (
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
    optional_metric_nonempty_counts = {}
    for metric in optional_metrics:
        if metric not in headers:
            optional_metric_nonempty_counts[metric] = 0
            continue
        cnt = 0
        for row in rows:
            if (row.get(metric) or "").strip() != "":
                cnt += 1
        optional_metric_nonempty_counts[metric] = cnt

    gates = {
        "format_min_30_pass": all(c >= 30 for c in format_counts.values()) if total > 0 else False,
        "format_min_100_pass": all(c >= 100 for c in format_counts.values()) if total > 0 else False,
        "all_categories_covered_pass": category_covered == len(CATEGORIES),
        "recency_90d_70pct_pass": _pct(within_90d, total) >= 70.0 if total > 0 else False,
    }
    if mode == "public-crawl":
        # public-crawl에서는 likes/comments/followers 고품질 확보가 핵심
        core = ("likes", "comments", "followers")
        core_nonempty_rates = {}
        for c in core:
            nonempty = total - missing_counts.get(c, total)
            core_nonempty_rates[c] = _pct(nonempty, total)
        gates["public_core_metrics_95pct_pass"] = all(v >= 95.0 for v in core_nonempty_rates.values()) if total > 0 else False
        gates["reels_views_30pct_pass"] = (
            _pct(optional_metric_nonempty_counts.get("views", 0), format_counts.get("reels", 0)) >= 30.0
            if format_counts.get("reels", 0) > 0
            else False
        )

    report = {
        "generated_at": now.isoformat(),
        "feature_contract_version": FEATURE_CONTRACT_VERSION,
        "mode": mode,
        "input_file": str(input_path),
        "total_rows": total,
        "coverage": {
            "category_counts": category_counts,
            "format_counts": format_counts,
            "category_format_matrix": matrix,
            "category_covered": category_covered,
            "format_covered": format_covered,
        },
        "missingness": {
            "counts": missing_counts,
            "rates_pct": {k: _pct(v, total) for k, v in missing_counts.items()},
            "per_format_required_missing_counts": per_format_required_missing,
        },
        "outliers": {
            "range_violation_counts": invalid_range_counts,
            "range_violation_rates_pct": {k: _pct(v, total) for k, v in invalid_range_counts.items()},
            "invalid_datetime_count": invalid_datetime,
            "invalid_impressions_vs_reach_count": invalid_impressions_vs_reach,
        },
        "recency": {
            "oldest_created_at": oldest,
            "newest_created_at": newest,
            "within_90d_count": within_90d,
            "within_90d_rate_pct": _pct(within_90d, total),
        },
        "followers": {
            "bucket_counts": follower_buckets,
            "bucket_rates_pct": {k: _pct(v, total) for k, v in follower_buckets.items()},
        },
        "optional_metric_availability": {
            "nonempty_counts": optional_metric_nonempty_counts,
            "nonempty_rates_pct": {k: _pct(v, total) for k, v in optional_metric_nonempty_counts.items()},
        },
        "gates": gates,
    }

    stamp = now.strftime("%Y%m%d-%H%M%S")
    json_out = out_dir / f"profile-{stamp}.json"
    md_out = out_dir / f"profile-{stamp}.md"
    latest_json = out_dir / "latest.json"
    latest_md = out_dir / "latest.md"

    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md = []
    md.append(f"# Model A Prep Profile Report\n")
    md.append(f"- generated_at: `{report['generated_at']}`")
    md.append(f"- contract: `{FEATURE_CONTRACT_VERSION}`")
    md.append(f"- mode: `{mode}`")
    md.append(f"- rows: `{total}`")
    md.append("")
    md.append("## Coverage")
    md.append(f"- categories covered: `{category_covered}/{len(CATEGORIES)}`")
    md.append(f"- formats covered: `{format_covered}/{len(FORMATS)}`")
    md.append(f"- format counts: `{format_counts}`")
    md.append("")
    md.append("## Gates")
    for k, v in report["gates"].items():
        md.append(f"- {k}: `{'PASS' if v else 'FAIL'}`")
    md.append("")
    md.append("## Missingness (Top 10 by count)")
    top_missing = sorted(missing_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for col, cnt in top_missing:
        md.append(f"- {col}: `{cnt}` ({_pct(cnt, total)}%)")
    md.append("")
    md.append("## Outliers")
    md.append(f"- invalid datetime: `{invalid_datetime}`")
    md.append(f"- impressions < reach: `{invalid_impressions_vs_reach}`")
    bad_ranges = {k: v for k, v in invalid_range_counts.items() if v > 0}
    if bad_ranges:
        md.append(f"- range violations: `{bad_ranges}`")
    else:
        md.append("- range violations: `{}`")
    md.append("")
    md.append("## Recency")
    md.append(f"- oldest: `{oldest}`")
    md.append(f"- newest: `{newest}`")
    md.append(f"- within 90d: `{within_90d}` ({_pct(within_90d, total)}%)")
    md.append("")
    md.append("## Followers Buckets")
    md.append(f"- counts: `{follower_buckets}`")
    md.append("")
    md.append("## Optional Metric Availability")
    top_optional = sorted(
        report["optional_metric_availability"]["nonempty_rates_pct"].items(),
        key=lambda x: x[1],
        reverse=True,
    )
    for metric, rate in top_optional:
        cnt = report["optional_metric_availability"]["nonempty_counts"][metric]
        md.append(f"- {metric}: `{cnt}` ({rate}%)")

    md_text = "\n".join(md) + "\n"
    md_out.write_text(md_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")

    print(f"[ok] profile report json: {json_out}")
    print(f"[ok] profile report md  : {md_out}")
    print(f"[ok] latest aliases     : {latest_json}, {latest_md}")
    print(f"[summary] mode={mode}, rows={total}, category_covered={category_covered}/{len(CATEGORIES)}, format_counts={format_counts}")
    print(f"[summary] gates={report['gates']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
