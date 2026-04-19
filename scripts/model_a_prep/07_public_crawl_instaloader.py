"""
공개 Instagram 계정 메타데이터를 수집해 Model A 준비용 source CSV를 생성한다.

주의:
- 로그인 없이 수집하면 계정/콘텐츠 접근 제한에 따라 실패할 수 있다.
- Instagram 정책/약관은 사용자 책임 하에 준수해야 한다.

출력 컬럼(merge 스크립트와 호환):
- post_id, created_at, category, format, caption, hashtags_count, media_count
- followers, likes, comments, views

예시:
  python3 scripts/model_a_prep/07_public_crawl_instaloader.py \
    --pair fashion:nike --pair food:starbucks \
    --per-account 20
"""
from __future__ import annotations

import argparse
import csv
import os
import re
from datetime import datetime
from getpass import getpass
from pathlib import Path
from typing import Iterable

import instaloader
from instaloader.exceptions import TwoFactorAuthRequiredException
from instaloader.instaloader import (
    get_default_session_filename,
    get_legacy_session_filename,
)


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "instagram_recalibration" / "source"

DEFAULT_PAIRS = [
    "fashion:nike",
    "food:starbucks",
    "fitness:nike",
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
        help="category:username 형태. 여러 번 전달 가능 (예: --pair fashion:nike)",
    )
    p.add_argument("--per-account", type=int, default=15, help="계정당 수집 게시물 수")
    p.add_argument(
        "--output",
        default="",
        help="출력 경로 (기본: data/instagram_recalibration/source/public_crawl_YYYYmmdd_HHMMSS.csv)",
    )
    p.add_argument(
        "--use-login",
        action="store_true",
        help="로그인 세션 사용(권장). 계정 정보는 인자 또는 환경변수에서 읽음",
    )
    p.add_argument("--login-user", default="", help="Instagram username (기본: INSTAGRAM_ID)")
    p.add_argument("--login-pass", default="", help="Instagram password (기본: INSTAGRAM_PASSWORD)")
    p.add_argument(
        "--session-file",
        default="",
        help="instaloader 세션 파일 경로(기본: data/instagram_recalibration/source/.instaloader_session_<user>)",
    )
    p.add_argument(
        "--prompt-pass",
        action="store_true",
        help="환경변수 비밀번호를 무시하고 TTY에서 비밀번호를 직접 입력",
    )
    return p.parse_args()


def _hashtags_count(caption: str) -> int:
    return len(re.findall(r"#\w+", caption or ""))


def _format_from_post(post: instaloader.Post) -> str:
    if post.typename == "GraphSidecar":
        return "carousel"
    if post.is_video:
        return "reels"
    return "single"


def _safe_int(v) -> int:
    if v is None:
        return 0
    try:
        return int(v)
    except Exception:
        return 0


def _iter_pairs(raw_pairs: list[str]) -> Iterable[tuple[str, str]]:
    pairs = raw_pairs if raw_pairs else DEFAULT_PAIRS
    for pair in pairs:
        if ":" not in pair:
            continue
        category, username = pair.split(":", 1)
        category = category.strip().lower()
        username = username.strip().lstrip("@")
        if not category or not username:
            continue
        yield category, username


def _resolve_creds(args: argparse.Namespace) -> tuple[str, str]:
    user = (args.login_user or os.getenv("INSTAGRAM_ID", "")).strip()
    if args.prompt_pass:
        password = (args.login_pass or "").strip()
    else:
        password = (args.login_pass or os.getenv("INSTAGRAM_PASSWORD", "")).strip()
    return user, password


def main() -> int:
    args = _args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.output:
        out_file = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = OUT_DIR / f"public_crawl_{ts}.csv"

    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
    )

    # Optional login flow (recommended for stable crawling)
    if args.use_login:
        user, password = _resolve_creds(args)
        if not user:
            print("[error] login user missing. pass --login-user or export INSTAGRAM_ID")
            return 2

        # Session load order:
        # 1) explicit --session-file
        # 2) project-local session
        # 3) instaloader default session path
        # 4) instaloader legacy tmp session path
        candidate_paths: list[Path] = []
        if args.session_file:
            candidate_paths.append(Path(args.session_file).expanduser())
        else:
            candidate_paths.extend(
                [
                    OUT_DIR / f".instaloader_session_{user}",
                    Path(get_default_session_filename(user)).expanduser(),
                    Path(get_legacy_session_filename(user)).expanduser(),
                ]
            )

        logged_in = False
        for p in candidate_paths:
            if not p.exists():
                continue
            try:
                loader.load_session_from_file(user, str(p))
                current = loader.test_login()
                if current:
                    logged_in = True
                    print(f"[ok] loaded session: {current} ({p})")
                    break
            except Exception as e:
                print(f"[warn] failed to load session file {p}: {e}")

        if not logged_in:
            if args.prompt_pass and os.isatty(0):
                password = getpass("Instagram password: ").strip()
            elif not password and os.isatty(0):
                password = getpass("Instagram password: ").strip()
            if not password:
                print("[error] session unavailable and password missing. pass --login-pass or export INSTAGRAM_PASSWORD")
                return 2
            try:
                loader.login(user, password)
            except TwoFactorAuthRequiredException:
                if not os.isatty(0):
                    print("[error] 2FA required but stdin is not interactive.")
                    return 2
                code = input("2FA code: ").strip()
                if not code:
                    print("[error] empty 2FA code")
                    return 2
                loader.two_factor_login(code)
            except Exception as e:
                print(f"[error] login failed: {e}")
                return 2

            # Save both to project-local and default session path
            session_file = OUT_DIR / f".instaloader_session_{user}"
            try:
                loader.save_session_to_file(str(session_file))
                loader.save_session_to_file()  # default session path
                print(f"[ok] login success; session saved: {session_file}")
            except Exception as e:
                print(f"[warn] login succeeded but failed to persist session: {e}")
                return 2
    else:
        print("[info] running in no-login mode (may fail due to IG rate/authorization)")

    rows: list[dict[str, str]] = []
    failed: list[str] = []
    for category, username in _iter_pairs(args.pair):
        try:
            profile = instaloader.Profile.from_username(loader.context, username)
            followers = _safe_int(profile.followers)
            count = 0
            for post in profile.get_posts():
                rows.append(
                    {
                        "post_id": str(post.shortcode),
                        "created_at": post.date_utc.strftime("%Y-%m-%d %H:%M:%S"),
                        "category": category,
                        "format": _format_from_post(post),
                        "caption": (post.caption or "").replace("\x00", " "),
                        "hashtags_count": str(_hashtags_count(post.caption or "")),
                        "media_count": str(post.mediacount if post.typename == "GraphSidecar" else 1),
                        "followers": str(followers),
                        "likes": str(_safe_int(post.likes)),
                        "comments": str(_safe_int(post.comments)),
                        "views": str(_safe_int(post.video_view_count if post.is_video else 0)),
                    }
                )
                count += 1
                if count >= args.per_account:
                    break
            print(f"[ok] {username}: {count} posts")
        except Exception as e:
            failed.append(f"{category}:{username} ({e})")
            print(f"[warn] {category}:{username} failed: {e}")

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
        for it in failed:
            print(f"  - {it}")
    print("[next] run: make modela-prep-crawl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
