"""
진단 이력 CRUD API
"""
import json
import logging
import os
import sqlite3
import uuid

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import HistoryCreateRequest, HistoryListItem, HistoryDetail
from app import local_memory

router = APIRouter()
logger = logging.getLogger("insta-advisor.history")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "baseline.db")


def _get_conn() -> sqlite3.Connection:
    """SQLite 연결을 열고 `row_factory=Row`로 설정한다."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.post("/history", response_model=dict)
async def create_history(req: HistoryCreateRequest):
    """
    진단 이력 1건을 저장한다.
    @param req - title, category, report(전체 DiagnoseResponse dict) 포함
    @returns {id: str} 신규 UUID
    """
    record_id = uuid.uuid4().hex
    report = req.report
    overall_score = report.get("overall_score", 0)
    grade = report.get("grade", "")

    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO diagnosis_history
               (id, title, category, overall_score, grade, report_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (record_id, req.title, req.category, overall_score, grade, json.dumps(report, ensure_ascii=False)),
        )
        conn.commit()
    except Exception as e:
        logger.error("진단 이력 저장 실패: %s", e)
        raise HTTPException(500, "저장 실패")
    finally:
        conn.close()

    try:
        local_memory.write_diagnosis_record(
            record_id, req.title, req.category, float(overall_score or 0), grade or "", report
        )
    except Exception as e:
        logger.warning("로컬 메모리 파일 기록 실패(데이터베이스에는 영향 없음): %s", e)

    return {"id": record_id}


@router.get("/history", response_model=list[HistoryListItem])
async def list_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    이력 목록을 최신순으로 조회한다(전체 report JSON 제외).
    @param limit - 페이지당 개수(기본 20, 최대 100)
    @param offset - 오프셋
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT id, title, category, overall_score, grade, created_at
               FROM diagnosis_history
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
    finally:
        conn.close()

    return [
        HistoryListItem(
            id=r["id"],
            title=r["title"],
            category=r["category"],
            overall_score=r["overall_score"] or 0,
            grade=r["grade"] or "",
            created_at=r["created_at"] or "",
        )
        for r in rows
    ]


@router.get("/history/{record_id}", response_model=HistoryDetail)
async def get_history(record_id: str):
    """
    단일 이력 상세를 조회한다(전체 report 포함).
    @param record_id - UUID
    """
    conn = _get_conn()
    try:
        row = conn.execute(
            """SELECT id, title, category, overall_score, grade, report_json, created_at
               FROM diagnosis_history WHERE id = ?""",
            (record_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(404, "기록을 찾을 수 없습니다")

    return HistoryDetail(
        id=row["id"],
        title=row["title"],
        category=row["category"],
        overall_score=row["overall_score"] or 0,
        grade=row["grade"] or "",
        created_at=row["created_at"] or "",
        report=json.loads(row["report_json"]),
    )


@router.delete("/history/{record_id}")
async def delete_history(record_id: str):
    """
    이력 1건을 삭제한다.
    @param record_id - UUID
    """
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM diagnosis_history WHERE id = ?", (record_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "기록을 찾을 수 없습니다")
    finally:
        conn.close()

    try:
        local_memory.delete_diagnosis_record(record_id)
    except Exception as e:
        logger.warning("로컬 메모리 파일 삭제 중 오류: %s", e)

    return {"ok": True}
