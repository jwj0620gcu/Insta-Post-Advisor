"""
개발 및 데모용 시뮬레이션 baseline 시드 데이터를 생성합니다.
실제 서비스 전에 실제로 수집한 Instagram 게시글 데이터로 교체해야 합니다.

Usage:
    python scripts/seed_data.py
"""
import sqlite3
import json
import random
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "baseline.db")

FOOD_TITLES = [
    "집에서 만드는 일본식 반숙 달걀! 실패 없음!", "1주일 다이어트 식단 공유｜맛있고 살 안 찌는",
    "이 집 소고기 국수 대박! 2시간 줄 세울 만해", "5분 아침 식사｜직장인 필수 간편 요리",
    "집에서 미슐랭 디저트 따라 만들기, 재료비 2만원 이하", "오늘의 도시락🍱 간단하고 예쁜",
    "샤브샤브 육수 브랜드 10개 비교 리뷰!", "다이어트 중에도 먹을 수 있는 신의 디저트 모음",
    "탐방｜골목 안에 숨어 있는 숨은 카페", "에어프라이어 레시피 모음｜귀차니스트 필수",
    "혼밥 저녁｜혼자 사는 소소한 행복", "인스타 맛집 낚이지 않는 가이드‼️ 더 이상 속지 마세요",
    "가을 첫 버블티 직접 만들기🧋", "기숙사 필수템! 불도 전기도 없이 푸짐한 식사",
    "엄마의 맛｜집밥 돼지고기 조림 레시피", "저칼로리 고단백 샐러드｜먹을수록 날씬해지는",
]

FASHION_TITLES = [
    "소키즈 코디｜155cm도 롱 레그 가능", "한 옷 여러 가지로｜흰 셔츠 7가지 코디",
    "가을겨울 필수 기본템 5가지｜뭐든 잘 어울리는", "통통한 여자의 슬리밍 코디 공식",
    "출근 코디 공유｜회사에서도 예쁘게", "오늘의 OOTD｜일본풍 감성 스타일",
    "학생 가성비 코디｜전신 10만원 이하", "이 바지 너무 다리 길어 보이는 거 아님?!",
    "한국풍 코디 모음｜뼛속까지 부드러운", "피부 밝아 보이는 코디｜노란 피부 필독",
    "봄 코디 영감｜뚱뚱해 보이지 않게 나가기", "코트+스웨터의 환상 조합",
    "분위기 있는 코디 튜토리얼｜한국 드라마 여주인공 변신", "서양 배 체형 코디 가이드｜살 가리고 슬리밍",
    "미니멀 코디｜옷장에 이 10개만 있으면 됨", "데이트 코디｜달콤하고 세련된 하루",
]

TECH_TITLES = [
    "2024 가장 살 만한 태블릿 추천", "iPhone vs 안드로이드? 실제 1년 사용 비교",
    "개발자 필수 10가지 생산성 도구", "AI 그림 입문 튜토리얼｜왕초보도 대작 가능",
    "MacBook 구매 가이드｜돈 낭비하지 마세요", "스마트홈 리모델링 전체 기록｜3만 원 쓸 만했나",
    "이 앱이 내 공부 방식을 바꿨어", "디지털 기기 연말 결산｜이거 써보면 울어",
    "iPad 공부법｜꼴찌에서 우등생으로", "이어폰 비교｜10만원 이하 가장 살 만한 5개",
    "NAS 입문 가이드｜개인 클라우드 스토리지 만들기", "폰 사진 스킬｜영화 감성 찍기",
    "기계식 키보드 입문 가이드｜초보 필독", "중고 디지털 기기 사기 방지 가이드‼️",
    "AI 도구 모음｜효율 10배 향상", "미니멀 책상 세팅｜고효율 작업 공간 만들기",
]

TRAVEL_TITLES = [
    "제주 5박 4일 완전 가이드｜1인 30만원", "숨은 여행지 추천｜국내 가장 아름다운 10개 소도시",
    "처음 일본 가는 사람｜도쿄 오사카 자유여행 가이드", "주말 어디 갈까? 서울 근교 당일치기 모음",
    "등산 자동차 여행기｜살면서 꼭 한번 가야 해", "여행 사진 명소｜출사율 초고 스팟 공유",
    "캠핑 장비 체크리스트｜입문자 가이드", "유니버셜 스튜디오 절약 공략｜줄 안 서고 다 타는 법",
    "부산 3박 2일｜먹고 즐기고 구경하는 완전 가이드", "태국 방콕 파타야 7일 자세한 일정",
    "전국 가장 아름다운 도서관 TOP10 방문", "해안도로 드라이브｜달리면서 보는 풍경",
    "홋카이도 겨울 여행｜설경이 너무 예뻐", "부산 여행 꼭 가봐야 할 20곳",
    "유럽 저예산 여행 공략｜월급 50만원으로도 갈 수 있어", "섬 휴양｜국내 가장 갈 만한 5개 섬",
]

