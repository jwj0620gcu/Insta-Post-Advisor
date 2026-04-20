"""
Step 4: LLM 심층 분석 (Track B)
커버 비주얼 분석 (omni) + 콘텐츠 패턴 요약 (pro) + 태그 전략 분석 (pro)

Usage:
    python scripts/research/04_llm_analysis.py [--covers] [--content] [--tags] [--all]

의존성:
    pip install openai httpx
"""
from __future__ import annotations

import sqlite3
import json
import asyncio
import argparse
import base64
import sys
from pathlib import Path

import httpx
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    RESEARCH_DB, COVERS_DIR, LLM_DIR,
    API_KEY, API_BASE, MODEL_OMNI, MODEL_PRO, MODEL_FAST,
    OMNI_CONCURRENCY, ALL_CATEGORIES,
)


def get_client() -> AsyncOpenAI:
    http_client = httpx.AsyncClient(proxy=None, trust_env=False, timeout=httpx.Timeout(120.0, connect=30.0))
    return AsyncOpenAI(api_key=API_KEY, base_url=API_BASE, http_client=http_client)


# ─── 4.1 커버 비주얼 분석 ───

COVER_PROMPT = """당신은 Instagram 커버 비주얼 분석 전문가입니다. 이 Instagram 게시글 커버 이미지를 분석하고 JSON 형식으로 출력하세요:

{
  "cover_style": "인물등장/제품클로즈업/장면사진/콜라주/텍스트전용/비교사진/풍경",
  "color_tone": "따뜻한색/차가운색/중성/고채도/저채도",
  "text_overlay": true또는false,
  "text_content": "커버의 텍스트 내용, 텍스트 없으면 빈 문자열",
  "text_area_ratio": 0.0에서1.0사이의숫자,
  "has_face": true또는false,
  "face_expression": "미소/진지함/과장됨/없음",
  "composition": "중앙배치/3분법/대각선/여백/꽉찬구도",
  "visual_quality": 1에서10사이의정수,
  "click_appeal": 1에서10사이의정수,
  "style_tags": ["태그1", "태그2"]
}

JSON만 출력하고 다른 내용은 포함하지 마세요."""


async def analyze_cover(client: AsyncOpenAI, note_id: str, image_path: Path, semaphore: asyncio.Semaphore) -> dict | None:
    """omni 모델로 커버 이미지 한 장을 분석합니다"""
    async with semaphore:
        try:
            img_data = image_path.read_bytes()
            b64 = base64.b64encode(img_data).decode()

            # 이미지 형식 감지
            suffix = image_path.suffix.lower()
            mime = "image/webp" if suffix == ".webp" else "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

            response = await client.chat.completions.create(
                model=MODEL_OMNI,
                messages=[
                    {"role": "system", "content": COVER_PROMPT},
                    {"role": "user", "content": [
                        {"type": "text", "text": "이 Instagram 게시글 커버를 분석해 주세요"},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ]},
                ],
                max_tokens=500,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(raw)
            result["note_id"] = note_id
            return result
        except Exception as e:
            print(f"  커버 분석 실패 {note_id}: {e}")
            return None


async def run_cover_analysis():
    """커버 이미지 일괄 분석"""
    print("\n=== 4.1 커버 비주얼 분석 (mimo-v2-omni) ===")

    conn = sqlite3.connect(RESEARCH_DB)
    cursor = conn.cursor()
    client = get_client()
    semaphore = asyncio.Semaphore(OMNI_CONCURRENCY)

    all_results = {}
    for cat in ALL_CATEGORIES:
        cat_dir = COVERS_DIR / cat
        if not cat_dir.exists():
            continue

        cursor.execute(
            "SELECT note_id FROM research_notes WHERE category=? AND cover_analysis IS NULL",
            (cat,)
        )
        note_ids = {r[0] for r in cursor.fetchall()}

        # 找到已下载的封面
        tasks = []
        for img_path in cat_dir.iterdir():
            nid = img_path.stem
            if nid in note_ids:
                tasks.append((nid, img_path))

        if not tasks:
            continue

        print(f"  [{cat}] {len(tasks)}장의 커버 분석 중...")

        batch_size = 20
        cat_results = []
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i+batch_size]
            coros = [analyze_cover(client, nid, p, semaphore) for nid, p in batch]
            results = await asyncio.gather(*coros)
            for r in results:
                if r:
                    cat_results.append(r)
                    # 데이터베이스 업데이트
                    cursor.execute(
                        "UPDATE research_notes SET cover_analysis=? WHERE note_id=?",
                        (json.dumps(r, ensure_ascii=False), r["note_id"])
                    )
            conn.commit()
            print(f"    배치 {i//batch_size + 1}/{(len(tasks)-1)//batch_size + 1}: {sum(1 for r in results if r)}/{len(batch)} 성공")

        all_results[cat] = cat_results

    # 결과 요약 저장
    out = LLM_DIR / "cover_analysis_all.json"
    out.write_text(json.dumps(all_results, ensure_ascii=False, indent=2))
    print(f"  → {out}")

    conn.close()
    await client.close()
    return all_results


# ─── 4.2 콘텐츠 패턴 분석 ───

