"""
Baseline 비교 엔진.
사용자 노트 특성을 카테고리별 baseline과 정량 비교한다.
"""
import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "baseline.db")


class BaselineComparator:
    """사용자 노트 특성과 baseline 데이터를 비교한다."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def get_category_stats(self, category: str) -> dict:
        """
        지정 카테고리의 baseline 통계를 조회한다.

        @param category - 카테고리 식별자 (food / fashion / tech)
        @returns dict 전체 통계 지표
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT metric_name, metric_value, metric_json FROM baseline_stats WHERE category=?",
            (category,),
        )
        stats = {}
        for name, value, json_str in cursor.fetchall():
            if json_str:
                stats[name] = json.loads(json_str)
            else:
                stats[name] = value
        conn.close()
        return {"category": category, "stats": stats}

    def compare(self, category: str, note_features: dict) -> dict:
        """
        노트 특성을 baseline과 비교해 차이 분석을 반환한다.

        @param category - 카테고리
        @param note_features - 노트 분석 결과 (title_analysis + content_analysis + image_analysis)
        @returns dict 차원별 비교 결과
        """
        baseline = self.get_category_stats(category)
        stats = baseline.get("stats", {})

        comparisons = {}

        title_len = note_features.get("title_length", 0)
        avg_title_len = stats.get("avg_title_length", 0)
        viral_title_len = stats.get("viral_avg_title_length", 0)
        comparisons["title_length"] = {
            "user_value": title_len,
            "category_avg": avg_title_len,
            "viral_avg": viral_title_len,
            "deviation": round(title_len - avg_title_len, 1),
            "verdict": self._judge_deviation(title_len, avg_title_len, viral_title_len),
        }

        tag_count = note_features.get("tag_count", 0)
        avg_tag_count = stats.get("avg_tag_count", 0)
        comparisons["tag_count"] = {
            "user_value": tag_count,
            "category_avg": avg_tag_count,
            "deviation": round(tag_count - avg_tag_count, 1),
            "verdict": "too_few" if tag_count < avg_tag_count * 0.7 else (
                "too_many" if tag_count > avg_tag_count * 1.5 else "balanced"
            ),
        }

        top_tags = stats.get("top_tags", [])
        user_tags = note_features.get("tags", [])
        hot_tag_names = {t["tag"] for t in top_tags[:10]} if isinstance(top_tags, list) else set()
        matched = [t for t in user_tags if t in hot_tag_names]
        comparisons["tag_relevance"] = {
            "matched_hot_tags": matched,
            "hot_tag_coverage": round(len(matched) / max(len(user_tags), 1), 2),
            "top_tags_in_category": [t["tag"] for t in top_tags[:10]] if isinstance(top_tags, list) else [],
        }

        if "saturation" in note_features:
            sat = note_features["saturation"]
            avg_sat = stats.get("cover_avg_saturation", 0)
            viral_sat = stats.get("viral_cover_avg_saturation", 0)
            comparisons["cover_saturation"] = {
                "user_value": sat,
                "category_avg": avg_sat,
                "viral_avg": viral_sat,
                "verdict": "too_low" if sat < avg_sat * 0.8 else ("too_high" if sat > avg_sat * 1.3 else "balanced"),
            }

        if "text_ratio" in note_features:
            tr = note_features["text_ratio"]
            avg_tr = stats.get("cover_avg_text_ratio", 0)
            comparisons["cover_text_ratio"] = {
                "user_value": tr,
                "category_avg": avg_tr,
                "verdict": "too_low" if tr < 0.1 else ("too_high" if tr > 0.4 else "balanced"),
            }

        if "has_face" in note_features:
            face_rate = stats.get("cover_face_rate", 0)
            comparisons["cover_face"] = {
                "user_has_face": note_features["has_face"],
                "category_face_rate": f"{face_rate}%",
                "suggestion": "consider showing face" if face_rate > 50 and not note_features["has_face"] else "",
            }

        hour_dist = stats.get("hour_distribution", [])
        if isinstance(hour_dist, list) and hour_dist:
            best_hours = sorted(hour_dist, key=lambda x: x.get("avg_engagement", 0), reverse=True)[:3]
            comparisons["best_publish_hours"] = [h["hour"] for h in best_hours]

        comparisons["viral_rate"] = stats.get("viral_rate", 0)

        # avg_engagement가 없으면 구성 지표에서 산출
        avg_engagement = stats.get("avg_engagement")
        if avg_engagement is None:
            avg_likes = stats.get("avg_likes", 0) or 0
            avg_collects = stats.get("avg_collects", 0) or 0
            avg_comments = stats.get("avg_comments", 0) or 0
            avg_engagement = round(avg_likes + avg_collects + avg_comments, 1)
        comparisons["avg_engagement"] = avg_engagement

        viral_engagement = None
        vl = stats.get("viral_avg_likes", 0) or 0
        vc = stats.get("viral_avg_collects", 0) or 0
        vco = stats.get("viral_avg_comments", 0) or 0
        if vl or vc or vco:
            viral_engagement = round(vl + vc + vco, 1)
        comparisons["viral_engagement"] = viral_engagement

        return {
            "category": category,
            "comparisons": comparisons,
            "raw_stats": stats,
        }

    def _judge_deviation(self, user_val, avg_val, viral_val) -> str:
        """편차 방향을 판단한다."""
        if abs(user_val - viral_val) < abs(user_val - avg_val):
            return "close_to_viral_level"
        if user_val < avg_val * 0.7:
            return "significantly_low"
        if user_val > avg_val * 1.3:
            return "significantly_high"
        return "within_normal_range"
