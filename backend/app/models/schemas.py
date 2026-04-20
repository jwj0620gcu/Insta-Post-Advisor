"""
Pydantic 요청/응답 모델 (Insta-Advisor)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DiagnoseRequest(BaseModel):
    """진단 요청"""
    # 기존 필드 (호환)
    title: str
    content: str = ""
    category: str
    tags: list[str] = []

    # 인스타 확장 필드 (옵션)
    content_format: Optional[str] = None  # single_image / carousel / reels
    goal: Optional[str] = None  # awareness / engagement / inquiry / purchase

    cover_image_url: Optional[str] = None


class AgentOpinion(BaseModel):
    """단일 Agent 의견"""
    agent_name: str
    dimension: str
    score: float
    issues: list[str]
    suggestions: list[str]
    reasoning: str
    debate_comments: list[str] = []


class SimulatedComment(BaseModel):
    """AI 시뮬레이션 댓글"""
    username: str
    avatar_emoji: str
    comment: str
    sentiment: str
    likes: int = 0
    time_ago: str = ""
    ip_location: str = ""
    is_author: bool = False


class DebateEntry(BaseModel):
    """토론 타임라인 엔트리"""
    round: int
    agent_name: str
    kind: str
    text: str


class CoverDirection(BaseModel):
    """커버/썸네일 제안"""
    layout: str = ""
    color_scheme: str = ""
    text_style: str = ""
    tips: list[str] = []


class DiagnoseResponse(BaseModel):
    """진단 결과 응답"""
    overall_score: float
    grade: str
    radar_data: dict
    agent_opinions: list[AgentOpinion]
    issues: list[dict]
    suggestions: list[dict]
    debate_summary: str
    debate_timeline: list[DebateEntry] = []
    simulated_comments: list[SimulatedComment]

    # 기존 필드 (호환)
    optimized_title: Optional[str] = None
    optimized_content: Optional[str] = None
    cover_direction: Optional[CoverDirection] = None

    # 인스타 확장 필드 (옵션)
    recommended_format: Optional[str] = None
    recommended_hashtags: list[str] = []
    best_post_time: Optional[str] = None


# --------------- 히스토리 ---------------

class HistoryCreateRequest(BaseModel):
    """진단 히스토리 저장"""
    title: str
    category: str
    report: dict


class HistoryListItem(BaseModel):
    """히스토리 목록 항목"""
    id: str
    title: str
    category: str
    overall_score: float
    grade: str
    created_at: str


class HistoryDetail(BaseModel):
    """히스토리 상세"""
    id: str
    title: str
    category: str
    overall_score: float
    grade: str
    created_at: str
    report: dict
