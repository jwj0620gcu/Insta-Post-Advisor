/**
 * 오프라인 fallback 데이터 — 백엔드를 사용할 수 없을 때 표시
 */
import type { DiagnoseResult } from "./api";

export const FALLBACK_REPORT: DiagnoseResult = {
  overall_score: 62,
  grade: "B",
  radar_data: {
    content: 70,
    visual: 55,
    growth: 58,
    user_reaction: 65,
    overall: 62,
  },
  agent_opinions: [
    {
      agent_name: "캡션 분석가",
      dimension: "콘텐츠 품질",
      score: 70,
      issues: [
        "캡션 첫 줄에 구체적인 숫자나 후킹 문구가 없어 클릭 유인이 부족합니다",
        "본문 단락 구분이 부족합니다. 3~5개 블록으로 나누는 것을 권장합니다",
      ],
      suggestions: [
        "캡션 첫 줄에 숫자를 넣어 보세요. 예: 「5가지 방법」 「3분 만에」",
        "각 단락 시작에 이모지를 활용해 가독성을 높이세요",
      ],
      reasoning:
        "캡션 첫 줄이 125자 이내 기준에서 후킹력이 부족합니다. 인스타그램 '더 보기' 버튼 전에 보이는 구간 최적화가 필요합니다.",
      debate_comments: [],
    },
    {
      agent_name: "비주얼 진단가",
      dimension: "시각 완성도",
      score: 55,
      issues: [
        "썸네일 색채 채도가 낮아 피드에서 눈에 띄지 않습니다",
        "썸네일에 텍스트 오버레이가 없어 정보 전달이 부족합니다",
      ],
      suggestions: [
        "채도를 0.6 이상으로 높여 보세요",
        "썸네일에 핵심 키워드 텍스트를 20~30% 영역에 추가하세요",
      ],
      reasoning:
        "썸네일 채도 0.35, 카테고리 평균 0.55보다 낮습니다. 바이럴 게시물의 썸네일 스타일을 참고하세요.",
      debate_comments: [],
    },
    {
      agent_name: "성장 전략가",
      dimension: "성장 전략",
      score: 58,
      issues: [
        "해시태그가 3개로 카테고리 최적 기준(5~7개)보다 부족합니다",
        "인기 해시태그를 하나도 사용하지 않았습니다",
      ],
      suggestions: [
        "해시태그를 5~7개로 늘리고 대형·중형·니치 태그를 믹스하세요",
        "18:00~21:00 사이에 게시하면 이 카테고리 참여율이 가장 높습니다",
      ],
      reasoning:
        "해시태그 커버리지 0%, Top10 인기 태그 미포함. 관련 카테고리 태그 추가가 필요합니다.",
      debate_comments: [],
    },
    {
      agent_name: "오디언스 시뮬레이터",
      dimension: "오디언스 반응",
      score: 65,
      issues: [
        "캡션 톤이 너무 평범해 스크롤 중 유저가 그냥 지나칠 수 있습니다",
        "참여 유도 문구(CTA)가 없습니다",
      ],
      suggestions: [
        "캡션 마지막에 「여러분은 어떻게 생각하세요? 댓글로 알려주세요👇」 같은 CTA를 추가하세요",
        "개인 경험과 진솔한 감상을 더해 공감대를 높이세요",
      ],
      reasoning: "오디언스 시뮬레이션: 핵심 팔로워는 클릭하지만 참여율이 낮을 가능성 높음. 스크롤 중 유저는 대부분 지나칩니다.",
      debate_comments: [],
    },
  ],
  issues: [
    {
      severity: "high",
      description: "해시태그 전략이 매우 부족하며 인기 태그 커버리지가 0%입니다",
      from_agent: "성장 전략가",
    },
    {
      severity: "high",
      description: "썸네일 시각 흡인력이 카테고리 평균 이하입니다",
      from_agent: "비주얼 진단가",
    },
    {
      severity: "medium",
      description: "캡션 첫 줄에 후킹 문구와 숫자가 없어 클릭률이 낮을 수 있습니다",
      from_agent: "캡션 분석가",
    },
  ],
  suggestions: [
    {
      priority: 1,
      description: "해시태그를 5~7개로 늘리고, 카테고리 인기 태그 3개 이상 포함하세요",
      expected_impact: "예상 노출량 30~50% 향상",
    },
    {
      priority: 2,
      description: "썸네일을 재디자인해 채도를 높이고 텍스트 타이틀을 추가하세요",
      expected_impact: "예상 클릭률 20~40% 향상",
    },
    {
      priority: 3,
      description: "캡션 첫 줄을 최적화해 숫자와 감성 키워드를 추가하세요",
      expected_impact: "예상 클릭률 15~25% 향상",
    },
  ],
  debate_summary:
    "4명의 전문가 에이전트가 해시태그 전략 부족을 가장 큰 문제로 꼽았습니다. 캡션 분석가와 오디언스 시뮬레이터 사이에 캡션 후킹력에 대한 미묘한 의견 차이가 있었지만, 최종적으로 중간값으로 수렴했습니다.",
  simulated_comments: [
    {
      username: "맛집탐방러",
      avatar_emoji: "🍽️",
      comment: "분위기 좋아 보여요! 여기 어디예요?",
      sentiment: "positive",
    },
    {
      username: "일상기록중",
      avatar_emoji: "📸",
      comment: "사진 더 선명하게 찍으면 훨씬 좋겠어요",
      sentiment: "neutral",
    },
    {
      username: "저장요정",
      avatar_emoji: "🔖",
      comment: "저장해둘게요! 나중에 가봐야겠다",
      sentiment: "positive",
    },
    {
      username: "솔직한리뷰어",
      avatar_emoji: "🤔",
      comment: "캡션이 좀 더 구체적이면 좋겠어요",
      sentiment: "neutral",
    },
    {
      username: "인스타탐색중",
      avatar_emoji: "🌿",
      comment: "정보 감사합니다! 도움이 됐어요",
      sentiment: "positive",
    },
  ],
  optimized_title: "5분이면 완성! 실패 없는 초간단 레시피 🔥 | 초보도 OK",
  optimized_content:
    "오늘 엄청 간단한 레시피 공유할게요!\n\n✅ 재료 준비 (5분)\n달걀, 밥, 간장, 파 — 냉장고에 항상 있는 재료면 충분해요.\n\n✅ 만드는 법 (10분)\n1. 묵은 밥 풀어서 준비\n2. 달걀 풀고 소금 약간\n3. 달군 팬에 기름 두르고 달걀 먼저 볶기\n4. 밥 넣고 간장으로 색 내기, 센 불에 볶기\n5. 파 올리면 완성!\n\n✅ 꿀팁\n밥은 꼭 묵은 밥 써야 알알이 살아있어요!\n\n여러분이 제일 좋아하는 간단 요리는 뭐예요? 댓글로 알려주세요👇",
  cover_direction: {
    layout: "텍스트 위 + 음식 아래 배치, 주 피사체가 화면의 60% 이상 차지",
    color_scheme: "따뜻한 색조(주황/노랑) 위주, 채도 0.6 이상",
    text_style: "썸네일 대문자로 「5분 완성」, 부제목 「실패 없는 레시피」",
    tips: [
      "음식 클로즈업이 전경보다 더 눈길을 끌어요",
      "젓가락이나 손을 추가해 생동감을 더하세요",
      "과도한 필터는 음식 색감을 왜곡할 수 있으니 주의하세요",
    ],
  },
  debate_timeline: [
    {
      round: 2,
      agent_name: "캡션 분석가",
      kind: "agree" as const,
      text: "성장 전략가의 해시태그 부족 판단에 동의합니다. 해시태그 커버리지 0%는 가장 큰 약점입니다.",
    },
    {
      round: 2,
      agent_name: "비주얼 진단가",
      kind: "rebuttal" as const,
      text: "오디언스 시뮬레이터의 평가에 완전히 동의하지 않습니다. 캡션이 평범하더라도, 시각 썸네일이 약한 게 스크롤 이탈의 주요 원인입니다.",
    },
    {
      round: 2,
      agent_name: "성장 전략가",
      kind: "add" as const,
      text: "간과된 문제를 추가합니다: 캡션 마지막에 참여 유도 문구가 없습니다. 「여러분은 어떻게 생각하세요?」 같은 CTA가 댓글률을 크게 높입니다.",
    },
    {
      round: 2,
      agent_name: "오디언스 시뮬레이터",
      kind: "agree" as const,
      text: "비주얼 진단가의 의견에 동의합니다. 피드에서 눈에 띄려면 더 선명한 색감의 썸네일이 필요합니다.",
    },
  ],
};
