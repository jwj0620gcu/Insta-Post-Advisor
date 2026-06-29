"""
DB 연결 헬퍼.

두 종류의 데이터를 구분한다:
- baseline (notes, baseline_stats): 빌드 시 시드된 읽기 전용 데이터.
  항상 로컬 파일(baseline.db)을 사용한다. → get_baseline_connection()
- runtime (diagnosis_history, usage_log): 런타임에 쌓이며 영속 저장이 필요한 데이터.
  TURSO_DATABASE_URL(+TURSO_AUTH_TOKEN) 설정 시 Turso(libSQL)에 저장,
  미설정 시 로컬 baseline.db로 폴백(개발 환경). → get_runtime_connection()

Render 무료 플랜은 영구 디스크가 없어 재배포 때마다 로컬 파일이 초기화되므로,
운영 환경에서는 Turso로 runtime 데이터를 영속화한다.
"""
import os
import sqlite3

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BASELINE_DB_PATH = os.path.join(DATA_DIR, "baseline.db")


def get_baseline_connection() -> sqlite3.Connection:
    """baseline(notes/baseline_stats) 읽기용 로컬 SQLite 연결."""
    return sqlite3.connect(BASELINE_DB_PATH)


def _turso_config() -> tuple[str | None, str | None]:
    url = (os.getenv("TURSO_DATABASE_URL") or "").strip()
    token = (os.getenv("TURSO_AUTH_TOKEN") or "").strip()
    return (url, token) if url else (None, None)


def _libsql_available() -> bool:
    """libsql-experimental 패키지 설치 여부(선택적 의존성)."""
    import importlib.util

    return importlib.util.find_spec("libsql_experimental") is not None


def runtime_is_turso() -> bool:
    """런타임 데이터가 실제로 Turso에 저장되는지 여부.

    Turso 설정이 있어도 libsql-experimental이 설치돼 있지 않으면 로컬로 폴백하므로 False.
    """
    return _turso_config()[0] is not None and _libsql_available()


def get_runtime_connection():
    """
    runtime(diagnosis_history/usage_log)용 연결.
    Turso 설정 + libSQL 설치 시 libSQL 원격 연결, 아니면 로컬 baseline.db로 폴백한다.
    libSQL 연결도 sqlite3와 동일한 execute/commit/cursor 인터페이스를 제공한다.
    """
    url, token = _turso_config()
    if url:
        try:
            import libsql_experimental as libsql
        except ImportError:
            # libsql-experimental은 Docker 이미지(Python 3.11)에서만 설치된다.
            # 미설치 환경에서는 영속화를 포기하고 로컬 파일로 폴백한다(앱은 정상 부팅).
            print(
                "[db] TURSO_DATABASE_URL이 설정됐지만 libsql-experimental이 없어 "
                "로컬 SQLite로 폴백합니다. Turso 영속화를 쓰려면 Docker 런타임으로 배포하세요."
            )
        else:
            return libsql.connect(database=url, auth_token=token)
    os.makedirs(DATA_DIR, exist_ok=True)
    return sqlite3.connect(BASELINE_DB_PATH)


def rows_as_dicts(cursor, rows) -> list[dict]:
    """
    cursor.description의 컬럼명으로 행을 dict 리스트로 변환한다.
    sqlite3.Row / libSQL 튜플 양쪽에서 동일하게 동작한다(백엔드 무관).
    """
    cols = [c[0] for c in (cursor.description or [])]
    return [dict(zip(cols, row)) for row in rows]
