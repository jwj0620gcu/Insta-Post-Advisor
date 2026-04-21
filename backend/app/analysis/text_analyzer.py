"""
텍스트 분석 모듈
인스타 게시물의 제목/캡션 품질을 경량 규칙으로 분석한다.
한국어 특화 — jieba(중국어) 의존성 없음.
"""
from __future__ import annotations

import re

# kiwi(한국어 형태소 분석기) 선택적 사용 — 없으면 regex 폴백
try:
    from kiwipiepy import Kiwi
    _kiwi = Kiwi()
    _KIWI_AVAILABLE = True
except Exception:
    _kiwi = None
    _KIWI_AVAILABLE = False


EMOTION_WORDS = {
    "positive": [
        "추천", "꿀팁", "대박", "좋다", "최고", "만족", "필수", "강추", "미쳤다",
        "완전", "찐", "갓", "레전드", "맛있", "예쁘", "힐링", "소름", "감동",
        "역대급", "인생샷", "핫플", "뷰맛집",
    ],
    "negative": [
        "비추", "실망", "후회", "별로", "최악", "문제", "실패", "주의", "논란",
        "별로", "아쉽", "불편", "최악", "쓰레기",
    ],
    "urgency": [
        "지금", "오늘", "당장", "마감", "한정", "놓치지", "필독", "저장", "필수",
        "기간한정", "한정수량", "마지막", "오늘만", "이벤트",
    ],
}

# 인스타 후킹 패턴
HOOK_PATTERNS = [
    r"\d+",                        # 숫자 (3가지, 5분, 1만원)
    r"[！!]{1,}",                   # 느낌표
    r"[?？]",                       # 물음표
    r"[｜|]",                       # 분리자
    r"[\U0001f300-\U0001f9ff]",    # 이모지
    r"(진짜|대박|꿀팁|무조건|필수|비밀|공개|저장|레알|미쳤|실화냐|레전드|솔직히|고백)",
    r"(무료|공짜|할인|특가|세일|이벤트|증정|혜택)",  # 혜택/프로모션 키워드
    r"(방법|비결|노하우|팁|공략|후기|리뷰)",         # 정보성 키워드
]

# 한국어 + 영숫자 토큰 패턴
WORD_RE = re.compile(r"[0-9A-Za-z가-힣_]+")

# 인스타 캡션 최적 길이 기준 (카테고리 실데이터 기반)
CAPTION_OPTIMAL = {
    "food": (100, 300),
    "fashion": (80, 250),
    "fitness": (150, 400),
    "business": (200, 500),
    "lifestyle": (100, 350),
    "travel": (150, 400),
    "education": (300, 600),
    "shop": (150, 400),
    "default": (100, 400),
}


class TextAnalyzer:
    """인스타 게시물 텍스트 품질 분석기."""

    def analyze_title(self, title: str) -> dict:
        """제목/첫 문장(캡션 첫 125자) 분석."""
        length = len(title or "")
        keywords = self._extract_keywords(title)
        keyword_list = [{"word": w, "weight": round(s, 3)} for w, s in keywords]

        emotion_found = self._find_emotion_words(title)
        hook_count = sum(1 for p in HOOK_PATTERNS if re.search(p, title or ""))
        has_numbers = bool(re.search(r"\d+", title or ""))

        score = self._score_title(length, hook_count, len(emotion_found), has_numbers)

        return {
            "length": length,
            "keywords": keyword_list,
            "emotion_words": emotion_found,
            "hook_count": hook_count,
            "has_numbers": has_numbers,
            "score": score,
        }

    def analyze_content(self, content: str, category: str = "default") -> dict:
        """캡션 본문 분석."""
        if not content or not content.strip():
            return {
                "length": 0,
                "paragraph_count": 0,
                "avg_sentence_length": 0,
                "has_emoji": False,
                "readability_score": 0,
                "info_density": 0,
            }

        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        sentences = re.split(r"[。！？!?;\n]", content)
        sentences = [s.strip() for s in sentences if s.strip()]
        avg_sent_len = sum(len(s) for s in sentences) / max(len(sentences), 1)

        emoji_pattern = re.compile(r"[\U0001f300-\U0001f9ff]")
        has_emoji = bool(emoji_pattern.search(content))

        words = self._tokenize(content)
        unique_words = set(words)
        info_density = len(unique_words) / max(len(words), 1)

        readability = self._calc_readability(avg_sent_len, len(paragraphs), has_emoji)

        return {
            "length": len(content),
            "paragraph_count": len(paragraphs),
            "sentence_count": len(sentences),
            "avg_sentence_length": round(avg_sent_len, 1),
            "has_emoji": has_emoji,
            "readability_score": readability,
            "info_density": round(info_density, 3),
        }

    @staticmethod
    def _rank_by_frequency(tokens: list[str]) -> list[tuple[str, float]]:
        freq: dict[str, int] = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:10]
        if not top:
            return []
        max_freq = float(top[0][1])
        return [(w, c / max_freq) for w, c in top]

    def _extract_keywords(self, text: str) -> list[tuple[str, float]]:
        if not text:
            return []

        if _KIWI_AVAILABLE and _kiwi is not None:
            try:
                result = _kiwi.analyze(text)
                tokens = [
                    token for token, pos, *_ in result[0][0]
                    # NNG(일반명사), NNP(고유명사), VA(형용사), VV(동사)
                    if pos.startswith(("NN", "VA", "VV")) and len(token) > 1
                ]
                return self._rank_by_frequency(tokens)
            except Exception:
                pass

        tokens = [t for t in self._tokenize(text) if len(t) > 1]
        return self._rank_by_frequency(tokens)

    def _tokenize(self, text: str) -> list[str]:
        if _KIWI_AVAILABLE and _kiwi is not None:
            try:
                result = _kiwi.analyze(text)
                return [token for token, pos, *_ in result[0][0] if token.strip()]
            except Exception:
                pass
        return WORD_RE.findall(text or "")

    def _find_emotion_words(self, text: str) -> list[dict]:
        found = []
        text = text or ""
        for category, words in EMOTION_WORDS.items():
            for w in words:
                if w in text:
                    found.append({"word": w, "type": category})
        return found

    def _score_title(self, length: int, hooks: int, emotions: int, has_num: bool) -> float:
        """인스타 첫 문장/제목 점수(0-100).
        인스타 캡션은 첫 125자가 '더 보기' 클릭 전 노출됨.
        최적 구간: 15-60자 (짧고 후킹력 있는 첫 문장)
        """
        score = 50.0

        if 15 <= length <= 60:
            score += 15
        elif 8 <= length < 15 or 60 < length <= 100:
            score += 8
        else:
            score -= 10

        score += min(hooks, 4) * 7
        score += min(emotions, 2) * 6
        if has_num:
            score += 5

        return min(max(round(score, 1), 0), 100)

    def _calc_readability(self, avg_sent_len: float, para_count: int, has_emoji: bool) -> float:
        """인스타 캡션 가독성 점수(0-100).
        모바일 기준 짧은 문장 + 줄바꿈 + 이모지가 유리.
        """
        score = 50.0

        # 인스타 모바일 최적: 문장당 15-30자
        if 10 <= avg_sent_len <= 30:
            score += 20
        elif avg_sent_len < 10:
            score += 12  # 너무 짧아도 괜찮음 (반응형 댓글 스타일)
        else:
            score -= 10

        if para_count >= 3:
            score += 15
        elif para_count >= 2:
            score += 8

        if has_emoji:
            score += 10

        return min(max(round(score, 1), 0), 100)
