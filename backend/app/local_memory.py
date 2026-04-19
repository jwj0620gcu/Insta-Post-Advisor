"""
로컬 메모리 레이어.
Markdown 파일은 사람이 읽기 쉬운 기록원, JSON은 전체 리포트 원본 보관용이다.

디렉터리(backend/data/instarx_workspace):
- MEMORY.md                  장기 설명(수동 편집 가능)
- memory/YYYY-MM-DD.md       일자별 진단 요약 append 로그
- memory/records/{id}.json   단건 전체 리포트(SQLite와 동시 기록)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger("instarx.local_memory")

_DATA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
WORKSPACE_ROOT = os.path.join(_DATA_ROOT, "instarx_workspace")
MEMORY_MD = os.path.join(WORKSPACE_ROOT, "MEMORY.md")
MEMORY_DIR = os.path.join(WORKSPACE_ROOT, "memory")
RECORDS_DIR = os.path.join(MEMORY_DIR, "records")

MEMORY_MD_TEMPLATE = """# InstaRx 로컬 메모리(MEMORY)

이 파일은 **장기 설명 영역**이다. 일별 진단 로그는 `memory/YYYY-MM-DD.md`, 전체 JSON은 `memory/records/`에 저장된다.

## 용도

- 사람이 읽기 쉬움: `grep`, 에디터, 버전관리(git 포함)에 바로 활용 가능
- 원본 데이터는 `memory/records/<id>.json` + SQLite `diagnosis_history`에 이중 기록되어 조회/백업/복구가 쉽다

## 참고

- 이력 삭제 시 `records`의 JSON도 함께 삭제되며, 일별 md에는 삭제 흔적 라인이 남아 감사 추적이 가능하다.
"""


def _ensure_dirs() -> None:
    os.makedirs(RECORDS_DIR, exist_ok=True)


def ensure_memory_md() -> None:
    """MEMORY.md가 없으면 생성한다."""
    _ensure_dirs()
    if not os.path.isfile(MEMORY_MD):
        try:
            with open(MEMORY_MD, "w", encoding="utf-8") as f:
                f.write(MEMORY_MD_TEMPLATE)
            logger.info("로컬 메모리 파일 초기화 완료: %s", MEMORY_MD)
        except OSError as e:
            logger.warning("MEMORY.md 쓰기 실패: %s", e)


def _safe_title(title: str) -> str:
    return (title or "").replace("\n", " ").replace("\r", "").strip()[:120]


def _day_path(when: datetime | None = None) -> str:
    d = when or datetime.now()
    return os.path.join(MEMORY_DIR, f"{d.strftime('%Y-%m-%d')}.md")


def write_diagnosis_record(
    record_id: str,
    title: str,
    category: str,
    overall_score: float,
    grade: str,
    report: dict,
) -> None:
    """
    일자별 Markdown 요약과 records 하위 전체 JSON을 함께 기록한다.
    @param record_id - SQLite 기본 키와 동일
    """
    ensure_memory_md()
    _ensure_dirs()

    title_s = _safe_title(title)
    now = datetime.now()
    time_str = now.strftime("%H:%M:%S")

    payload = {
        "id": record_id,
        "title": title,
        "category": category,
        "overall_score": overall_score,
        "grade": grade,
        "saved_at_local": now.isoformat(timespec="seconds"),
        "report": report,
    }

    json_path = os.path.join(RECORDS_DIR, f"{record_id}.json")
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error("기록 JSON 쓰기 실패 %s: %s", json_path, e)
        return

    day_file = _day_path(now)
    block = (
        f"\n## {time_str} · [{category}] {title_s}\n\n"
        f"- **점수** {overall_score:g} · **등급** {grade}\n"
        f"- **id** `{record_id}`\n"
        f"- **전체 JSON** `memory/records/{record_id}.json`\n\n"
    )
    try:
        existed = os.path.isfile(day_file)
        with open(day_file, "a", encoding="utf-8") as f:
            if not existed:
                f.write(f"# 진단 로그 · {now.strftime('%Y-%m-%d')}\n\n")
            f.write(block)
    except OSError as e:
        logger.warning("일자 로그 append 실패 %s: %s", day_file, e)


def delete_diagnosis_record(record_id: str) -> None:
    """JSON 복사본을 삭제하고 당일 md 말미에 삭제 표시를 append한다."""
    _ensure_dirs()
    json_path = os.path.join(RECORDS_DIR, f"{record_id}.json")
    try:
        if os.path.isfile(json_path):
            os.remove(json_path)
    except OSError as e:
        logger.warning("기록 JSON 삭제 실패 %s: %s", json_path, e)

    now = datetime.now()
    day_file = _day_path(now)
    line = f"\n> 삭제된 기록 `{record_id}` · {now.strftime('%H:%M:%S')}\n\n"
    try:
        with open(day_file, "a", encoding="utf-8") as f:
            if not os.path.isfile(day_file) or os.path.getsize(day_file) == 0:
                f.write(f"# 진단 로그 · {now.strftime('%Y-%m-%d')}\n\n")
            f.write(line)
    except OSError as e:
        logger.warning("삭제 표시 기록 실패 %s: %s", day_file, e)
