# Model A Recalibration Prep

Model A 재보정 전에 반드시 통과해야 하는 준비 스크립트 모음.

## 실행 순서
1. 템플릿 생성
   - `python3 scripts/model_a_prep/01_generate_template.py`
2. source CSV 병합/정규화 (선택)
   - source 위치: `data/instagram_recalibration/source/*.csv`
   - 실행: `python3 scripts/model_a_prep/04_merge_sources.py`
   - 결과: `data/instagram_recalibration/raw_posts.csv` 자동 upsert
3. 실제 데이터 투입
   - 수동 입력 시 `data/instagram_recalibration/raw_posts.csv` 파일을 직접 채운다.
4. 스키마/품질 검증
   - `python3 scripts/model_a_prep/02_validate_dataset.py --input data/instagram_recalibration/raw_posts.csv`
   - 공개 크롤링 모드: `python3 scripts/model_a_prep/02_validate_dataset.py --mode public-crawl --input data/instagram_recalibration/raw_posts.csv`
5. 프로파일 리포트 생성
   - `python3 scripts/model_a_prep/03_profile_report.py --input data/instagram_recalibration/raw_posts.csv`
   - 공개 크롤링 모드: `python3 scripts/model_a_prep/03_profile_report.py --mode public-crawl --input data/instagram_recalibration/raw_posts.csv`
   - 산출물: `data/instagram_recalibration/reports/latest.md`, `latest.json`
6. 일괄 실행 (선택)
   - `make modela-prep`
   - 공개 크롤링 일괄: `make modela-prep-crawl`
7. weak-label 학습셋 생성 (public-crawl 권장)
   - `python3 scripts/model_a_prep/05_build_weaklabel_dataset.py --input data/instagram_recalibration/raw_posts.csv --output data/instagram_recalibration/modela_ready_weak.csv`
8. 간단 크롤링 결과 변환 (선택)
   - `python3 scripts/model_a_prep/06_from_simple_crawl.py --input /path/to/instagram.xlsx --category fashion --format single --followers 500000`
   - 출력: `data/instagram_recalibration/source/converted_*.csv`
9. 로그인 없이 공개 프로필 수집 (선택)
   - `python3 scripts/model_a_prep/08_public_crawl_webapi.py --per-account 12`
   - 또는 `make modela-crawl-public-nologin`
   - 출력: `data/instagram_recalibration/source/public_webapi_*.csv`
10. 로그인 기반 수집 (권장)
   - `export INSTAGRAM_ID=...`
   - `export INSTAGRAM_PASSWORD=...`
   - `make modela-crawl-login`
   - 또는 직접:
     `python3 scripts/model_a_prep/07_public_crawl_instaloader.py --use-login --per-account 20`
   - 세션 파일 재사용:
     `data/instagram_recalibration/source/.instaloader_session_<user>`

## 기대 결과
- 카테고리/포맷 키가 계약과 100% 일치
- 포맷별 필수 컬럼 누락 없음
- 주요 수치 범위 이상치 자동 탐지
- 커버리지/결측/이상치/최근성/팔로워 분포를 한 번에 점검 가능

## public-crawl 모드 설명
- 인사이트 지표(`reach/impressions/saves/shares/...`)가 없어도 검증/리포트 가능
- 필수 최소 컬럼:
  - `post_id, created_at, category, format, caption, hashtags_count, media_count, followers, likes, comments`
- `caption`은 빈 문자열 허용(무캡션 포스트 대응)
- `make modela-prep-crawl` 실행 시 `modela_ready_weak.csv`가 생성됨
- 간단 크롤링 포맷(date/text/like/image)만 있어도 `06_from_simple_crawl.py`로 source CSV를 만들 수 있음
