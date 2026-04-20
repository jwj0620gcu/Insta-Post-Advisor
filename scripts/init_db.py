"""
SQLite 데이터베이스를 초기화하고 baseline 데이터 테이블 구조를 생성합니다.

Usage:
    python scripts/init_db.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "baseline.db")


def init_database():
    """데이터베이스 테이블 구조를 생성합니다"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,         -- food / fashion / tech (카테고리)
            title TEXT NOT NULL,
            title_length INTEGER,
            content TEXT,
            tags TEXT,                      -- JSON array (태그 배열)
            publish_hour INTEGER,           -- 0-23 (게시 시간)
            likes INTEGER DEFAULT 0,
            collects INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            followers INTEGER DEFAULT 0,
            is_viral INTEGER DEFAULT 0,     -- 1=바이럴, 0=일반
            cover_has_face INTEGER DEFAULT 0,
            cover_text_ratio REAL DEFAULT 0,
            cover_saturation REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS baseline_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            metric_name TEXT NOT NULL,       -- 예: avg_title_length
            metric_value REAL,
            metric_json TEXT,                -- 복합 지표용 JSON
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category, metric_name)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnosis_history (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            overall_score REAL,
            grade TEXT,
            report_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_history_created
        ON diagnosis_history(created_at DESC)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_notes_category ON notes(category)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_notes_viral ON notes(category, is_viral)
    """)

    conn.commit()
    conn.close()
    print(f"데이터베이스가 초기화되었습니다: {os.path.abspath(DB_PATH)}")


if __name__ == "__main__":
    init_database()
