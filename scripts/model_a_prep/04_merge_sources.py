"""
여러 source CSV를 Model A raw_posts.csv 포맷으로 정규화/병합.

기본 동작:
- 입력: data/instagram_recalibration/source/*.csv
- 출력: data/instagram_recalibration/raw_posts.csv (upsert by post_id)

Usage:
    python3 scripts/model_a_prep/04_merge_sources.py
"""
from __future__ import annotations

import csv
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.agents.model_a_contract import (  # noqa: E402
    OPTIONAL_RAW_COLUMNS_COMMON,
    REQUIRED_RAW_COLUMNS_COMMON,
    REQUIRED_RAW_COLUMNS_BY_FORMAT,
)


IN_DIR = ROOT / "data" / "instagram_recalibration" / "source"
OUT_FILE = ROOT / "data" / "instagram_recalibration" / "raw_posts.csv"


def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


ALIAS = {
    "post_id": ["post_id", "id", "media_id", "postid", "mediaid"],
    "created_at": ["created_at", "createdat", "date", "published_at", "publishedat", "timestamp"],
    "category": ["category", "niche", "vertical", "topic"],
    "format": ["format", "post_type", "content_type", "media_type", "type"],
    "caption": ["caption", "content", "text", "description"],
    "hashtags_count": ["hashtags_count", "hashtag_count", "hashtags", "tag_count"],
    "media_count": ["media_count", "image_count", "slide_count", "asset_count"],
    "followers": ["followers", "follower_count", "followers_count"],
    "reach": ["reach", "accounts_reached"],
    "impressions": ["impressions"],
    "views": ["views", "video_views", "play_count", "plays"],
    "likes": ["likes", "like_count"],
    "comments": ["comments", "comment_count"],
    "saves": ["saves", "saved", "save_count"],
    "shares": ["shares", "share_count"],
    "watch_3s_rate": ["watch_3s_rate", "3s_hold_rate", "three_second_rate", "watch3srate"],
    "watch_completion_rate": ["watch_completion_rate", "completion_rate", "watch_complete_rate"],
    "carousel_swipe_rate": ["carousel_swipe_rate", "swipe_rate", "carousel_rate"],
    "profile_visits": ["profile_visits", "profile_visit", "profile_clicks"],
}


def _build_reverse_alias() -> dict[str, str]:
    rev: dict[str, str] = {}
    for canonical, arr in ALIAS.items():
        for a in arr:
            rev[_norm_key(a)] = canonical
    return rev


REVERSE_ALIAS = _build_reverse_alias()


def _detect_format(v: str) -> str:
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
    return cols


def _load_existing(headers: list[str]) -> dict[str, dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    if not OUT_FILE.exists():
        return by_id
    with OUT_FILE.open("r", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        for row in rd:
            pid = (row.get("post_id") or "").strip()
            if pid:
                by_id[pid] = {h: (row.get(h) or "") for h in headers}
    return by_id


def main() -> int:
    IN_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    headers = _headers()
    merged = _load_existing(headers)

    source_files = sorted(IN_DIR.glob("*.csv"))
    if not source_files:
        print(f"[warn] no source CSV found in: {IN_DIR}")
        print("[next] place source files under that folder and rerun.")
        return 0

    scanned = 0
    accepted = 0
    skipped_no_post_id = 0

    for fp in source_files:
        with fp.open("r", encoding="utf-8-sig", newline="") as f:
            rd = csv.DictReader(f)
            src_headers = rd.fieldnames or []

            # source header -> canonical
            map_src_to_canonical: dict[str, str] = {}
            for sh in src_headers:
                key = REVERSE_ALIAS.get(_norm_key(sh))
                if key:
                    map_src_to_canonical[sh] = key

            for row in rd:
                scanned += 1
                canonical_row = {h: "" for h in headers}
                for sh, val in row.items():
                    c = map_src_to_canonical.get(sh)
                    if not c:
                        continue
                    canonical_row[c] = (val or "").strip()

                # normalize format
                canonical_row["format"] = _detect_format(canonical_row["format"])
                pid = canonical_row["post_id"].strip()
                if not pid:
                    skipped_no_post_id += 1
                    continue

                # upsert with non-empty overwrite
                prev = merged.get(pid, {h: "" for h in headers})
                out = prev.copy()
                for h in headers:
                    nv = canonical_row.get(h, "")
                    if nv != "":
                        out[h] = nv
                merged[pid] = out
                accepted += 1

    with OUT_FILE.open("w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=headers)
        wr.writeheader()
        for pid in sorted(merged.keys()):
            wr.writerow(merged[pid])

    print(f"[ok] merged source files: {len(source_files)}")
    print(f"[ok] scanned rows: {scanned}")
    print(f"[ok] accepted rows: {accepted}")
    print(f"[ok] unique post_ids in output: {len(merged)}")
    print(f"[warn] skipped rows without post_id: {skipped_no_post_id}")
    print(f"[out] {OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
