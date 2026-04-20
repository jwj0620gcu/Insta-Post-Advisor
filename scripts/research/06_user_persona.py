"""
Step 6: 사용자 페르소나 시스템
step 1에서 가져온 research_comments를 사용하여 LLM 분류 + 페르소나 생성.

Usage:
    python scripts/research/06_user_persona.py
"""
from __future__ import annotations

import sqlite3
import json
import asyncio
import sys
from pathlib import Path

import httpx
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    RESEARCH_DB, LLM_DIR,
    API_KEY, API_BASE, MODEL_FAST, MODEL_PRO,
    FLASH_CONCURRENCY, ALL_CATEGORIES,
)


def get_client() -> AsyncOpenAI:
    http_client = httpx.AsyncClient(proxy=None, trust_env=False, timeout=httpx.Timeout(120.0, connect=30.0))
    return AsyncOpenAI(api_key=API_KEY, base_url=API_BASE, http_client=http_client)


def ensure_classification_columns(cursor):
    """research_comments 테이블에 LLM 분류 컬럼이 있는지 확인합니다"""
    existing = {r[1] for r in cursor.execute("PRAGMA table_info(research_comments)")}
    additions = {
        "category": "TEXT",
        "sentiment": "TEXT",
        "user_type": "TEXT",
        "intent": "TEXT",
        "emotion_level": "INTEGER",
        "classified_at": "TIMESTAMP",
    }
    for col, dtype in additions.items():
        if col not in existing:
            cursor.execute(f"ALTER TABLE research_comments ADD COLUMN {col} {dtype}")


def assign_categories(cursor):
    """note_id를 통해 댓글에 카테고리를 할당합니다"""
    cursor.execute("""
        UPDATE research_comments
        SET category = (
            SELECT rn.category FROM research_notes rn
            WHERE rn.note_id = research_comments.note_id
        )
        WHERE category IS NULL AND note_id IS NOT NULL AND note_id != ''
    """)
    cursor.execute("SELECT COUNT(*) FROM research_comments WHERE category IS NOT NULL")
    assigned = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM research_comments")
    total = cursor.fetchone()[0]
    print(f"  카테고리 연결: {assigned}/{total} 개 댓글에 카테고리 할당 완료")


# ─── LLM 분류 ───

CLASSIFY_PROMPT = """아래 Instagram 댓글을 분류하세요. 각 댓글에 대해 JSON 객체를 하나씩 출력하세요.

분류 기준:
- sentiment: positive / negative / neutral
- user_type: 추천형 / 경험형 / 의심형 / 구매요청형 / 유머형 / 일반인형
- intent: 칭찬 / 질문 / 경험공유 / 의심 / 링크요청 / 불평 / 상호작용 / 논쟁
- emotion_level: 1-5 (1=평범, 5=격렬)

JSON 배열로 출력:
[
  {{"id": "댓글ID", "sentiment": "...", "user_type": "...", "intent": "...", "emotion_level": N}},
  ...
]

댓글 데이터:
{comments}"""


