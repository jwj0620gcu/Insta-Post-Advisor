<div align="center">

# InstaRx

### 인스타그램 게시물 AI 진단 엔진

**멀티 에이전트 분석** | **96건 실제 데이터 학습** | **카테고리별 베이스라인 비교**

<br>

[**기술 아키텍처**](#기술-아키텍처) &nbsp;&nbsp;|&nbsp;&nbsp; [**빠른 시작**](#빠른-시작) &nbsp;&nbsp;|&nbsp;&nbsp; [**연구 백서**](docs/research_whitepaper.html)

<br>

> 인스타그램 게시물(이미지·릴스·스크린샷)을 올리면, AI가 콘텐츠·비주얼·성장 전략을 분석하고 정량적 진단 리포트와 실행 가능한 개선 방안을 제공합니다.

</div>

---

## 진단 흐름

```
업로드 (이미지 / 릴스 / 스크린샷)
    │
    ▼
① 파싱          OpenCV로 이미지 분석 (채도·밝기·텍스트 비율·얼굴 유무)
                텍스트 분석기로 캡션·해시태그 구조 분석
    │
    ▼
② 사전 채점     Model A — LLM 없이 50ms 이내 즉시 채점
                96건 실제 게시물 회귀 분석 기반 5차원 점수 산출
    │
    ▼
③ 베이스라인    SQLite에서 같은 카테고리 평균 지표 조회
비교            캡션 길이 / 해시태그 수 / 인게이지먼트율 비교
    │
    ▼
④ 에이전트      ContentAgent   후킹·캡션·감정선 분석
진단            UserSimAgent   실제 유저 반응·댓글 시뮬레이션
(병렬 실행)
    │
    ▼
⑤ 종합 심사     JudgeAgent — 두 에이전트 결과 종합
                최종 점수·등급·핵심 이슈·우선순위 개선안 결정
    │
    ▼
⑥ 리포트 출력   레이더 차트 / 차원 바 / 베이스라인 비교
                시뮬레이션 댓글 / 개선 제안 목록
```

---

## 기술 아키텍처

### Model A — 정량 예측 엔진

- **학습 데이터**: 96건 실제 인스타그램 게시물 (2026년 3–4월, 8개 카테고리 × 12건)
- **포맷별 평균 인게이지먼트율**: 캐러셀 24.5% > 릴스 16.3% > 단일 이미지 4.0%
- **동작 방식**: LLM 호출 없이 회귀 가중치만으로 즉시 채점 → 동일 입력은 항상 동일 점수
- **출력**: 5차원 점수 (제목 품질 / 콘텐츠 품질 / 비주얼 / 태그 전략 / 인게이지먼트 잠재력)

### 베이스라인 DB (SQLite)

| 테이블 | 내용 |
|---|---|
| `baseline_stats` | 카테고리별 평균 지표 (캡션 길이·태그 수·채도·인게이지먼트율 등) |
| `diagnosis_history` | 과거 진단 결과 저장 |
| `usage_log` | 토큰 사용량·응답 시간 추적 |

### 에이전트 구성 (현재 설정 기준)

| 에이전트 | 역할 | 상태 |
|---|---|---|
| **ContentAgent** | 캡션·후킹·감정선 분석 | ✅ 실행 중 |
| **UserSimAgent** | 유저 반응·댓글 시뮬레이션 | ✅ 실행 중 |
| VisualAgent | 이미지·레이아웃 분석 | ⏸ 무료 티어 모드로 비활성 |
| GrowthAgent | 해시태그·성장 전략 분석 | ⏸ 무료 티어 모드로 비활성 |
| **JudgeAgent** | 에이전트 결과 종합 심사 | ✅ 실행 중 |
| 에이전트 토론 (Round 2) | 교차 반박·보완 | ⏸ 무료 티어 모드로 비활성 |

> `LLM_FREE_TIER_MODE=1` 해제 시 4개 에이전트 병렬 실행 + 토론 라운드 활성화됨

### LLM

- **현재 모델**: `gemini-2.5-flash-lite` (PRO·OMNI·FAST 역할 모두 동일 모델)
- **연결 방식**: OpenAI SDK → Google Gemini OpenAI 호환 엔드포인트
- **교체 가능**: `.env`에서 `LLM_PROVIDER=openai|anthropic|gemini` 로 변경

### 지원 카테고리 (8개)

`food` 맛집/카페 · `fashion` 패션/뷰티 · `fitness` 운동/건강 · `business` 사업/마케팅  
`lifestyle` 일상/육아 · `travel` 여행 · `education` 정보/교육 · `shop` 쇼핑/리뷰

### 기술 스택

| 계층 | 기술 |
|---|---|
| **프론트엔드** | React 19 · TypeScript 6 · Vite 8 · MUI v9 · Framer Motion · ECharts · React Router v7 |
| **백엔드** | FastAPI · Uvicorn · Pydantic v2 · asyncio · SQLite |
| **이미지 처리** | OpenCV (headless) · Pillow |
| **AI** | OpenAI SDK (Gemini 호환) · Anthropic SDK (선택) |
| **저장소** | SQLite (서버) · IndexedDB (브라우저 히스토리) |

---

## 빠른 시작

```bash
git clone https://github.com/jwj0620gcu/Insta-Post-Advisor.git
cd Insta-Post-Advisor

# 환경 변수 설정
cp .env.example backend/.env
# backend/.env 에서 API 키 입력

# 설치 + DB 초기화 + 실행
make install && make data && ./start.sh
```

`http://localhost:5173` 접속

### 주요 환경 변수

| 변수 | 설명 | 기본값 |
|---|---|---|
| `LLM_PROVIDER` | `gemini` / `openai` / `anthropic` | `gemini` |
| `GEMINI_API_KEY` | Google AI Studio 키 | — |
| `LLM_MODEL_PRO` | 에이전트 진단·심사용 모델 | `gemini-2.5-flash-lite` |
| `LLM_FREE_TIER_MODE` | `1` = 에이전트 2개만 실행, 토론 생략 | `1` |
| `VIDEO_STT_ENABLED` | `1` = 영상 음성인식 활성화 | `0` |
| `MAX_VIDEO_UPLOAD_MB` | 영상 업로드 용량 한도 | `300` |

---

## License

Apache License 2.0
