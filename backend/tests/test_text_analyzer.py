"""
텍스트 분석 모듈 테스트
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.analysis.text_analyzer import TextAnalyzer


analyzer = TextAnalyzer()


def test_title_length():
    """제목 분석은 올바른 글자 수를 반환해야 한다"""
    result = analyzer.analyze_title("초간단 일식 반숙달걀 만들기! 실패 없음!")
    assert result["length"] == len("초간단 일식 반숙달걀 만들기! 실패 없음!")
    assert "keywords" in result
    assert "score" in result


def test_title_hooks():
    """숫자가 포함된 제목은 hook을 감지해야 한다"""
    result = analyzer.analyze_title("5분 만에 만드는 아침밥 3종!")
    assert result["has_numbers"] is True
    assert result["hook_count"] >= 1


def test_empty_content():
    """빈 본문은 0값을 반환해야 한다"""
    result = analyzer.analyze_content("")
    assert result["length"] == 0
    assert result["paragraph_count"] == 0


def test_content_paragraphs():
    """본문 단락 수 집계가 올바르게 동작해야 한다"""
    text = "첫 번째 단락 내용\n\n두 번째 단락 내용\n\n세 번째 단락 내용"
    result = analyzer.analyze_content(text)
    assert result["paragraph_count"] == 3


def test_emotion_detection():
    """제목의 감정 단어가 감지되어야 한다"""
    result = analyzer.analyze_title("이 숨은 맛집 대박! 강추합니다")
    emotions = [e["word"] for e in result["emotion_words"]]
    assert "대박" in emotions or "강추" in emotions or "추천" in emotions
