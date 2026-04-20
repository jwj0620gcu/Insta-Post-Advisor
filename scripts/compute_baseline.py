"""
notes 테이블 데이터를 기반으로 각 카테고리의 baseline 통계 지표를 사전 계산하여 baseline_stats 테이블에 저장합니다.

Usage:
    python scripts/compute_baseline.py
"""
import sqlite3
import json
import os
from collections import Counter

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "baseline.db")


def upsert_stat(cursor, category, metric_name, metric_value=None, metric_json=None):
    """통계 지표 하나를 삽입하거나 업데이트합니다"""
    cursor.execute("""
        INSERT INTO baseline_stats (category, metric_name, metric_value, metric_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(category, metric_name)
        DO UPDATE SET metric_value=excluded.metric_value,
                      metric_json=excluded.metric_json,
                      updated_at=CURRENT_TIMESTAMP
    """, (category, metric_name, metric_value, metric_json))


def compute_for_category(cursor, category):
    """지정된 카테고리의 모든 baseline 지표를 계산합니다"""

    # --- 제목 통계 ---
    cursor.execute(
        "SELECT AVG(title_length) FROM notes WHERE category=?", (category,)
    )
    avg_title_len = cursor.fetchone()[0] or 0
    upsert_stat(cursor, category, "avg_title_length", round(avg_title_len, 1))

    cursor.execute(
        "SELECT AVG(title_length) FROM notes WHERE category=? AND is_viral=1",
        (category,),
    )
    viral_avg_title_len = cursor.fetchone()[0] or 0
    upsert_stat(cursor, category, "viral_avg_title_length", round(viral_avg_title_len, 1))

    # --- 태그 통계 ---
    cursor.execute("SELECT tags FROM notes WHERE category=?", (category,))
    tag_counter = Counter()
    tag_counts = []
    for (tags_json,) in cursor.fetchall():
        try:
            t = json.loads(tags_json)
            tag_counter.update(t)
            tag_counts.append(len(t))
        except (json.JSONDecodeError, TypeError):
            pass

    avg_tag_count = sum(tag_counts) / len(tag_counts) if tag_counts else 0
    upsert_stat(cursor, category, "avg_tag_count", round(avg_tag_count, 1))

    top_tags = [{"tag": t, "count": c} for t, c in tag_counter.most_common(20)]
    upsert_stat(cursor, category, "top_tags", metric_json=json.dumps(top_tags, ensure_ascii=False))

    # --- 인터랙션 데이터 ---
    for metric in ["likes", "collects", "comments"]:
        cursor.execute(
            f"SELECT AVG({metric}), MAX({metric}) FROM notes WHERE category=?",
            (category,),
        )
        avg_val, max_val = cursor.fetchone()
        upsert_stat(cursor, category, f"avg_{metric}", round(avg_val or 0, 1))
        upsert_stat(cursor, category, f"max_{metric}", max_val or 0)

        cursor.execute(
            f"SELECT AVG({metric}) FROM notes WHERE category=? AND is_viral=1",
            (category,),
        )
        viral_avg = cursor.fetchone()[0] or 0
        upsert_stat(cursor, category, f"viral_avg_{metric}", round(viral_avg, 1))

    # --- 게시 시간 분포 ---
    cursor.execute("""
        SELECT publish_hour, COUNT(*) as cnt,
               AVG(likes + collects + comments) as avg_engagement
        FROM notes WHERE category=?
        GROUP BY publish_hour ORDER BY publish_hour
    """, (category,))
    hour_dist = [
        {"hour": h, "count": c, "avg_engagement": round(e, 1)}
        for h, c, e in cursor.fetchall()
    ]
    upsert_stat(cursor, category, "hour_distribution",
                metric_json=json.dumps(hour_dist, ensure_ascii=False))

    # --- 커버 통계 ---
    cursor.execute(
        "SELECT AVG(cover_has_face), AVG(cover_text_ratio), AVG(cover_saturation) "
        "FROM notes WHERE category=?",
        (category,),
    )
    face_rate, text_ratio, saturation = cursor.fetchone()
    upsert_stat(cursor, category, "cover_face_rate", round((face_rate or 0) * 100, 1))
    upsert_stat(cursor, category, "cover_avg_text_ratio", round(text_ratio or 0, 3))
    upsert_stat(cursor, category, "cover_avg_saturation", round(saturation or 0, 3))

    cursor.execute(
        "SELECT AVG(cover_has_face), AVG(cover_text_ratio), AVG(cover_saturation) "
        "FROM notes WHERE category=? AND is_viral=1",
        (category,),
    )
    vf, vt, vs = cursor.fetchone()
    upsert_stat(cursor, category, "viral_cover_face_rate", round((vf or 0) * 100, 1))
    upsert_stat(cursor, category, "viral_cover_avg_text_ratio", round(vt or 0, 3))
    upsert_stat(cursor, category, "viral_cover_avg_saturation", round(vs or 0, 3))

    # --- 바이럴 비율 ---
    cursor.execute(
        "SELECT COUNT(*) FROM notes WHERE category=? AND is_viral=1", (category,)
    )
    viral_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM notes WHERE category=?", (category,))
    total_count = cursor.fetchone()[0]
    viral_rate = (viral_count / total_count * 100) if total_count else 0
    upsert_stat(cursor, category, "viral_rate", round(viral_rate, 1))

    # --- 팔로워 계층별 통계 ---
    fan_buckets = [
        ("nano", 0, 1000),
        ("micro", 1000, 10000),
        ("mid", 10000, 100000),
        ("macro", 100000, 10**9),
    ]
    fan_stats = []
    for label, lo, hi in fan_buckets:
        cursor.execute("""
            SELECT COUNT(*), AVG(likes + collects + comments),
                   AVG(CASE WHEN is_viral=1 THEN 1.0 ELSE 0.0 END)
            FROM notes WHERE category=? AND followers >= ? AND followers < ?
        """, (category, lo, hi))
        cnt, avg_eng, vr = cursor.fetchone()
        fan_stats.append({
            "bucket": label,
            "range": f"{lo}-{hi}",
            "count": cnt or 0,
            "avg_engagement": round(avg_eng or 0, 1),
            "viral_rate": round((vr or 0) * 100, 1),
        })
    upsert_stat(cursor, category, "fan_bucket_stats",
                metric_json=json.dumps(fan_stats, ensure_ascii=False))

    # --- 태그 수 구간별 vs 인터랙션율 ---
    cursor.execute("""
        SELECT tags, likes + collects + comments as eng
        FROM notes WHERE category=?
    """, (category,))
    tag_buckets: dict[str, list[float]] = {}
    for (tags_json, eng) in cursor.fetchall():
        try:
            n = len(json.loads(tags_json))
        except (json.JSONDecodeError, TypeError):
            n = 0
        bucket = f"{n}" if n <= 8 else "9+"
        tag_buckets.setdefault(bucket, []).append(eng)

    tag_bucket_stats = []
    for bucket in sorted(tag_buckets.keys(), key=lambda x: int(x.replace("+", ""))):
        vals = tag_buckets[bucket]
        tag_bucket_stats.append({
            "tag_count": bucket,
            "note_count": len(vals),
            "avg_engagement": round(sum(vals) / len(vals), 1) if vals else 0,
        })
    upsert_stat(cursor, category, "tag_count_vs_engagement",
                metric_json=json.dumps(tag_bucket_stats, ensure_ascii=False))

    print(f"  [{category}] baseline 지표 계산 완료 (팔로워 계층 및 태그 구간 포함)")


def main():
    """모든 카테고리의 baseline 통계 지표를 계산합니다"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM baseline_stats")

    for cat in ["food", "fashion", "tech", "travel", "beauty", "fitness", "lifestyle", "home"]:
        compute_for_category(cursor, cat)

    conn.commit()
    conn.close()
    print("모든 baseline 통계 지표 계산이 완료되었습니다")


if __name__ == "__main__":
    main()
