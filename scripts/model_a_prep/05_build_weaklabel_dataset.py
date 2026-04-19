"""
public-crawl raw_posts.csv -> Model A weak-label 학습용 데이터셋 생성.

Usage:
  python3 scripts/model_a_prep/05_build_weaklabel_dataset.py \
    --input data/instagram_recalibration/raw_posts.csv \
    --output data/instagram_recalibration/modela_ready_weak.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.agents.model_a_contract import (  # noqa: E402
    REQUIRED_RAW_COLUMNS_COMMON,
    REQUIRED_RAW_COLUMNS_BY_FORMAT,
    OPTIONAL_RAW_COLUMNS_COMMON,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="raw_posts.csv")
    p.add_argument(
        "--output",
        default="data/instagram_recalibration/modela_ready_weak.csv",
        help="output csv path",
    )
    return p.parse_args()


def _f(v: str | None, default: float = 0.0) -> float:
    s = (v or "").strip()
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _normalize_format(v: str) -> str:
    t = (v or "").strip().lower()
    if t in ("reel", "reels", "video", "short", "shorts", "clip", "clips"):
        return "reels"
    if t in ("carousel", "album", "multi", "gallery"):
        return "carousel"
    if t in ("single", "image", "photo", "feed"):
        return "single"
    return t


def _headers() -> list[str]:
    cols = list(REQUIRED_RAW_COLUMNS_COMMON)
    for arr in REQUIRED_RAW_COLUMNS_BY_FORMAT.values():
        for c in arr:
            if c not in cols:
                cols.append(c)
    for c in OPTIONAL_RAW_COLUMNS_COMMON:
        if c not in cols:
            cols.append(c)
    # proxy/debug columns
    cols.extend(
        [
            "engagement_proxy_count",
            "engagement_proxy_rate",
            "proxy_flags",
        ]
    )
    return cols


def main() -> int:
    args = _parse_args()
    in_path = Path(args.input)
    out_path = ROOT / args.output if not Path(args.output).is_absolute() else Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not in_path.exists():
        print(f"[error] input file not found: {in_path}")
        return 1

    with in_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    headers = _headers()
    out_rows: list[dict[str, str]] = []
    proxy_rows = 0

    for row in rows:
        o = {h: (row.get(h) or "").strip() for h in headers}
        flags: list[str] = []

        # normalize basics
        o["format"] = _normalize_format(o.get("format", ""))
        if not o.get("caption", ""):
            o["caption"] = "[no_caption]"
            flags.append("caption_proxy")
        if not o.get("hashtags_count", ""):
            o["hashtags_count"] = "0"
            flags.append("hashtags_proxy")
        if not o.get("media_count", ""):
            o["media_count"] = "1"
            flags.append("media_count_proxy")

        likes = _f(o.get("likes"))
        comments = _f(o.get("comments"))
        followers = _f(o.get("followers"), 1.0)
        views = _f(o.get("views"))
        reach = _f(o.get("reach"))
        impressions = _f(o.get("impressions"))
        saves = _f(o.get("saves"))
        shares = _f(o.get("shares"))
        hashtags = _f(o.get("hashtags_count"))
        media_count = _f(o.get("media_count"), 1.0)

        engagement_proxy_count = likes + 2.0 * comments
        engagement_proxy_rate = (engagement_proxy_count / max(1.0, followers)) * 100.0

        # fill reach/impressions when missing
        if reach <= 0:
            reach_proxy = views if views > 0 else (impressions if impressions > 0 else followers * 0.35)
            o["reach"] = str(round(max(1.0, reach_proxy), 2))
            flags.append("reach_proxy")
            reach = _f(o.get("reach"))
        if impressions <= 0:
            impressions_proxy = impressions if impressions > 0 else max(reach * 1.2, views * 1.05 if views > 0 else 1.0)
            o["impressions"] = str(round(max(1.0, impressions_proxy), 2))
            flags.append("impressions_proxy")
            impressions = _f(o.get("impressions"))

        # saves/shares proxy
        if saves <= 0:
            saves_proxy = max(0.0, likes * 0.18 + comments * 0.4)
            o["saves"] = str(int(round(saves_proxy)))
            flags.append("saves_proxy")
        if shares <= 0:
            shares_proxy = max(0.0, comments * 0.35 + likes * 0.02)
            o["shares"] = str(int(round(shares_proxy)))
            flags.append("shares_proxy")

        # format-specific proxies
        fmt = o.get("format", "")
        if fmt == "reels":
            w3 = _f(o.get("watch_3s_rate"))
            wc = _f(o.get("watch_completion_rate"))
            if w3 <= 0:
                denom = views if views > 0 else max(reach, 1.0)
                w3 = _clamp((engagement_proxy_count / max(1.0, denom)) * 220.0, 8.0, 95.0)
                o["watch_3s_rate"] = str(round(w3, 2))
                flags.append("watch_3s_rate_proxy")
            if wc <= 0:
                wc = _clamp(_f(o.get("watch_3s_rate")) * 0.58, 4.0, 85.0)
                o["watch_completion_rate"] = str(round(wc, 2))
                flags.append("watch_completion_rate_proxy")
        elif fmt == "carousel":
            sw = _f(o.get("carousel_swipe_rate"))
            if sw <= 0:
                base = 22.0 + media_count * 4.0 + min(hashtags, 8.0) * 1.5
                if o.get("caption", "") and o["caption"] != "[no_caption]":
                    base += 5.0
                sw = _clamp(base, 8.0, 95.0)
                o["carousel_swipe_rate"] = str(round(sw, 2))
                flags.append("carousel_swipe_rate_proxy")
        elif fmt == "single":
            pv = _f(o.get("profile_visits"))
            if pv <= 0:
                pv = max(1.0, likes * 0.12 + comments * 0.6)
                o["profile_visits"] = str(int(round(pv)))
                flags.append("profile_visits_proxy")

        o["engagement_proxy_count"] = str(round(engagement_proxy_count, 2))
        o["engagement_proxy_rate"] = str(round(engagement_proxy_rate, 4))
        o["proxy_flags"] = ",".join(flags)
        if flags:
            proxy_rows += 1

        out_rows.append(o)

    with out_path.open("w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=headers)
        wr.writeheader()
        wr.writerows(out_rows)

    print(f"[ok] weaklabel dataset written: {out_path}")
    print(f"[summary] rows={len(out_rows)}, proxy_rows={proxy_rows}, proxy_rate={round((proxy_rows/max(1, len(out_rows)))*100, 2)}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

