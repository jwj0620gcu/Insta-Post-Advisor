"""
진단 이력 CRUD API
"""
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import HistoryCreateRequest, HistoryListItem, HistoryDetail
from app import local_memory
from app.db import get_runtime_connection

router = APIRouter()
logger = logging.getLogger("insta-advisor.history")


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

    conn = get_runtime_connection()
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
    conn = get_runtime_connection()
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

    # 컬럼 순서: id, title, category, overall_score, grade, created_at
    return [
        HistoryListItem(
            id=r[0],
            title=r[1],
            category=r[2],
            overall_score=r[3] or 0,
            grade=r[4] or "",
            created_at=r[5] or "",
        )
        for r in rows
    ]


@router.get("/history/{record_id}", response_model=HistoryDetail)
async def get_history(record_id: str):
    """
    단일 이력 상세를 조회한다(전체 report 포함).
    @param record_id - UUID
    """
    conn = get_runtime_connection()
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

    # 컬럼 순서: id, title, category, overall_score, grade, report_json, created_at
    return HistoryDetail(
        id=row[0],
        title=row[1],
        category=row[2],
        overall_score=row[3] or 0,
        grade=row[4] or "",
        created_at=row[6] or "",
        report=json.loads(row[5]),
    )


@router.delete("/history/{record_id}")
async def delete_history(record_id: str):
    """
    이력 1건을 삭제한다.
    @param record_id - UUID
    """
    conn = get_runtime_connection()
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
