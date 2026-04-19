"""
로그인 없이 공개 프로필 Web API를 사용해 source CSV를 생성한다.

주의:
- Instagram 정책/약관은 사용자 책임 하에 준수해야 한다.
- 공개 프로필/게시물만 대상이며, 엔드포인트 변경 시 실패할 수 있다.

출력 컬럼:
post_id, created_at, category, format, caption, hashtags_count, media_count,
followers, likes, comments, views

예시:
  python3 scripts/model_a_prep/08_public_crawl_webapi.py \
    --pair fashion:nike --pair food:starbucks --per-account 12
"""
from __future__ import annotations

import argparse
import csv
import random
import re
import time
from datetime import datetime
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "instagram_recalibration" / "source"
PROFILE_API = "https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"

# 공개 웹 요청에서 널리 사용되는 헤더
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "X-IG-App-ID": "936619743392459",
    "Accept": "*/*",
}

DEFAULT_PAIRS = [
    "fashion:nike",
    "food:starbucks",
    "fitness:adidas",
    "business:shopify",
    "lifestyle:airbnb",
    "travel:lonelyplanet",
    "education:ted",
    "shop:amazon",
]


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--pair",
        action="append",
        default=[],
        help="category:username 형식 (여러 번 가능). 미입력 시 기본 샘플 사용",
    )
    p.add_argument("--per-account", type=int, default=12, help="계정당 최대 게시물 수(기본 12)")
    p.add_argument("--output", default="", help="출력 파일 경로 지정(선택)")
    p.add_argument("--sleep-min", type=float, default=1.0, help="계정 간 최소 대기(초)")
    p.add_argument("--sleep-max", type=float, default=2.0, help="계정 간 최대 대기(초)")
    return p.parse_args()


def _iter_pairs(raw_pairs: list[str]) -> list[tuple[str, str]]:
    pairs = raw_pairs if raw_pairs else DEFAULT_PAIRS
    parsed: list[tuple[str, str]] = []
    for it in pairs:
        if ":" not in it:
            continue
        category, username = it.split(":", 1)
        category = category.strip().lower()
        username = username.strip().lstrip("@")
        if category and username:
            parsed.append((category, username))
    return parsed


def _extract_caption(node: dict) -> str:
    edges = (((node.get("edge_media_to_caption") or {}).get("edges")) or [])
    if not edges:
        return ""
    cnode = edges[0].get("node") or {}
    return str(cnode.get("text") or "")


def _hashtags_count(caption: str) -> int:
    return len(re.findall(r"#\w+", caption))


def _format_from_node(node: dict) -> str:
    t = node.get("__typename")
    if t == "GraphSidecar":
        return "carousel"
    if bool(node.get("is_video")):
        return "reels"
    return "single"


def _media_count(node: dict) -> int:
    sidecar = (node.get("edge_sidecar_to_children") or {}).get("edges") or []
    if sidecar:
        return len(sidecar)
    return 1


def _likes(node: dict) -> int:
    a = (node.get("edge_liked_by") or {}).get("count")
    if isinstance(a, int):
        return a
    b = (node.get("edge_media_preview_like") or {}).get("count")
    return int(b) if isinstance(b, int) else 0


def _comments(node: dict) -> int:
    c = (node.get("edge_media_to_comment") or {}).get("count")
    return int(c) if isinstance(c, int) else 0


def _fetch_profile(username: str, timeout: int = 20) -> dict:
    url = PROFILE_API.format(username=username)
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    if r.status_code == 401:
        msg = ""
        try:
            msg = (r.json() or {}).get("message", "")
        except Exception:
            msg = r.text[:200]
        raise RuntimeError(f"401 unauthorized: {msg}")
    r.raise_for_status()
    payload = r.json()
    user = (payload.get("data") or {}).get("user") or {}
    if not user:
        raise RuntimeError("user payload empty")
    return user


def main() -> int:
    args = _args()
    pairs = _iter_pairs(args.pair)
    if not pairs:
        print("[error] no valid pair provided")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.output:
        out_file = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = OUT_DIR / f"public_webapi_{ts}.csv"

    rows: list[dict[str, str]] = []
    failed: list[str] = []
    per = max(1, min(args.per_account, 50))

    for idx, (category, username) in enumerate(pairs):
        try:
            user = _fetch_profile(username)
            followers = int(((user.get("edge_followed_by") or {}).get("count")) or 0)
            edges = (((user.get("edge_owner_to_timeline_media") or {}).get("edges")) or [])[:per]

            imported = 0
            for edge in edges:
                node = edge.get("node") or {}
                shortcode = str(node.get("shortcode") or "").strip()
                ts = node.get("taken_at_timestamp")
                if not shortcode or not isinstance(ts, int):
                    continue
                caption = _extract_caption(node).replace("\x00", " ")
                rows.append(
                    {
                        "post_id": shortcode,
                        "created_at": datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S"),
                        "category": category,
                        "format": _format_from_node(node),
                        "caption": caption,
                        "hashtags_count": str(_hashtags_count(caption)),
                        "media_count": str(_media_count(node)),
                        "followers": str(followers),
                        "likes": str(_likes(node)),
                        "comments": str(_comments(node)),
                        "views": str(int(node.get("video_view_count") or 0)),
                    }
                )
                imported += 1
            print(f"[ok] {username}: imported={imported}, followers={followers}")
        except Exception as e:
            failed.append(f"{category}:{username} ({e})")
            print(f"[warn] {category}:{username} failed: {e}")

        if idx < len(pairs) - 1:
            time.sleep(random.uniform(args.sleep_min, args.sleep_max))

    fieldnames = [
        "post_id",
        "created_at",
        "category",
        "format",
        "caption",
        "hashtags_count",
        "media_count",
        "followers",
        "likes",
        "comments",
        "views",
    ]
    if rows:
        with out_file.open("w", encoding="utf-8", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=fieldnames)
            wr.writeheader()
            wr.writerows(rows)
        print(f"[out] {out_file}")
    else:
        print("[out] skipped (rows=0, empty source file not written)")

    print(f"[summary] rows={len(rows)}, failed_accounts={len(failed)}")
    if failed:
        print("[failed]")
        for item in failed:
            print(f"  - {item}")
    # 차단 시나리오 가이드
    if rows == 0 and failed:
        lower = " ".join(failed).lower()
        if "401 unauthorized" in lower or "require_login" in lower or "please wait a few minutes" in lower:
            print("[hint] Instagram no-login endpoint blocked on current IP/session.")
            print("[hint] wait cooldown and retry later, or switch to other data source.")
            print("[hint] existing source CSVs remain usable by `make modela-prep-crawl`.")
            return 2
    print("[next] run: make modela-prep-crawl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