BEAUTY_TITLES = [
    "노란 피부 밝아 보이는 립스틱 모음｜바르는 순간 화이트닝", "초보 메이크업 튜토리얼｜5분 데일리 메이크업",
    "2024 연간 애용 스킨케어 결산", "모공 넓은 거 어떡해? 직접 써보고 효과 있는 방법",
    "가성비 스킨케어 추천｜학생 필수", "여름 메이크업 지속력의 비결이 여기 있었어!",
    "민감성 피부 스킨케어 가이드｜함부로 바르지 마세요", "아이섀도 배색 공식｜초보도 고급스럽게",
    "선크림 리뷰｜지성 건성 각각 어떻게 고를까", "미백 세럼 비교｜어떤 게 진짜 효과 있어?",
    "메이크업 브러시 입문 추천｜이 몇 개면 충분해", "환절기 스킨케어 공략｜환절기에 트러블 없이",
    "컨투어 튜토리얼｜둥근 얼굴 순식간에 V라인으로", "블러셔 바르는 법 총정리｜얼굴형별 적용법",
    "베이스 메이크업 스킬｜인형 얼굴 탈출", "마스카라 리뷰｜풍성함 섬세함 컬링 다 해결",
]

FITNESS_TITLES = [
    "홈트｜매일 30분으로 복근 만들기", "파멜라 1주일 따라하기 계획｜진짜 빠짐",
    "달리기 입문｜0에서 5km까지", "다이어트 기간에 어떻게 먹어? 칼로리 계산 공식 공유",
    "요가 입문｜왕초보도 할 수 있는 10가지 동작", "근육 늘리기 식이 가이드｜단백질 보충 방법",
    "직장인 스트레칭｜5분으로 장시간 앉아서 오는 통증 해소", "헬스장 기구 사용 가이드｜초보 필독",
    "한 달에 5kg 감량 실제 기록", "힙업 트레이닝 플랜｜집에서도 가능",
    "자세 교정｜굽은 등 라운드 숄더 이렇게 고치기", "다이어트 vs 감량｜90%가 착각하는 것",
    "아침 달리기 vs 저녁 달리기｜어느 것이 당신에게 더 적합한가", "HIIT 트레이닝 모음｜지방 연소 효율 2배",
    "프로틴 어떻게 고를까? 브랜드 비교 리뷰", "스트레칭 총정리｜운동 전후 올바른 자세",
]

FOOD_TAGS = ["맛집 공유", "레시피", "다이어트 식단", "아침식사", "맛집 탐방", "집밥", "베이킹", "다이어트 식단", "샤브샤브", "카페"]
FASHION_TAGS = ["코디", "OOTD", "슬리밍", "가성비 코디", "한국풍", "일본풍", "출근 코디", "기본템", "스타일링", "가을겨울 코디"]
TECH_TAGS = ["디지털", "테크", "추천 템", "생산성 도구", "AI", "iPad", "스마트폰", "스마트홈", "앱 추천", "리뷰"]
TRAVEL_TAGS = ["여행 가이드", "자유여행", "여행 사진", "방문", "주말 여행", "드라이브 여행", "캠핑", "섬", "숨은 여행지", "절약 공략"]
BEAUTY_TAGS = ["스킨케어", "메이크업 튜토리얼", "립스틱", "선크림", "민감성 피부", "미백", "가성비 아이템", "베이스 메이크업", "아이섀도", "리뷰"]
FITNESS_TAGS = ["운동", "다이어트", "요가", "달리기", "홈트", "복근", "근육 증가", "자세 교정", "감량", "스트레칭"]

LIFESTYLE_TITLES = [
    "혼자 사는 여자의 하루｜치유되는 주말 vlog", "월세방 리모델링｜50만원으로 인스타 감성 방 만들기",
    "행복감을 높여주는 생활 소소한 습관 10가지", "미니멀 라이프｜비우고 난 후의 변화",
    "1인 생활의 의식｜아침 루틴", "대학생 절약 공략｜한 달 150만원 충분할까",
    "이사 정리술｜캐리어 수납 스킬", "사회공포증 여자의 혼자 일상",
    "30일 일찍 일어나기 챌린지｜내 생활이 완전히 바뀌었어", "퇴근 후 3시간을 어떻게 보낼까?",
    "추천 템｜삶의 질을 높여주는 작은 것들", "시간 관리｜평범한 사람도 하루를 효율적으로",
    "혼자라도 제대로 밥 먹기｜혼자 사는 일기", "주말 집콕 계획｜알차면서도 편안한",
    "졸업 후 첫 1년 혼자 살기｜진솔한 소감", "생활 추천 템｜한 번 써보면 못 돌아가는 소형가전",
]

