"""
Model A 재보정용 raw 데이터 템플릿 생성 스크립트.

Usage:
    python3 scripts/model_a_prep/01_generate_template.py
"""
from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.agents.model_a_contract import (  # noqa: E402
    FEATURE_CONTRACT_VERSION,
    OPTIONAL_RAW_COLUMNS_COMMON,
    REQUIRED_RAW_COLUMNS_COMMON,
    REQUIRED_RAW_COLUMNS_BY_FORMAT,
)


OUT_DIR = ROOT / "data" / "instagram_recalibration"
OUT_FILE = OUT_DIR / "raw_posts.csv"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 모든 포맷 추가 컬럼을 합쳐 단일 템플릿으로 생성
    extra_cols: list[str] = []
    for cols in REQUIRED_RAW_COLUMNS_BY_FORMAT.values():
        for c in cols:
            if c not in extra_cols:
                extra_cols.append(c)

    headers = list(REQUIRED_RAW_COLUMNS_COMMON) + extra_cols + list(OPTIONAL_RAW_COLUMNS_COMMON)

    if not OUT_FILE.exists():
        with OUT_FILE.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        print(f"[ok] template created: {OUT_FILE}")
    else:
        # 기존 파일이 있어도 헤더 drift를 자동 보정
        with OUT_FILE.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            old_headers = reader.fieldnames or []
            rows = list(reader)

        if old_headers == headers:
            print(f"[skip] template already up-to-date: {OUT_FILE}")
        else:
            with OUT_FILE.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for r in rows:
                    writer.writerow({h: r.get(h, "") for h in headers})
            print(f"[ok] template updated (header sync): {OUT_FILE}")

    print(f"[info] feature contract version: {FEATURE_CONTRACT_VERSION}")
    print("[next] fill CSV rows, then run:")
    print("       python3 scripts/model_a_prep/02_validate_dataset.py --input data/instagram_recalibration/raw_posts.csv")


if __name__ == "__main__":
    main()
