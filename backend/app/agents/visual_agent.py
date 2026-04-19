"""
비주얼 진단 Agent.
커버 구성/색감/가독성을 분석하고, 필요시 영상 이해 결과를 함께 반영한다.
"""
from __future__ import annotations

import json
import logging
import os

from app.agents.base_agent import BaseAgent
from app.agents.prompts.visual_agent import SYSTEM_PROMPT
from app.agents.research_data import build_data_prompt_for_agent

logger = logging.getLogger("instarx.visual_agent")


class VisualAgent(BaseAgent):
    """커버/영상의 시각 성능 분석."""

    agent_name = "비주얼 진단가"
    system_prompt = SYSTEM_PROMPT

    def build_user_message(
        self,
        title: str,
        category: str,
        image_analysis: dict | None,
        baseline_comparison: dict,
        video_analysis: dict | None = None,
        carousel_summary: dict | None = None,
    ) -> str:
        """이미지/영상 분석 + baseline 비교 기반 프롬프트 생성."""
        comparisons = baseline_comparison.get("comparisons", {})

        image_parts: list[str] = []

        # 캐러셀 분석 섹션 (다중 이미지)
        if carousel_summary:
            slide_count = carousel_summary.get("slide_count", 0)
            consistency = carousel_summary.get("consistency", {})
            first_slide = carousel_summary.get("first_slide", {})
            last_slide = carousel_summary.get("last_slide", {})
            image_parts.append(f"""## 캐러셀 슬라이드 분석 ({slide_count}장)
- 슬라이드 수: {slide_count}장 — {carousel_summary.get('slide_count_verdict', '')}
- 첫 슬라이드 채도: {first_slide.get('saturation', 0)} / 밝기: {first_slide.get('brightness', 0)}
- 첫 슬라이드 텍스트 비율: {first_slide.get('text_ratio', 0)} / 인물: {'있음' if first_slide.get('has_face') else '없음'}
- 색감 일관성 점수: {consistency.get('score', 0)}/100 (채도 편차={consistency.get('saturation_std', 0)}, 밝기 편차={consistency.get('brightness_std', 0)})
- 마지막 슬라이드 텍스트 비율: {last_slide.get('text_ratio', 0)} — {'CTA 슬라이드로 추정 ✓' if last_slide.get('likely_cta') else 'CTA 슬라이드 아님 (추가 권장)'}
- 전체 인물 출연: {'있음' if carousel_summary.get('any_face') else '없음'}
- 평균 채도: {carousel_summary.get('avg_saturation', 0)} / 평균 밝기: {carousel_summary.get('avg_brightness', 0)}""")

        # 대표 이미지(첫 슬라이드) 분석
        if image_analysis:
            label = "첫 슬라이드 상세 분석" if carousel_summary else "커버 이미지 분석"
            image_parts.append(f"""## {label}
- 사이즈: {image_analysis.get('width', 0)}x{image_analysis.get('height', 0)}
- 가로세로 비율: {image_analysis.get('aspect_ratio', 0)}
- 채도: {image_analysis.get('saturation', 0)}
- 밝기: {image_analysis.get('brightness', 0)}
- 인물/얼굴 감지: {'있음' if image_analysis.get('has_face') else '없음'}
- 텍스트 영역 비율: {image_analysis.get('text_ratio', 0)}
- 주요 색상: {json.dumps(image_analysis.get('dominant_colors', []), ensure_ascii=False)}""")
        if video_analysis:
            image_parts.append(f"""## 영상 이해 결과 (비주얼 진단 참고)
- 요약: {video_analysis.get('summary', '')}
- 장면 키워드: {json.dumps(video_analysis.get('scene_keywords', []), ensure_ascii=False)}
- 커버 방향 추천: {video_analysis.get('cover_suggestion', '')}
- 인물 출연: {'있음' if video_analysis.get('has_face') else '없음'}
- 촬영 스타일: {video_analysis.get('shot_style', '')}
- 리스크/제한: {json.dumps(video_analysis.get('risk_or_limitations', []), ensure_ascii=False)}""")
        if image_parts:
            image_info = "\n\n".join(image_parts)
        else:
            image_info = "## 커버 이미지 분석\n커버 이미지가 없어 제목/카테고리 기반 추정 제안을 작성합니다."

        cover_comp = ""
        if "cover_saturation" in comparisons:
            cs = comparisons["cover_saturation"]
            cover_comp += f"- 커버 채도: 사용자 {cs.get('user_value', 'N/A')} vs 카테고리 평균 {cs.get('category_avg', 'N/A')} ({cs.get('verdict', '')})\n"
        if "cover_text_ratio" in comparisons:
            ct = comparisons["cover_text_ratio"]
            cover_comp += f"- 텍스트 비율: 사용자 {ct.get('user_value', 'N/A')} vs 카테고리 평균 {ct.get('category_avg', 'N/A')} ({ct.get('verdict', '')})\n"
        if "cover_face" in comparisons:
            cf = comparisons["cover_face"]
            cover_comp += (
                f"- 인물 출연: 사용자 {'있음' if cf.get('user_has_face') else '없음'}, "
                f"카테고리 인물 비율 {cf.get('category_face_rate', 'N/A')} {cf.get('suggestion', '')}\n"
            )

        msg = f"""## 진단 대상 게시물
- **카테고리**: {category}
- **제목/첫 문장**: {title}

{image_info}

## Baseline 커버 비교
{cover_comp if cover_comp else '비교 데이터 없음'}

위 데이터를 기반으로 인스타그램 비주얼 진단을 작성하세요."""
        msg += build_data_prompt_for_agent("visual", category)
        return msg

    async def diagnose(
        self,
        *,
        title: str,
        category: str,
        image_analysis: dict | None,
        baseline_comparison: dict,
        video_analysis: dict | None = None,
        cover_image_bytes: bytes | None = None,
        carousel_summary: dict | None = None,
    ) -> dict:
        """
        비주얼 진단: 커버 이미지가 있으면 멀티모달로 직접 분석,
        없으면 텍스트 기반 추론으로 처리.
        캐러셀의 경우 carousel_summary로 전체 슬라이드 일관성을 반영한다.
        """
        msg = self.build_user_message(
            title=title,
            category=category,
            image_analysis=image_analysis,
            baseline_comparison=baseline_comparison,
            video_analysis=video_analysis,
            carousel_summary=carousel_summary,
        )
        vision_tail = (
            "\n\n## 작업 지시\n"
            "첨부된 커버 이미지를 직접 보고 분석하세요. "
            "reasoning에는 실제 보이는 요소(텍스트 위치, 주제, 색 대비, 구도)를 근거로 작성하세요."
        )

        if cover_image_bytes:
            try:
                from app.analysis.image_vision_prep import jpeg_bytes_for_vision

                jpeg = jpeg_bytes_for_vision(cover_image_bytes)
                max_tok = int(os.getenv("VISUAL_AGENT_MAX_COMPLETION_TOKENS", "2500"))
                return await self.call_llm_vision(msg + vision_tail, jpeg, max_tokens=max_tok)
            except Exception as e:
                logger.warning("커버 멀티모달 진단 실패, 텍스트 모드로 폴백: %s", e)
                return await self.call_llm(msg)

        return await self.call_llm(msg)
