.PHONY: data install test ci modela-template modela-merge modela-validate modela-report modela-prep modela-validate-crawl modela-report-crawl modela-build-weak modela-convert-simple modela-prep-crawl modela-crawl-public-nologin modela-crawl-login

# 一键初始化数据库并生成 baseline
data:
	python3 scripts/init_db.py
	python3 scripts/seed_data.py
	python3 scripts/compute_baseline.py

# 安装所有依赖
install:
	cd backend && python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt
	cd frontend && npm install

# 后端测试
test:
	cd backend && . venv/bin/activate && python -m pytest tests/ -v

# CI 检查（构建+测试）
ci: test
	cd frontend && npx tsc --noEmit && npx vite build

# Model A 재보정 준비: raw 템플릿 생성
modela-template:
	python3 scripts/model_a_prep/01_generate_template.py

# Model A 재보정 준비: source CSV 병합/정규화
modela-merge:
	python3 scripts/model_a_prep/04_merge_sources.py

# Model A 재보정 준비: raw 데이터 검증
modela-validate:
	python3 scripts/model_a_prep/02_validate_dataset.py --input data/instagram_recalibration/raw_posts.csv

# Model A 재보정 준비: raw 데이터 검증 (public-crawl mode)
modela-validate-crawl:
	python3 scripts/model_a_prep/02_validate_dataset.py --mode public-crawl --input data/instagram_recalibration/raw_posts.csv

# Model A 재보정 준비: 데이터 프로파일 리포트 생성
modela-report:
	python3 scripts/model_a_prep/03_profile_report.py --input data/instagram_recalibration/raw_posts.csv

# Model A 재보정 준비: 데이터 프로파일 리포트 생성 (public-crawl mode)
modela-report-crawl:
	python3 scripts/model_a_prep/03_profile_report.py --mode public-crawl --input data/instagram_recalibration/raw_posts.csv

# public-crawl raw -> weak-label 학습셋 생성
modela-build-weak:
	python3 scripts/model_a_prep/05_build_weaklabel_dataset.py --input data/instagram_recalibration/raw_posts.csv --output data/instagram_recalibration/modela_ready_weak.csv

# simple crawl(csv/xlsx) -> source csv 변환
# usage:
#   make modela-convert-simple INPUT=/path/to/instagram.xlsx CATEGORY=fashion FORMAT=single FOLLOWERS=500000
modela-convert-simple:
	python3 scripts/model_a_prep/06_from_simple_crawl.py --input "$(INPUT)" --category "$(CATEGORY)" --format "$(FORMAT)" --followers "$(FOLLOWERS)"

# 공개 프로필 no-login 크롤링 -> source csv 생성
modela-crawl-public-nologin:
	python3 scripts/model_a_prep/08_public_crawl_webapi.py

# 로그인 기반 크롤링(instaloader) -> source csv 생성
# 사용 전(택1):
# 1) export INSTAGRAM_ID=... && export INSTAGRAM_PASSWORD=...
# 2) make modela-crawl-login LOGIN_USER=... LOGIN_PASS=...
# 3) make modela-crawl-login LOGIN_USER=...   (비밀번호/2FA는 프롬프트 입력)
modela-crawl-login:
	python3 scripts/model_a_prep/07_public_crawl_instaloader.py --use-login --login-user "$(LOGIN_USER)" $(if $(LOGIN_PASS),--login-pass "$(LOGIN_PASS)",) $(if $(PROMPT_PASS),--prompt-pass,)

# Model A 재보정 준비: 템플릿 + 병합 + 검증 + 리포트
modela-prep: modela-template modela-merge modela-validate modela-report

# Model A 재보정 준비: 템플릿 + 병합 + 검증 + 리포트 (public-crawl mode)
modela-prep-crawl: modela-template modela-merge modela-validate-crawl modela-report-crawl modela-build-weak
