"""
Step 2: 커버 이미지 일괄 다운로드
research.db에서 cover_url을 읽어 data/covers/{category}/ 에 병렬 다운로드합니다.

Usage:
    python scripts/research/02_download_covers.py
"""
import sqlite3
import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from config import RESEARCH_DB, COVERS_DIR, DOWNLOAD_CONCURRENCY, ALL_CATEGORIES


async def download_one(client: httpx.AsyncClient, url: str, dest: Path, semaphore: asyncio.Semaphore) -> bool:
    """이미지 한 장을 다운로드합니다"""
    if dest.exists():
        return True  # 이미 다운로드됨
    if not url or not url.startswith("http"):
        return False

    async with semaphore:
        try:
            resp = await client.get(url, follow_redirects=True, timeout=30.0)
            if resp.status_code == 200 and len(resp.content) > 1000:
                dest.write_bytes(resp.content)
                return True
        except Exception:
            pass
    return False


async def main():
    print("=" * 60)
    print("Step 2: 커버 이미지 다운로드")
    print("=" * 60)

    conn = sqlite3.connect(RESEARCH_DB)
    cursor = conn.cursor()

    semaphore = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)

    async with httpx.AsyncClient(
        proxy=None, trust_env=False,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=httpx.Timeout(30.0)
    ) as client:
        for cat in ALL_CATEGORIES:
            cat_dir = COVERS_DIR / cat
            cat_dir.mkdir(parents=True, exist_ok=True)

            cursor.execute(
                "SELECT note_id, cover_url FROM research_notes WHERE category=? AND cover_url IS NOT NULL AND cover_url != ''",
                (cat,)
            )
            rows = cursor.fetchall()
            if not rows:
                continue

            print(f"\n[{cat}] {len(rows)}장 다운로드 대기 중")

            tasks = []
            for note_id, url in rows:
                ext = ".webp"
                if ".jpg" in url or ".jpeg" in url:
                    ext = ".jpg"
                elif ".png" in url:
                    ext = ".png"
                dest = cat_dir / f"{note_id}{ext}"
                tasks.append(download_one(client, url, dest, semaphore))

            results = await asyncio.gather(*tasks)
            success = sum(results)
            print(f"  성공: {success}/{len(rows)}")

    conn.close()
    print("\n커버 이미지가 저장된 경로:", COVERS_DIR)


if __name__ == "__main__":
    asyncio.run(main())
