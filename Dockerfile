# syntax=docker/dockerfile:1
# Insta-Advisor 프로덕션 이미지
# 멀티스테이지: (1) 프론트엔드 빌드 → (2) ffmpeg 포함 Python 런타임
# 단일 컨테이너 · 단일 포트($PORT)로 SPA + API + STT를 모두 서빙한다.

# ---- Stage 1: 프론트엔드(SPA) 빌드 ----
FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python 런타임 ----
FROM python:3.11-slim AS runtime

# ffmpeg: 영상 STT(오디오 추출)에 필수
# libGL/glib: opencv-python-headless 런타임 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 파이썬 의존성 (레이어 캐시를 위해 먼저 복사)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 애플리케이션 소스
COPY backend/ backend/
COPY scripts/ scripts/
COPY docs/ docs/

# Stage 1에서 빌드한 SPA 산출물
COPY --from=frontend /app/frontend/dist frontend/dist

# 빌드 시 baseline DB 시드 (런타임에는 diagnosis_history/usage_log만 자동 생성)
RUN python scripts/init_db.py \
    && python scripts/seed_data.py \
    && python scripts/compute_baseline.py

ENV PYTHONUNBUFFERED=1 \
    PORT=8001

EXPOSE 8001
WORKDIR /app/backend

# $PORT는 플랫폼(Render 등)이 주입; 없으면 8001
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