async def classify_batch(client: AsyncOpenAI, batch: list[dict], semaphore: asyncio.Semaphore) -> list[dict]:
    async with semaphore:
        try:
            comments_text = "\n".join(
                f'ID:{c["id"]} 내용:{c["text"][:100]}'
                for c in batch
            )
            response = await client.chat.completions.create(
                model=MODEL_FAST,
                messages=[
                    {"role": "system", "content": "당신은 댓글 분석 전문가입니다. JSON 배열만 출력하세요."},
                    {"role": "user", "content": CLASSIFY_PROMPT.format(comments=comments_text)},
                ],
                max_completion_tokens=1500,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(raw)
        except Exception as e:
            print(f"    분류 실패: {e}")
            return []


async def run_classification():
    print("\n=== 6.2 LLM 댓글 분류 (mimo-v2-flash) ===")

    conn = sqlite3.connect(RESEARCH_DB)
    cursor = conn.cursor()
    client = get_client()
    semaphore = asyncio.Semaphore(FLASH_CONCURRENCY)

    cursor.execute(
        "SELECT comment_id, content FROM research_comments WHERE sentiment IS NULL AND content != '' LIMIT 5000"
    )
    rows = cursor.fetchall()
    if not rows:
        print("  분류할 댓글 없음")
        conn.close()
        return

    print(f"  분류 대기: {len(rows)} 개")

    batch_size = 10
    total_classified = 0
    tasks = []

    for i in range(0, len(rows), batch_size):
        batch = [{"id": r[0], "text": r[1]} for r in rows[i:i+batch_size]]
        tasks.append((i, classify_batch(client, batch, semaphore)))

    # Run in concurrent batches of 10
    for chunk_start in range(0, len(tasks), 10):
        chunk = tasks[chunk_start:chunk_start+10]
        results = await asyncio.gather(*(t[1] for t in chunk))

        for (i, _), batch_results in zip(chunk, results):
            for r in batch_results:
                cid = r.get("id")
                if not cid:
                    continue
                cursor.execute("""
                    UPDATE research_comments
                    SET sentiment=?, user_type=?, intent=?, emotion_level=?, classified_at=CURRENT_TIMESTAMP
                    WHERE comment_id=?
                """, (r.get("sentiment"), r.get("user_type"), r.get("intent"),
                      r.get("emotion_level"), cid))
                total_classified += 1

        conn.commit()
        done = min(chunk_start + 10, len(tasks)) * batch_size
        print(f"    진행: {min(done, len(rows))}/{len(rows)}")

    print(f"  분류 완료: {total_classified} 개")
    conn.close()
    await client.close()


# ─── 페르소나 생성 ───

PERSONA_PROMPT = """당신은 Instagram 사용자 연구 전문가입니다. 아래는 {category} 카테고리 댓글의 분류 통계 및 예시 댓글입니다.

5-8가지 전형적인 사용자 페르소나를 생성하고 JSON으로 출력하세요:
{{
  "personas": [
    {{
      "name": "페르소나 이름",
      "ratio": 0.30,
      "description": "간단한 설명",
      "language_style": "언어 스타일 특징",
      "typical_phrases": ["자주 쓰는 표현1", "자주 쓰는 표현2", "자주 쓰는 표현3"],
      "comment_templates": ["템플릿1: {{product}} 너무 좋아요!", "템플릿2"],
      "triggers": "어떤 콘텐츠가 이런 댓글을 유발하는지",
      "interaction_style": "좋아요 경향/답글/논쟁/조용히 저장"
    }}
  ],
  "controversy_patterns": [
    {{
      "topic": "논쟁 주제",
      "side_a": "찬성측 의견 템플릿",
      "side_b": "반대측 의견 템플릿",
      "escalation_path": ["시작→", "고조→", "폭발"]
    }}
  ],
  "category_characteristics": "해당 카테고리 댓글 공간의 독특한 생태 설명"
}}

분류 통계:
{stats}

예시 댓글 (유형별 분류):
{examples}"""


async def generate_personas():
    print("\n=== 6.3 사용자 페르소나 생성 (mimo-v2-pro) ===")

    conn = sqlite3.connect(RESEARCH_DB)
    cursor = conn.cursor()
    client = get_client()

    all_personas = {}
    for cat in ALL_CATEGORIES:
        cursor.execute("""
            SELECT user_type, COUNT(*), AVG(emotion_level)
            FROM research_comments
            WHERE category=? AND user_type IS NOT NULL
            GROUP BY user_type
        """, (cat,))
        type_stats = cursor.fetchall()
        if not type_stats:
            continue

        stats = [{"type": r[0], "count": r[1], "avg_emotion": round(r[2] or 0, 1)} for r in type_stats]

        examples = {}
        for s in stats:
            cursor.execute("""
                SELECT content FROM research_comments
                WHERE category=? AND user_type=?
                ORDER BY likes DESC LIMIT 5
            """, (cat, s["type"]))
            examples[s["type"]] = [r[0] for r in cursor.fetchall()]

        prompt = PERSONA_PROMPT.format(
            category=cat,
            stats=json.dumps(stats, ensure_ascii=False, indent=1),
            examples=json.dumps(examples, ensure_ascii=False, indent=1),
        )

        print(f"  [{cat}] 페르소나 생성 중...")
        try:
            response = await client.chat.completions.create(
                model=MODEL_PRO,
                messages=[
                    {"role": "system", "content": "당신은 사용자 연구 전문가입니다. JSON만 출력하세요."},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=3000,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            result = json.loads(raw)
            all_personas[cat] = result
            n = len(result.get("personas", []))
            print(f"    {n}가지 페르소나 생성")
        except Exception as e:
            print(f"    실패: {e}")

    out = LLM_DIR / "user_personas.json"
    out.write_text(json.dumps(all_personas, ensure_ascii=False, indent=2))
    print(f"  → {out}")

    conn.close()
    await client.close()
    return all_personas


async def main():
    print("=" * 60)
    print("Step 6: 사용자 페르소나 시스템")
    print("=" * 60)

    conn = sqlite3.connect(RESEARCH_DB)
    cursor = conn.cursor()

    # 분류 컬럼 존재 확인
    ensure_classification_columns(cursor)

    # note_id를 통해 카테고리 연결
    print("\n=== 6.1 카테고리 연결 ===")
    assign_categories(cursor)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM research_comments WHERE content != ''")
    total = cursor.fetchone()[0]
    conn.close()

    if total > 0:
        print(f"  댓글 총 수: {total}")
        await run_classification()
        await generate_personas()
    else:
        print("\n댓글 데이터가 없습니다. 먼저 01_import_data.py를 실행하여 데이터를 가져오세요.")

    print("\n" + "=" * 60)
    print("Step 6 완료!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
