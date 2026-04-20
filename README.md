<div align="center">

# Insta-Advisor

### 인스타그램 게시물 AI 진단 및 최적화 솔루션

**5-Agent 멀티 에이전트** | **96건 실제 데이터 학습** | **카테고리별 베이스라인 비교**

<br>

[**기술 아키텍처**](#기술-아키텍처) &nbsp;&nbsp;|&nbsp;&nbsp; [**빠른 시작**](#빠른-시작) &nbsp;&nbsp;|&nbsp;&nbsp; [**라이브 데모 →**](https://insta-post-advisor.onrender.com/app)

</div>

---

## 왜 만들었나 — 페인 포인트

> *"왜 이번 영상은 조회수가 낮지?"*  
> *"어떻게 해야 유저에게 관심을 얻지?"*  
> *"제목이랑 캡션 생각하기 너무 귀찮다."*

#### 인스타그램 크리에이터라면 누구나 겪는 문제.
#### 열심히 만든 게시물이 왜 안 되는지, 어디를 고쳐야 하는지 알 방법이 X.
#### Insta-Advisor는 게시물을 올리기만 하면, 5개 전문가 에이전트가 진단하고, 바로 쓸 수 있는 개선안을 제시!

---
## 입력->처리->출력 전과정 AI 최적화 AI 네이티브 서비스!

## 서비스 흐름

### 1단계 — 업로드 & 파싱

사진 또는 릴스를 올리면 자동으로 분석이 시작된다.

- **OpenCV** — 채도·밝기·텍스트 비율·얼굴 유무 수치 추출
- **멀티모달 LLM** — 이미지를 직접 보고 시각적 특성 해석
- **오디오 STT** — 릴스 음성에서 텍스트 추출 

### 2단계 — 이중 진단 모델 협업

**첫 번째 모델 — 정량 채점 (Model A)**

8가지 카테고리(여행, 맛집, 패션, 일상 등) 실제 100여개 데이터 수 기반 5가지 지표로 게시물 점수 산출
회귀 분석 진행
인스타 정책상 크롤링 x

| 지표 | 설명 |
|---|---|
| 제목 품질 | 첫 문장의 후킹 강도 |
| 콘텐츠 품질 | 캡션 구조·가독성·정보 밀도 |
| 비주얼 품질 | 이미지 색감·구도·텍스트 비율 |
| 태그 전략 | 해시태그 수·적절성 |
| 잠재력 | 포맷·카테고리 기반 반응 예측 |

**두 번째 모델 — Gemini 에이전트 비평**

Model A 수치를 근거로 4개 에이전트가 진단한다.

- **Round 1** — 후킹 전문가 · 비주얼 진단가 · 트렌드 에이전트 · 인스타 중독 유저 병렬 진단
- **Round 2** — 에이전트 간 상호 반박·보완, 판사 에이전트가 결과 통합 후 최종 결정

### 3단계 — 진단 리포트 출력

- 종합 점수(0–100) 및 등급(S·A·B·C·D)
- 세부 피드백 — 제목 추천, 자동 캡션, 본문 가독성, 성장 전략
- **모의 댓글 시뮬레이션** — 공감형·광고 지적형·질문형 등 실제 유저 반응 미리 가늠하는 지능형 댓글
- **최적화 제안** — AI가 직접 수정한 제목·캡션 버전 제안, 마음에 들 때까지 재생성

---
입력: 
사용자가 스크린샷, 이미지, 영상을 넣으면 AI가 내용을 읽고 구조화함
처리:
ai가 멀티모달 해석, 여러 에이전트 토론, 판정까지 AI가 핵심 로직을 담당
출력:
진단 보고서, 수정안, 모의 댓글, 재작성서비스의 본체임
## 진단 흐름

```
업로드 (이미지 / 캐러셀 / 릴스 / 스크린샷)
    │
    ▼
① 파싱           텍스트 분석기 → 캡션·해시태그 구조 분석
                 OpenCV → 채도·밝기·텍스트 비율·얼굴 유무
                 캐러셀: 전체 슬라이드 병렬 분석 + 색감 일관성 산출
    │
    ▼
② 사전 채점      Model A — LLM 없이 즉시 채점 (50ms 이내)
 + 베이스라인    96건 실제 게시물 회귀 분석 기반 5차원 점수 산출
   비교          SQLite에서 같은 카테고리 평균 지표 비교
    │
    ▼
③ Round 1        4개 에이전트 병렬 진단 (asyncio.gather)
   병렬 진단     ┌─ 후킹 전문가    캡션 후킹·감정선·읽기 흐름
                 ├─ 비주얼 진단가  이미지 레이아웃·색감·CTA 슬라이드
                 ├─ 트렌드 에이전트  해시태그·카테고리 트렌드·성장 전략
                 └─ 인스타 중독 유저  실제 유저 반응·시뮬레이션 댓글 생성
    │
    ▼
④ Round 2        토론 + 종합 심사 동시 실행 (asyncio.gather)
 + 심사          ├─ 토론: 4개 에이전트가 서로의 의견에 반박·보완
   (병렬)        └─ 종합 심사관: 에이전트 결과 통합 → 최종 점수·등급·개선안
    │
    ▼
⑤ 리포트 출력   레이더 차트(결정론적) / 차원 바 / 베이스라인 비교
                 에이전트 토론 타임라인 / 시뮬레이션 댓글 / 개선 제안
```

---

## 기술 아키텍처

### Model A — 정량 예측 엔진

- **학습 데이터**: 96건 실제 인스타그램 게시물 (2026년 3–4월, 8개 카테고리 × 12건)
- **포맷별 평균 인게이지먼트율**: 캐러셀 24.5% > 릴스 16.3% > 단일 이미지 4.0%
- **동작 방식**: LLM 호출 없이 회귀 가중치만으로 즉시 채점 → 동일 입력은 항상 동일 점수
- **레이더 점수**: Model A + 텍스트/이미지 분석 결합 → 결정론적 산출 (LLM 출력과 독립)

### 에이전트 구성 (5개)

| 에이전트 | 역할 이름 | 담당 |
|---|---|---|
| **ContentAgent** | 후킹 전문가 | 캡션·후킹 문구·감정선·읽기 흐름 |
| **VisualAgent** | 비주얼 진단가 | 이미지 레이아웃·색감 일관성·CTA 슬라이드 |
| **GrowthAgent** | 트렌드 에이전트 | 해시태그·카테고리 트렌드·성장 전략 |
| **UserSimAgent** | 인스타 중독 유저 | 실제 유저 반응 예측·시뮬레이션 댓글 생성 |
| **JudgeAgent** | 종합 심사관 | 4개 에이전트 결과 통합·최종 등급·개선안 확정 |

> `LLM_FREE_TIER_MODE=1` 설정 시: ContentAgent + UserSimAgent 2개만 실행, 토론 생략 (API 호출 수 절감)  
> Gemini 사용 시 기본값은 free_tier_mode=True이므로, 전체 실행하려면 **`LLM_FREE_TIER_MODE=off`** 명시 필요

### LLM

- **현재 모델**: `gemini-2.5-flash-lite` (PRO·OMNI·FAST 역할 모두 동일)
- **연결 방식**: OpenAI SDK → Google Gemini OpenAI 호환 엔드포인트
- **교체 가능**: `.env`에서 `LLM_PROVIDER=openai|anthropic|gemini` 로 변경

### 베이스라인 DB (SQLite)

| 테이블 | 내용 |
|---|---|
| `baseline_stats` | 카테고리별 평균 지표 (캡션 길이·태그 수·채도·인게이지먼트율 등) |
| `diagnosis_history` | 과거 진단 결과 저장 |
| `usage_log` | 토큰 사용량·응답 시간 추적 |

### 지원 카테고리 (8개)

`food` 맛집/카페 · `fashion` 패션/뷰티 · `fitness` 운동/건강 · `business` 사업/마케팅  
`lifestyle` 일상/육아 · `travel` 여행 · `education` 정보/교육 · `shop` 쇼핑/리뷰

### 기술 스택

| 계층 | 기술 |
|---|---|
| **프론트엔드** | React 19 · TypeScript · Vite · MUI v9 · Framer Motion · ECharts · React Router v7 |
| **백엔드** | FastAPI · Uvicorn · Pydantic v2 · asyncio · SQLite |
| **이미지 처리** | OpenCV (headless) · Pillow |
| **AI** | Google Gemini 2.5 Flash Lite (OpenAI 호환 엔드포인트) |
| **저장소** | SQLite (서버) · IndexedDB (브라우저 히스토리) |
| **배포** | Render.com (Singapore, Free Tier) |

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
| `LLM_MODEL_FAST` | 토론 라운드용 모델 | `gemini-2.5-flash-lite` |
| `LLM_FREE_TIER_MODE` | `off` = 4개 에이전트 + 토론 전체 실행 | `off` (Gemini 사용 시 기본 `on`) |
| `VIDEO_STT_ENABLED` | `1` = 영상 음성인식 활성화 | `0` |
| `MAX_VIDEO_UPLOAD_MB` | 영상 업로드 용량 한도 | `300` |

---

## License

Apache License 2.0
