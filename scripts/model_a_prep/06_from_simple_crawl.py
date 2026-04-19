"""
간단 크롤링 결과(예: date/text/like/image) -> source CSV 변환기.

지원 입력:
- CSV 기본
- XLSX (pandas 설치 시)

입력 컬럼 별칭:
- date / created_at / time
- text / caption / content
- like / likes / like_count
- image / image_url / media_url
- brand / account (선택)

출력:
- data/instagram_recalibration/source/converted_<name>.csv

Usage:
  python3 scripts/model_a_prep/06_from_simple_crawl.py \
    --input /path/to/instagram.xlsx \
    --category fashion \
    --format single \
    --followers 500000
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "instagram_recalibration" / "source"


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="input csv/xlsx path")
    p.add_argument(
        "--category",
        required=True,
        choices=("food", "fashion", "fitness", "business", "lifestyle", "travel", "education", "shop"),
    )
    p.add_argument(
        "--format",
        dest="content_format",
        default="single",
        choices=("reels", "carousel", "single"),
        help="fallback format when source has no format column",
    )
    p.add_argument("--followers", type=int, default=10000, help="fallback followers count")
    p.add_argument("--output", default="", help="optional explicit output csv path")
    return p.parse_args()


def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _pick(row: dict[str, str], *cands: str) -> str:
    norm = {_norm_key(k): v for k, v in row.items()}
    for c in cands:
        v = norm.get(_norm_key(c))
        if v is not None:
            return str(v).strip()
    return ""


def _parse_count(s: str) -> int:
    t = (s or "").strip().lower().replace(",", "")
    if not t:
        return 0
    # e.g. 1.2k / 3m / 4.5b
    m = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([kmb])", t)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[unit]
        return int(round(num * mult))
    # korean unit (만/천)
    m2 = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(만|천)", t)
    if m2:
        num = float(m2.group(1))
        mult = 10_000 if m2.group(2) == "만" else 1_000
        return int(round(num * mult))
    # plain int
    try:
        return int(float(t))
    except ValueError:
        return 0


def _parse_date(s: str) -> str:
    v = (s or "").strip()
    if not v:
        return ""
    # try common parse
    candidates = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%b %d, %Y", "%Y.%m.%d")
    for fmt in candidates:
        try:
            dt = datetime.strptime(v, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    # fallback as-is (validator will catch if bad)
    return v


def _hashtags_count(text: str) -> int:
    return len(re.findall(r"#\w+", text or ""))


def _post_id(created_at: str, image_url: str, caption: str) -> str:
    raw = f"{created_at}|{image_url}|{caption[:80]}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _read_rows(path: Path) -> list[dict[str, str]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    if path.suffix.lower() in (".xlsx", ".xls"):
        try:
            import pandas as pd  # type: ignore
        except Exception as e:
            raise RuntimeError("XLSX 입력에는 pandas/openpyxl이 필요합니다. `pip install pandas openpyxl`") from e
        df = pd.read_excel(path)
        return [{str(k): ("" if v is None else str(v)) for k, v in r.items()} for r in df.to_dict(orient="records")]
    raise RuntimeError(f"unsupported input extension: {path.suffix}")


def main() -> int:
    args = _args()
    inp = Path(args.input)
    if not inp.exists():
        print(f"[error] input not found: {inp}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.output:
        out = Path(args.output)
    else:
        out = OUT_DIR / f"converted_{inp.stem}.csv"

    rows = _read_rows(inp)
    if not rows:
        print("[warn] input rows=0")
        return 0

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

    out_rows: list[dict[str, str]] = []
    for row in rows:
        created_at = _parse_date(_pick(row, "created_at", "date", "time"))
        caption = _pick(row, "caption", "text", "content", "description")
        like_raw = _pick(row, "likes", "like", "like_count")
        image_url = _pick(row, "image", "image_url", "media_url")
        format_raw = _pick(row, "format", "post_type", "content_type", "media_type")
        if not format_raw:
            format_raw = args.content_format

        # normalize format lightly
        f = format_raw.strip().lower()
        if f in ("reel", "reels", "video", "short", "shorts", "clip", "clips"):
            f = "reels"
        elif f in ("carousel", "album", "multi", "gallery"):
            f = "carousel"
        elif f in ("single", "image", "photo", "feed"):
            f = "single"
        else:
            f = args.content_format

        likes = _parse_count(like_raw)
        comments = _parse_count(_pick(row, "comments", "comment_count"))
        views = _parse_count(_pick(row, "views", "video_views", "play_count", "plays"))
        followers = _parse_count(_pick(row, "followers", "follower_count", "followers_count")) or int(args.followers)
        pid = _pick(row, "post_id", "id", "media_id", "postid", "mediaid") or _post_id(created_at, image_url, caption)

        out_rows.append(
            {
                "post_id": pid,
                "created_at": created_at,
                "category": args.category,
                "format": f,
                "caption": caption,
                "hashtags_count": str(_hashtags_count(caption)),
                "media_count": "1",
                "followers": str(followers),
                "likes": str(likes),
                "comments": str(comments),
                "views": str(views),
            }
        )

    with out.open("w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fieldnames)
        wr.writeheader()
        wr.writerows(out_rows)

    print(f"[ok] converted rows={len(out_rows)}")
    print(f"[out] {out}")
    print("[next] run: make modela-prep-crawl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