HOME_TITLES = [
    "소형 평수 수납｜40㎡도 100㎡ 느낌으로 살기", "거실 리모델링｜30만원으로 완전히 새로워진",
    "이케아 추천 아이템｜이 10만원 이하 아이템 대박", "인스타 감성 침실 인테리어｜월세방도 예쁠 수 있어",
    "주방 수납 비법｜조리대 항상 깔끔하게", "홈 인테리어 모음｜행복감 높이는 20가지",
    "전체 조명 디자인｜분위기 폭발", "화장실 리모델링 전후 비교｜차이가 너무 커",
    "미니멀 인테리어｜우리 집 인테리어 비용 목록", "발코니 리모델링｜도시의 작은 정원 만들기",
    "책상 인테리어 공유｜공부 효율 2배", "홈 방향제 추천｜방 자체에서 고급스러운 향기",
    "중고 가구 DIY 리모델링｜절약하면서 예쁘게", "스마트홈 입문｜전체 스마트화 비용",
    "월세방 리모델링｜벽 안 망가뜨리는 데코 방법", "일본식 수납술｜일본 주부한테 정리 배우기",
]

LIFESTYLE_TAGS = ["라이프스타일", "혼자 사는 일상", "vlog", "일상 공유", "자기 관리", "자기 계발", "절약", "시간 관리", "생활 기록", "힐링"]
HOME_TAGS = ["홈 인테리어", "수납", "인테리어", "리모델링", "추천 템", "소형 평수", "월세방 리모델링", "이케아", "홈 인테리어 아이템", "인테리어 영감"]


def generate_notes(category, titles, tags_pool, count=500):
    """지정된 카테고리의 시뮬레이션 게시글 데이터를 생성합니다"""
    notes = []
    for _ in range(count):
        title = random.choice(titles)
        title_var = title
        if random.random() > 0.5:
            suffixes = ["", "！", "✨", "🔥", "｜建议收藏", "‼️"]
            title_var = title + random.choice(suffixes)

        num_tags = random.randint(2, 8)
        selected_tags = random.sample(tags_pool, min(num_tags, len(tags_pool)))

        is_viral = random.random() < 0.15
        if is_viral:
            likes = random.randint(500, 50000)
            collects = random.randint(200, 20000)
            comments = random.randint(50, 5000)
        else:
            likes = random.randint(0, 500)
            collects = random.randint(0, 200)
            comments = random.randint(0, 50)

        notes.append((
            category,
            title_var,
            len(title_var),
            f"이것은 {category}에 관한 게시글 본문 내용으로, 자세한 공유를 담고 있습니다...",
            json.dumps(selected_tags, ensure_ascii=False),
            random.randint(6, 23),
            likes,
            collects,
            comments,
            random.choice([500, 1000, 5000, 10000, 50000, 100000]),
            1 if is_viral else 0,
            1 if random.random() > 0.4 else 0,
            round(random.uniform(0.05, 0.4), 2),
            round(random.uniform(0.3, 0.9), 2),
        ))
    return notes


def seed():
    """시드 데이터를 작성합니다"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM notes")

    all_notes = []
    all_notes.extend(generate_notes("food", FOOD_TITLES, FOOD_TAGS, 500))
    all_notes.extend(generate_notes("fashion", FASHION_TITLES, FASHION_TAGS, 500))
    all_notes.extend(generate_notes("tech", TECH_TITLES, TECH_TAGS, 500))
    all_notes.extend(generate_notes("travel", TRAVEL_TITLES, TRAVEL_TAGS, 500))
    all_notes.extend(generate_notes("beauty", BEAUTY_TITLES, BEAUTY_TAGS, 500))
    all_notes.extend(generate_notes("fitness", FITNESS_TITLES, FITNESS_TAGS, 500))
    all_notes.extend(generate_notes("lifestyle", LIFESTYLE_TITLES, LIFESTYLE_TAGS, 500))
    all_notes.extend(generate_notes("home", HOME_TITLES, HOME_TAGS, 500))

    cursor.executemany("""
        INSERT INTO notes (
            category, title, title_length, content, tags,
            publish_hour, likes, collects, comments, followers,
            is_viral, cover_has_face, cover_text_ratio, cover_saturation
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, all_notes)

    conn.commit()
    print(f"{len(all_notes)}개의 시드 데이터가 삽입되었습니다")
    conn.close()


if __name__ == "__main__":
    seed()
