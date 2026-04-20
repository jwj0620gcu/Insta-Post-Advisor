# NoteRx 데이터 연구 시스템

## 연구 목표

실제 Instagram 게시글 및 댓글 데이터에서 두 가지 「모델」(파라미터 집합 + 프롬프트)을 학습시켜 InstaRx 진단 정확도를 향상시킵니다:

- **Model A: 콘텐츠 점수 모델** — 게시글 인터랙션 성과를 예측하고, 차원별 점수 파라미터를 출력
- **Model B: 사용자 페르소나 모델** — 실감 나는 댓글을 생성하고, 페르소나 템플릿과 댓글 생성 프롬프트를 출력

## 전체 흐름

```
원본 데이터 (xlsx/csv)
  │
  ├─ 01_normalize.py ─────── 포맷 통일 → unified CSV + SQLite
  ├─ 02_download_covers.py ─ 커버 이미지 일괄 다운로드
  ├─ 03_feature_engineering.py ── 파생 피처 계산
  │
  ├─── Track A: 전통 통계 ─────────────────────────────────
  │    ├─ 04_traditional_analysis.py  기술통계/상관관계/회귀
  │    └─ 출력: stats/*.json + charts/*.png
  │
  ├─── Track B: LLM 심층 분석 ─────────────────────────────
  │    ├─ 05_cover_vision.py    mimo-v2-omni 커버 비주얼 이해
  │    ├─ 06_content_llm.py     mimo-v2-pro 콘텐츠 패턴 요약
  │    └─ 출력: llm/*.json
  │
  ├─── Track C: 사용자 페르소나 ─────────────────────────────────
  │    ├─ 07_comment_persona.py  댓글 분류 + 페르소나 생성
  │    └─ 출력: personas/*.json
  │
  ├─ 08_build_scoring_model.py ── 양 트랙 병합 → 점수 파라미터
  ├─ 09_generate_prompts.py ───── 강화된 Agent 프롬프트 생성
  ├─ 10_validate_model.py ─────── 알려진 바이럴 게시글로 역검증
  └─ 11_final_report.py ──────── 최종 연구 보고서 + 시각화

출력 디렉터리: data/research_output/
연구 일지: scripts/research/research_journal.md
```

## 실행 방법

```bash
# 전체 흐름 (데이터를 data/원시데이터_처리대기/ 와 data/댓글데이터/ 에 넣기)
python3 scripts/research/run_all.py

# 단계별 실행
python3 scripts/research/01_normalize.py
python3 scripts/research/04_traditional_analysis.py
python3 scripts/research/05_cover_vision.py --category food
# ...

# 모델 사용 (3단계)
MODEL_FAST=mimo-v2-flash   # 댓글 빠른 분류, 일괄 처리
MODEL_PRO=mimo-v2-pro      # 1M 컨텍스트, 콘텐츠 패턴 요약, 보고서 생성
MODEL_OMNI=mimo-v2-omni    # 멀티모달, 커버/동영상 비주얼 분석
```

## 의존성

```bash
pip install openpyxl pandas numpy scipy scikit-learn matplotlib seaborn openai httpx
```
