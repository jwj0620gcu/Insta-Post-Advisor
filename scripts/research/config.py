"""연구 시스템 공유 설정"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 경로
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "원시데이터"
COVERS_DIR = DATA_DIR / "covers"
OUTPUT_DIR = DATA_DIR / "research_output"
CHARTS_DIR = OUTPUT_DIR / "charts"
STATS_DIR = OUTPUT_DIR / "stats"
LLM_DIR = OUTPUT_DIR / "llm"
RESEARCH_DB = PROJECT_ROOT / "backend" / "data" / "research.db"

# 디렉터리가 없으면 생성
for d in [COVERS_DIR, CHARTS_DIR, STATS_DIR, LLM_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# .env 로드
load_dotenv(PROJECT_ROOT / "backend" / ".env", override=False)

# API 설정
API_KEY = os.getenv("OPENAI_API_KEY", "")
API_BASE = os.getenv("OPENAI_BASE_URL", "https://api.xiaomimimo.com/v1")
MODEL_FAST = os.getenv("LLM_MODEL_FAST", "mimo-v2-flash")
MODEL_PRO = os.getenv("LLM_MODEL_PRO", "mimo-v2-pro")
MODEL_OMNI = os.getenv("LLM_MODEL_OMNI", "mimo-v2-omni")

# 카테고리 매핑 (원본 파일명 키워드 → 내부 카테고리 key)
FILE_CATEGORY_MAP = {
    "美食帖": "food",
    "穿搭帖": "fashion",
    "时尚帖": "fashion",
    "穿搭博主": "fashion",
    "科技帖": "tech",
    "博主A": "tech",        # 블로거A 콘텐츠는 테크 카테고리
    "3_博主信息": "tech",   # 추천 시스템 게시글, tech에 분류
    "旅游帖": "travel",
    "美妆帖": "beauty",
    "健身帖": "fitness",
    "生活帖": "lifestyle",
    "女性觉醒博主": "lifestyle",
    "追星博主": "lifestyle",
    "家居帖": "home",
}

ALL_CATEGORIES = ["food", "fashion", "tech", "travel", "beauty", "fitness", "lifestyle", "home"]

# 동시성 제어
OMNI_CONCURRENCY = 5    # 멀티모달 분석 동시 처리 수
FLASH_CONCURRENCY = 10  # flash 모델 동시 처리 수
DOWNLOAD_CONCURRENCY = 20  # 이미지 다운로드 동시 처리 수

# 팔로워 수 구간
FAN_BUCKETS = [
    ("nano", 0, 1_000),
    ("micro", 1_000, 10_000),
    ("mid", 10_000, 100_000),
    ("macro", 100_000, 10**9),
]
