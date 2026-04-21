"""
멀티 에이전트 오케스트레이터
진단 플로우: 파싱 → baseline 비교 → 병렬 Agent 진단 → 토론 → 종합 심사.
모델 분배: pro(심층 분석) / omni(이미지 이해) / fast(빠른 작업)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Optional, Callable, Awaitable, Any

from app.analysis.text_analyzer import TextAnalyzer
from app.analysis.image_analyzer import ImageAnalyzer
from app.baseline.comparator import BaselineComparator
from app.agents.base_agent import MODEL_PRO, MODEL_FAST, _llm_provider
from app.agents.research_data import pre_score
from app.agents.content_agent import ContentAgent
from app.agents.visual_agent import VisualAgent
from app.agents.growth_agent import GrowthAgent
from app.agents.user_sim_agent import UserSimAgent
from app.agents.judge_agent import JudgeAgent
from app.agents.base_agent import _is_mimo_openai_compat
from app.agents.prompts.debate import DEBATE_PROMPT

logger = logging.getLogger("insta-advisor.orchestrator")


def _clamp_score(value: float) -> float:
    """Clamp to 0-100 and round to 1 decimal."""
    return round(min(max(value, 0.0), 100.0), 1)


def _build_carousel_summary(analyses: list[dict]) -> dict:
    """
    캐러셀 다중 이미지 분석 결과를 요약한다.
    첫 슬라이드(후킹), 마지막 슬라이드(CTA), 전체 색감 일관성을 계산한다.
    """
    count = len(analyses)
    if count == 0:
        return {}

    first = analyses[0]
    last = analyses[-1]

    saturations = [float(a.get("saturation", 0)) for a in analyses]
    brightnesses = [float(a.get("brightness", 0)) for a in analyses]

    sat_mean = sum(saturations) / count
    bri_mean = sum(brightnesses) / count
    sat_std = (sum((s - sat_mean) ** 2 for s in saturations) / count) ** 0.5
    bri_std = (sum((b - bri_mean) ** 2 for b in brightnesses) / count) ** 0.5

    # 색감 일관성: 편차가 낮을수록 높은 점수 (캐러셀은 일관성이 중요)
    sat_consistency = max(0.0, 1.0 - sat_std * 5.0)
    bri_consistency = max(0.0, 1.0 - bri_std * 5.0)
    consistency_score = round((sat_consistency + bri_consistency) / 2 * 100, 1)

    # 마지막 슬라이드 텍스트 비율이 높으면 CTA 슬라이드로 추정
    last_text_ratio = float(last.get("text_ratio", 0))
    last_likely_cta = last_text_ratio > 0.25

    # 슬라이드 수 적정성: 8-10장 최적
    slide_count_verdict = (
        "최적 (8-10장)" if 8 <= count <= 10
        else "적음 (8장 이상 권장)" if count < 8
        else "많음 (10장 이하 권장)"
    )

    return {
        "slide_count": count,
        "slide_count_verdict": slide_count_verdict,
        "first_slide": {
            "saturation": round(float(first.get("saturation", 0)), 3),
            "brightness": round(float(first.get("brightness", 0)), 3),
            "has_face": bool(first.get("has_face")),
            "text_ratio": round(float(first.get("text_ratio", 0)), 3),
            "aspect_ratio": round(float(first.get("aspect_ratio", 0)), 2),
        },
        "last_slide": {
            "text_ratio": round(last_text_ratio, 3),
            "likely_cta": last_likely_cta,
            "saturation": round(float(last.get("saturation", 0)), 3),
        },
        "consistency": {
            "score": consistency_score,
            "saturation_std": round(sat_std, 3),
            "brightness_std": round(bri_std, 3),
        },
        "avg_saturation": round(sat_mean, 3),
        "avg_brightness": round(bri_mean, 3),
        "any_face": any(bool(a.get("has_face")) for a in analyses),
    }


def _build_stable_scores(
    model_a_score: dict,
    content_analysis: dict,
    image_analysis: dict | None,
    video_analysis: dict | None,
    carousel_summary: dict | None = None,
) -> dict[str, float]:
    """
    Model A 사전 평가 + 텍스트/이미지 분석으로 결정론적 레이더 점수를 산출한다.
    LLM 출력 불필요 → 동일 입력에 항상 동일 점수 반환.
    """
    dims = model_a_score.get("dimensions", {})
    title_quality = float(dims.get("title_quality", 50))
    content_quality = float(dims.get("content_quality", 50))
    visual_quality = float(dims.get("visual_quality", 50))
    tag_strategy = float(dims.get("tag_strategy", 50))
    engagement_potential = float(dims.get("engagement_potential", 50))

    readability = float(content_analysis.get("readability_score", 0))
    info_density = float(content_analysis.get("info_density", 0)) * 100
    content_score = _clamp_score(
        title_quality * 0.25 + content_quality * 0.55
        + readability * 0.12 + info_density * 0.08
    )

    if image_analysis:
        saturation = float(image_analysis.get("saturation", 0)) * 100
        text_ratio = float(image_analysis.get("text_ratio", 0))
        text_balance = max(0.0, 100.0 - abs(text_ratio - 0.22) * 260.0)
        face_seen = (
            bool(image_analysis.get("has_face"))
            or bool((video_analysis or {}).get("has_face"))
            or bool((carousel_summary or {}).get("any_face"))
        )
        face_bonus = 8.0 if face_seen else 0.0
        visual_score = _clamp_score(
            visual_quality * 0.7 + saturation * 0.15
            + text_balance * 0.15 + face_bonus
        )
    elif video_analysis:
        face_bonus = 8.0 if video_analysis.get("has_face") else 0.0
        visual_score = _clamp_score(visual_quality * 0.85 + 10.0 + face_bonus)
    else:
        visual_score = _clamp_score(visual_quality)

    # 캐러셀: 색감 일관성 점수로 시각 점수 보정 (-5 ~ +5)
    if carousel_summary:
        consistency = float(carousel_summary.get("consistency", {}).get("score", 50))
        carousel_adj = (consistency - 50) * 0.1
        visual_score = _clamp_score(visual_score + carousel_adj)

    # 성장 전략은 태그만 보지 않음 — engagement_potential 가중치 상향
    # 좋은 콘텐츠 자체가 성장 동력, 태그는 보조 수단
    growth_score = _clamp_score(tag_strategy * 0.35 + engagement_potential * 0.45 + content_quality * 0.20)
    user_reaction_score = _clamp_score(
        content_score * 0.35 + visual_score * 0.2 + growth_score * 0.45
    )
    # Overall: 각 차원 평균, model_a 단독 사용 안 함 (model_a가 다소 낙관적)
    raw_overall = (content_score + visual_score + growth_score + user_reaction_score) / 4
    model_a_overall = float(model_a_score.get("total_score", 50))
    # 가중 평균: model_a 40% + 차원 평균 60% (과도한 고점 억제)
    overall_score = _clamp_score(model_a_overall * 0.4 + raw_overall * 0.6)

    return {
        "content": content_score,
        "visual": visual_score,
        "growth": growth_score,
        "user_reaction": user_reaction_score,
        "overall": overall_score,
    }


def _normalize_issues_items(raw: list | None) -> list[dict]:
    # BaseAgent가 문자열 목록을 반환할 수 있어 dict로 정규화
    out: list[dict] = []
    for it in raw or []:
        if isinstance(it, dict):
            desc = it.get("description") or it.get("msg") or ""
            row = {**it, "description": desc or str(it)}
            row.setdefault("severity", "high")
            row.setdefault("from_agent", row.get("from_agent") or "")
            out.append(row)
        else:
            out.append({"severity": "high", "description": str(it), "from_agent": "시스템"})
    return out


def _normalize_suggestions_items(raw: list | None) -> list[dict]:
    out: list[dict] = []
    for it in raw or []:
        if isinstance(it, dict):
            out.append({
                "priority": int(it.get("priority", 1)),
                "description": str(it.get("description", "")),
                "expected_impact": str(it.get("expected_impact", "")),
            })
        else:
            out.append({"priority": 1, "description": str(it), "expected_impact": ""})
    return out


class Orchestrator:
    """멀티 에이전트 진단 오케스트레이터"""

    def __init__(self, model: Optional[str] = None):
        """
        @param model - 기본 모델 오버라이드; 미지정 시 LLM_MODEL 환경변수 사용
        """
        if model:
            self.model = model
        else:
            env_model = os.getenv("LLM_MODEL", "").strip()
            if env_model:
                self.model = env_model
            elif _is_mimo_openai_compat():
                self.model = "mimo-v2-omni"
            else:
                self.model = "gpt-4o"
        self.text_analyzer = TextAnalyzer()
        self.image_analyzer = ImageAnalyzer()
        self.baseline_comparator = BaselineComparator()

    async def run(
        self,
        title: str,
        content: str,
        category: str,
        tags: list[str],
        cover_image: Optional[bytes] = None,
        cover_images: Optional[list[bytes]] = None,
        video_analysis: Optional[dict] = None,
        progress_cb: Optional[Callable[[str, str], Awaitable[Any] | Any]] = None,
    ) -> dict:
        """
        @param cover_image  - 대표 커버 이미지 1장 (단일 이미지 / 릴스 썸네일)
        @param cover_images - 캐러셀 전체 슬라이드 (2장 이상일 때 캐러셀 분석 활성화)
                              1장이면 cover_image와 동일하게 처리됨
        """
        t0 = time.time()

        async def _emit_progress(step: str, message: str) -> None:
            if progress_cb is None:
                return
            try:
                ret = progress_cb(step, message)
                if asyncio.iscoroutine(ret):
                    await ret
            except Exception as e:
                logger.warning("progress callback failed (%s): %s", step, e)

        agent_timeout = float(os.getenv("AGENT_LLM_TIMEOUT_SEC", "90"))
        judge_timeout = float(os.getenv("JUDGE_LLM_TIMEOUT_SEC", "180"))
        debate_timeout = float(os.getenv("DEBATE_LLM_TIMEOUT_SEC", "90"))
        free_tier_mode_env = os.getenv("LLM_FREE_TIER_MODE", "").strip().lower()
        free_tier_mode = (
            free_tier_mode_env in ("1", "true", "yes", "on")
            or (_llm_provider() == "gemini" and free_tier_mode_env != "off")
        )

        # --- Step 1: 멀티모달 콘텐츠 파싱 ---
        await _emit_progress("parse_start", "제목, 캡션, 미디어를 분석하는 중...")
        title_analysis = self.text_analyzer.analyze_title(title)
        content_analysis = self.text_analyzer.analyze_content(content)

        all_images: list[bytes] = []
        if cover_images:
            all_images = cover_images
        elif cover_image:
            all_images = [cover_image]

        image_analysis: dict | None = None
        carousel_summary: dict | None = None

        if len(all_images) >= 2:
            # 캐러셀: 슬라이드를 순차 분석 (병렬 시 numpy 배열이 동시에 쌓여 512MB OOM 발생)
            await _emit_progress("parse_start", f"캐러셀 {len(all_images)}장 슬라이드를 분석하는 중...")
            raw_results = []
            for img in all_images:
                try:
                    result = await asyncio.to_thread(self.image_analyzer.analyze, img)
                    raw_results.append(result)
                except Exception as e:
                    raw_results.append(e)
            valid_analyses = [r for r in raw_results if isinstance(r, dict)]
            if valid_analyses:
                image_analysis = valid_analyses[0]  # 첫 슬라이드를 대표 이미지로 사용
                carousel_summary = _build_carousel_summary(valid_analyses)
                logger.info(
                    "캐러셀 분석 완료: %d장 (유효=%d) | 일관성=%s | CTA=%s",
                    len(all_images),
                    len(valid_analyses),
                    carousel_summary.get("consistency", {}).get("score"),
                    carousel_summary.get("last_slide", {}).get("likely_cta"),
                )
        elif all_images:
            image_analysis = await asyncio.to_thread(self.image_analyzer.analyze, all_images[0])
            logger.info(
                "cover_image: bytes=%d cv_size=%sx%s",
                len(all_images[0]),
                image_analysis.get("width"),
                image_analysis.get("height"),
            )

        logger.info("파싱 완료 %.1fs", time.time() - t0)
        await _emit_progress("parse_done", "콘텐츠 및 미디어 파싱 완료")

        # --- Step 2: Baseline 비교 ---
        await _emit_progress("baseline_start", "동일 카테고리 벤치마크 비교 및 사전 평가 중...")
        note_features = {
            "title_length": title_analysis["length"],
            "tag_count": len(tags),
            "tags": tags,
        }
        if image_analysis:
            face_seen = bool(image_analysis.get("has_face")) or bool((video_analysis or {}).get("has_face"))
            note_features.update({
                "saturation": image_analysis.get("saturation", 0),
                "text_ratio": image_analysis.get("text_ratio", 0),
                "has_face": face_seen,
            })
        elif video_analysis:
            note_features.update({
                "has_face": bool(video_analysis.get("has_face", False)),
            })

        baseline_comparison = self.baseline_comparator.compare(category, note_features)

        # --- Step 2.5: Model A 사전 평가 ---
        image_count = len(all_images) if all_images else (1 if video_analysis else 0)
        model_a_score = pre_score(
            title=title,
            content=content,
            category=category,
            tag_count=len(tags),
            image_count=image_count,
        )
        baseline_comparison["model_a_pre_score"] = model_a_score
        if carousel_summary:
            baseline_comparison["carousel_summary"] = carousel_summary
        # 결정론적 레이더 점수 (LLM 없이 동일 입력 → 동일 점수)
        stable_scores = _build_stable_scores(
            model_a_score=model_a_score,
            content_analysis=content_analysis,
            image_analysis=image_analysis,
            video_analysis=video_analysis,
            carousel_summary=carousel_summary,
        )
        logger.info("Model A 사전 평가: %.1f (%s), stable_scores=%s", model_a_score["total_score"], model_a_score["level"], stable_scores)
        await _emit_progress("baseline_done", "벤치마크 비교 완료, 전문가 진단 시작")

        # --- Step 3: 병렬 에이전트 진단 (Round 1) ---
        await _emit_progress("round1_start", "4명의 전문가가 병렬로 진단 중...")
        t1 = time.time()
        content_agent = ContentAgent(model=MODEL_PRO)
        visual_agent = VisualAgent(model=MODEL_PRO)
        growth_agent = GrowthAgent(model=MODEL_PRO)
        user_sim_agent = UserSimAgent(model=MODEL_PRO)

        async def _run_round1_agent(label: str, coro):
            try:
                return await asyncio.wait_for(coro, timeout=agent_timeout)
            except asyncio.TimeoutError:
                logger.warning("Round1 %s 타임아웃 (%.0fs)", label, agent_timeout)
                return Exception(f"{label} 호출 타임아웃 ({int(agent_timeout)}s)")
            except Exception as e:
                logger.warning("Round1 %s 오류: %s", label, e)
                return e

        round1_specs = [
            (
                "후킹 전문가",
                "round1_content_done",
                "후킹 전문가 진단 완료",
                content_agent.diagnose(
                    title=title, content=content, category=category,
                    title_analysis=title_analysis, content_analysis=content_analysis,
                    baseline_comparison=baseline_comparison,
                ),
            ),
            (
                "비주얼 진단가",
                "round1_visual_done",
                "비주얼 진단가 진단 완료",
                visual_agent.diagnose(
                    title=title, category=category,
                    image_analysis=image_analysis,
                    video_analysis=video_analysis,
                    baseline_comparison=baseline_comparison,
                    cover_image_bytes=all_images[0] if all_images else None,
                    carousel_summary=carousel_summary,
                ),
            ),
            (
                "트렌드 에이전트",
                "round1_growth_done",
                "트렌드 에이전트 진단 완료",
                growth_agent.diagnose(
                    title=title, content=content, category=category,
                    tags=tags, baseline_comparison=baseline_comparison,
                ),
            ),
            (
                "인스타 중독 유저",
                "round1_user_done",
                "인스타 중독 유저 진단 완료",
                user_sim_agent.diagnose(
                    title=title, content=content, category=category, tags=tags,
                ),
            ),
        ]
        if free_tier_mode:
            # 무료 티어(낮은 RPM)에서는 호출 수를 줄이되, 댓글 기능을 위해 user_sim은 유지한다.
            round1_specs = [round1_specs[0], round1_specs[3]]

        round1_tasks = [_run_round1_agent(label, coro) for label, _step_key, _step_msg, coro in round1_specs]

        opinions = await asyncio.gather(*round1_tasks, return_exceptions=True)
        agent_opinions = []
        round1_tokens = 0

        for idx, op in enumerate(opinions):
            if isinstance(op, Exception):
                agent_opinions.append({
                    "agent_name": "Unknown", "dimension": "error", "score": 0,
                    "issues": [str(op)], "suggestions": [], "reasoning": str(op),
                })
            else:
                meta = op.pop("_meta", None)
                if meta:
                    round1_tokens += meta.get("total_tokens", 0)
                    logger.info("  [%s] tokens=%d", op.get("agent_name", "?"), meta.get("total_tokens", 0))
                agent_opinions.append(op)
            if idx < len(round1_specs):
                _label, step_key, step_msg, _coro = round1_specs[idx]
                await _emit_progress(step_key, step_msg)

        logger.info("Round 1 진단 완료 %.1fs, tokens=%d", time.time() - t1, round1_tokens)
        await _emit_progress("round1_done", "전문가 진단 완료, 토론 단계 진입")

        # --- Step 4+5: 토론 + 종합 심사 ---
        if free_tier_mode:
            await _emit_progress("debate_start", "무료 티어 모드: 토론 생략, 종합 심사만 진행 중...")
        else:
            await _emit_progress("debate_start", "전문가 토론과 종합 심사 동시 진행 중...")
        t2 = time.time()
        agents_list = [content_agent, visual_agent, growth_agent, user_sim_agent]

        # 토론과 심사 병렬 실행, 각자 완료 시 즉시 진행 이벤트 발송
        judge = JudgeAgent(model=MODEL_PRO)

        debate_records: list[dict] = []
        debate_tokens = 0
        final_report: dict = {}
        judge_tokens = 0

        async def _debate_task():
            nonlocal debate_records, debate_tokens
            if free_tier_mode:
                await _emit_progress("debate_done", "무료 티어 모드: 토론 생략")
                return
            try:
                debate_records, debate_tokens = await self._run_debate(
                    agent_opinions,
                    agents_list,
                    progress_cb=_emit_progress,
                    debate_timeout_sec=debate_timeout,
                )
            except Exception as e:
                logger.warning("토론 오류: %s", e)
            await _emit_progress("debate_done", "전문가 토론 완료")

        async def _judge_task():
            nonlocal final_report, judge_tokens
            await _emit_progress("judge_start", "종합 심사관이 평가 중...")
            try:
                result = await asyncio.wait_for(
                    judge.diagnose(
                        title=title, category=category,
                        agent_opinions=agent_opinions, debate_records=None,
                    ),
                    timeout=judge_timeout,
                )
                final_report = result
                meta = final_report.pop("_meta", None)
                judge_tokens = meta.get("total_tokens", 0) if meta else 0
            except asyncio.TimeoutError:
                logger.error("종합 심사 타임아웃 (%.0fs)", judge_timeout)
                final_report = {
                    "overall_score": 50, "grade": "C",
                    "issues": [{
                        "severity": "high",
                        "description": f"종합 심사 타임아웃 ({int(judge_timeout)}s)",
                        "from_agent": "system",
                    }],
                    "suggestions": [], "debate_summary": "종합 심사 타임아웃, 임시 결과 사용",
                }
            except Exception as e:
                logger.error("종합 심사 오류: %s", e)
                final_report = {"overall_score": 50, "grade": "C", "issues": [{"severity": "high", "description": str(e), "from_agent": "system"}], "suggestions": [], "debate_summary": "종합 심사 실패"}
            await _emit_progress("judge_done", "종합 심사 완료")

        await asyncio.gather(_debate_task(), _judge_task())

        logger.info("토론+심사 병렬 완료 %.1fs, debate_tokens=%d, judge_tokens=%d",
                     time.time() - t2, debate_tokens, judge_tokens)

        # --- Step 6: 최종 보고서 조합 ---
        await _emit_progress("finalizing", "최종 진단 보고서 생성 중...")
        simulated_comments = []
        for op in agent_opinions:
            if "simulated_comments" in op:
                simulated_comments = op["simulated_comments"]
                break

        debate_timeline = self._build_debate_timeline(debate_records)

        total_time = time.time() - t0
        logger.info("진단 완료 | 총 소요=%.1fs | 총 tokens≈%d",
                     total_time, round1_tokens + debate_tokens + judge_tokens)

        result = self._assemble_response(
            final_report, agent_opinions, simulated_comments, debate_timeline,
            stable_scores=stable_scores,
        )
        result["model_a_pre_score"] = model_a_score
        result["_usage"] = {
            "total_tokens": round1_tokens + debate_tokens + judge_tokens,
            "duration_sec": round(total_time, 1),
        }
        return result

    async def _run_debate(
        self,
        opinions: list[dict],
        agents: list,
        progress_cb=None,
        debate_timeout_sec: float = 90.0,
    ) -> tuple[list[dict], int]:
        """토론 단계: 4명 에이전트가 순차 발언, 완료 시 진행 이벤트 전송."""
        agent_names = ["후킹 전문가", "비주얼 진단가", "트렌드 에이전트", "인스타 중독 유저"]
        debate_records = []
        debate_tokens = 0

        # 토론 프롬프트 선조립
        prompts = []
        for i, agent in enumerate(agents):
            other_opinions = []
            for j, op in enumerate(opinions):
                if j != i:
                    other_opinions.append({
                        "agent_name": op.get("agent_name", ""),
                        "dimension": op.get("dimension", ""),
                        "score": op.get("score", 0),
                        "issues": op.get("issues", [])[:3],
                        "suggestions": op.get("suggestions", [])[:3],
                    })
            other_text = json.dumps(other_opinions, ensure_ascii=False)
            prompts.append(DEBATE_PROMPT.format(
                agent_name=agent.agent_name, other_opinions=other_text,
            ))

        # 4명 병렬 실행, 각자 완료 시 진행 이벤트 전송 (개별 타임아웃으로 전체 중단 방지)
        async def _single_debate(idx):
            try:
                result = await asyncio.wait_for(
                    agents[idx].call_llm(
                        prompts[idx], system_override=agents[idx].system_prompt,
                        model_override=MODEL_FAST, max_tokens=1024,
                    ),
                    timeout=debate_timeout_sec,
                )
                return idx, result
            except asyncio.TimeoutError:
                logger.warning("토론 agent[%d] 타임아웃 (%.0fs)", idx, debate_timeout_sec)
                return idx, {
                    "agent_name": agents[idx].agent_name,
                    "agreements": [],
                    "disagreements": [f"전문가 발언 타임아웃 ({int(debate_timeout_sec)}s), 건너뜀"],
                    "additions": [],
                }
            except Exception as e:
                logger.warning("토론 agent[%d] 실패: %s", idx, e)
                return idx, {
                    "agent_name": agents[idx].agent_name,
                    "agreements": [],
                    "disagreements": [str(e)],
                    "additions": [],
                }

        tasks = [asyncio.create_task(_single_debate(i)) for i in range(len(agents))]
        for coro in asyncio.as_completed(tasks):
            try:
                idx, result = await coro
            except Exception as e:
                logger.warning("토론 오류: %s", e)
                continue
            if isinstance(result, dict):
                meta = result.pop("_meta", None)
                if meta:
                    debate_tokens += meta.get("total_tokens", 0)
                result["agent_name"] = agents[idx].agent_name
                debate_records.append(result)
                # 반박 > 추가 > 동의 순으로 가장 흥미로운 발언을 프리뷰로 사용
                name = agent_names[idx] if idx < len(agent_names) else agents[idx].agent_name
                snippets = (result.get("disagreements") or []) + (result.get("additions") or []) + (result.get("agreements") or [])
                preview = snippets[0][:80] if snippets else f"{name} 발언 완료"
                if progress_cb:
                    try:
                        ret = progress_cb(f"debate_agent_{idx}", f"{name}：{preview}")
                        if asyncio.iscoroutine(ret):
                            await ret
                    except Exception:
                        pass

        return debate_records, debate_tokens

    def _build_debate_timeline(self, debate_records: list[dict]) -> list[dict]:
        timeline = []
        for record in debate_records:
            name = record.get("agent_name", "")
            for text in record.get("agreements", []):
                timeline.append({"round": 2, "agent_name": name, "kind": "agree", "text": text})
            for text in record.get("disagreements", []):
                timeline.append({"round": 2, "agent_name": name, "kind": "rebuttal", "text": text})
            for text in record.get("additions", []):
                timeline.append({"round": 2, "agent_name": name, "kind": "add", "text": text})
        return timeline

    def _assemble_response(self, final_report, agent_opinions, simulated_comments, debate_timeline, stable_scores=None) -> dict:
        is_llm_error = final_report.get("dimension") == "error"

        # 결정론적 stable_scores를 레이더 점수로 사용 (LLM 출력 불필요, 점수 안정성)
        if stable_scores:
            radar = {k: _clamp_score(v) for k, v in stable_scores.items()}
        else:
            radar = final_report.get("radar_data", {})
            if not radar:
                scores = {op.get("dimension", "unknown"): op.get("score", 0) for op in agent_opinions}
                radar = {
                    "content": scores.get("후킹력", scores.get("콘텐츠 품질", 50)),
                    "visual": scores.get("시각 완성도", 50),
                    "growth": scores.get("트렌드 적합성", scores.get("성장 전략", 50)),
                    "user_reaction": scores.get("유저 반응", scores.get("오디언스 반응", 50)),
                    "overall": final_report.get("overall_score", 50),
                }
            for k in radar:
                radar[k] = round(max(0, min(100, float(radar[k]))))

        if is_llm_error and final_report.get("overall_score") is None:
            overall_score = float(final_report.get("score", 0))
        else:
            overall_score = float(final_report.get("overall_score", 50))
        # stable_scores가 있으면 결정론적 overall 사용
        if stable_scores:
            overall_score = round(stable_scores.get("overall", overall_score))
        else:
            overall_score = round(max(0, min(100, overall_score)))
        grade = final_report.get("grade") if not is_llm_error else "D"
        if not grade:
            grade = self._calc_grade(overall_score)

        formatted_opinions = []
        for op in agent_opinions:
            formatted_opinions.append({
                "agent_name": op.get("agent_name", ""),
                "dimension": op.get("dimension", ""),
                "score": op.get("score", 0),
                "issues": op.get("issues", []),
                "suggestions": op.get("suggestions", []),
                "reasoning": op.get("reasoning", ""),
                "debate_comments": op.get("debate_comments", []),
            })

        formatted_comments = []
        for c in simulated_comments:
            if isinstance(c, dict):
                formatted_comments.append({
                    "username": c.get("username", "인스타 유저"),
                    "avatar_emoji": c.get("avatar_emoji", "😊"),
                    "comment": c.get("comment", ""),
                    "sentiment": c.get("sentiment", "neutral"),
                    "likes": int(c.get("likes", 0)) if c.get("likes") is not None else 0,
                })

        cover_dir = final_report.get("cover_direction")
        if cover_dir is not None and not isinstance(cover_dir, dict):
            cover_dir = None

        issues = _normalize_issues_items(final_report.get("issues", []))
        # Fallback: Judge가 issues를 반환하지 않으면 각 Agent에서 취합
        if not issues and not is_llm_error:
            agent_iss: list = []
            for op in agent_opinions:
                for iss in (op.get("issues") or [])[:2]:
                    agent_iss.append(iss)
            issues = _normalize_issues_items(agent_iss[:6])
        suggestions = _normalize_suggestions_items(final_report.get("suggestions", []))
        # Fallback: Judge가 suggestions를 반환하지 않으면 각 Agent suggestions에서 취합
        if not suggestions and not is_llm_error:
            agent_sug: list = []
            for op in agent_opinions:
                for s in (op.get("suggestions") or [])[:2]:
                    agent_sug.append(s)
            suggestions = _normalize_suggestions_items(agent_sug[:6])
        if is_llm_error and not suggestions:
            suggestions = _normalize_suggestions_items([
                "AI 서비스에 연결할 수 없습니다. 네트워크, 프록시, OPENAI_BASE_URL/API Key 설정을 확인한 후 다시 시도하세요.",
            ])

        debate_summary = final_report.get("debate_summary", "")
        if is_llm_error and not debate_summary:
            debate_summary = final_report.get("reasoning", "") or "AI 호출 실패로 에이전트 토론과 종합 심사를 완료하지 못했습니다."

        return {
            "overall_score": overall_score,
            "grade": grade,
            "radar_data": radar,
            "agent_opinions": formatted_opinions,
            "issues": issues,
            "suggestions": suggestions,
            "debate_summary": debate_summary,
            "debate_timeline": debate_timeline,
            "simulated_comments": formatted_comments,
            "optimized_title": final_report.get("optimized_title"),
            "optimized_content": final_report.get("optimized_content"),
            "cover_direction": cover_dir,
        }

    def _calc_grade(self, score: float) -> str:
        if score >= 90: return "S"
        if score >= 75: return "A"
        if score >= 60: return "B"
        if score >= 40: return "C"
        return "D"