CONTENT_PATTERN_PROMPT = """당신은 Instagram 콘텐츠 연구 전문가입니다. 아래는 {category} 카테고리의 인기 게시글 데이터(제목 및 본문 요약)입니다.

분석하고 요약한 결과를 JSON으로 출력하세요:

{{
  "title_patterns": [
    {{"pattern_name": "패턴 이름", "template": "템플릿 문장 형식", "examples": ["예시1", "예시2"], "frequency": "높음/중간/낮음"}}
  ],
  "content_structure": [
    {{"type": "구조 유형", "description": "설명", "typical_flow": ["단락1", "단락2", "..."]}}
  ],
  "high_frequency_words": ["단어1", "단어2", ...],
  "emotion_tone": "카테고리 주류 감성 기조",
  "info_density": "고밀도 정보/중간/가벼운 일상",
  "viral_vs_normal_diff": ["차이점1", "차이점2", ...],
  "key_findings": ["발견1", "발견2", ...]
}}

게시글 데이터:
{notes_json}"""


async def run_content_analysis():
    """카테고리별 콘텐츠 패턴 분석"""
    print("\n=== 4.2 콘텐츠 패턴 분석 (mimo-v2-pro) ===")

    conn = sqlite3.connect(RESEARCH_DB)
    cursor = conn.cursor()
    client = get_client()

    results = {}
    for cat in ALL_CATEGORIES:
        # 인기 게시글 + 일부 일반 게시글 가져오기
        cursor.execute("""
            SELECT title, SUBSTR(content, 1, 200) as excerpt, engagement, is_viral
            FROM research_notes WHERE category=? AND title != ''
            ORDER BY engagement DESC LIMIT 80
        """, (cat,))
        rows = cursor.fetchall()
        if not rows:
            continue

        notes_data = [
            {"title": r[0], "excerpt": r[1], "engagement": r[2], "is_viral": bool(r[3])}
            for r in rows
        ]

        prompt = CONTENT_PATTERN_PROMPT.format(
            category=cat,
            notes_json=json.dumps(notes_data, ensure_ascii=False, indent=1)
        )

        print(f"  [{cat}] {len(rows)}개 게시글 콘텐츠 패턴 분석 중...")
        try:
            response = await client.chat.completions.create(
                model=MODEL_PRO,
                messages=[
                    {"role": "system", "content": "당신은 데이터 분석 전문가입니다. JSON만 출력하세요."},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=3000,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(raw)
            results[cat] = result
            print(f"    {len(result.get('title_patterns', []))}가지 제목 패턴 발견")
        except Exception as e:
            print(f"    실패: {e}")

    out = LLM_DIR / "content_patterns.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"  → {out}")

    conn.close()
    await client.close()
    return results


# ─── 4.3 태그 전략 분석 ───

TAG_ANALYSIS_PROMPT = """다음 {category} 카테고리 게시글의 태그 사용 전략을 분석하세요. 데이터에는 각 게시글의 태그 목록과 인터랙션 데이터가 포함되어 있습니다.

JSON으로 출력하세요:
{{
  "top_tags": [{{"tag": "태그", "count": 수량, "avg_engagement": 평균인터랙션}}],
  "hidden_gems": [{{"tag": "롱테일태그", "avg_engagement": 평균인터랙션, "note_count": 사용수량}}],
  "best_combinations": [{{"tags": ["태그1", "태그2", "태그3"], "avg_engagement": 평균인터랙션}}],
  "optimal_tag_count": {{"min": 최소, "max": 최대, "best": 최적}},
  "strategy_advice": ["조언1", "조언2", ...]
}}

데이터:
{data_json}"""


async def run_tag_analysis():
    """태그 전략 분석"""
    print("\n=== 4.3 태그 전략 분석 (mimo-v2-pro) ===")

    conn = sqlite3.connect(RESEARCH_DB)
    cursor = conn.cursor()
    client = get_client()

    results = {}
    for cat in ALL_CATEGORIES:
        cursor.execute("""
            SELECT tags, engagement, is_viral
            FROM research_notes WHERE category=? AND tags IS NOT NULL
        """, (cat,))
        rows = cursor.fetchall()
        if not rows:
            continue

        data = [
            {"tags": json.loads(r[0]) if r[0] else [], "engagement": r[1], "is_viral": bool(r[2])}
            for r in rows
        ]

        prompt = TAG_ANALYSIS_PROMPT.format(
            category=cat,
            data_json=json.dumps(data[:100], ensure_ascii=False, indent=1)  # 限制大小
        )

        print(f"  [{cat}] {len(rows)}개 게시글 태그 전략 분석 중...")
        try:
            response = await client.chat.completions.create(
                model=MODEL_PRO,
                messages=[
                    {"role": "system", "content": "당신은 데이터 분석 전문가입니다. JSON만 출력하세요."},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=2000,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(raw)
            results[cat] = result
            print(f"    최적 태그 수: {result.get('optimal_tag_count', {}).get('best', '?')}")
        except Exception as e:
            print(f"    실패: {e}")

    out = LLM_DIR / "tag_analysis.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"  → {out}")

    conn.close()
    await client.close()
    return results


# ─── Main ───

async def main():
    parser = argparse.ArgumentParser(description="LLM 심층 분석")
    parser.add_argument("--covers", action="store_true", help="커버 비주얼 분석 실행")
    parser.add_argument("--content", action="store_true", help="콘텐츠 패턴 분석 실행")
    parser.add_argument("--tags", action="store_true", help="태그 전략 분석 실행")
    parser.add_argument("--all", action="store_true", help="전체 분석 실행")
    args = parser.parse_args()

    if not any([args.covers, args.content, args.tags, args.all]):
        args.all = True

    print("=" * 60)
    print("Step 4: LLM 심층 분석 (Track B)")
    print("=" * 60)

    if args.covers or args.all:
        await run_cover_analysis()
    if args.content or args.all:
        await run_content_analysis()
    if args.tags or args.all:
        await run_tag_analysis()

    print("\n" + "=" * 60)
    print(f"Track B 완료! 결과 저장 위치: {LLM_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
