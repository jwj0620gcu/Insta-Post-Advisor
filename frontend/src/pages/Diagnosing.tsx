import { useEffect, useState, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import axios from "axios";
import { Box, Typography, useTheme, useMediaQuery, Alert, Button } from "@mui/material";

import { preScore, diagnoseStream, diagnoseNote, DIAGNOSE_CLIENT_MAX_MS } from "../utils/api";
import type { PreScoreResult, StreamEvent } from "../utils/api";

/* ── 차원 레이블 ── */
const DIM_LABELS: Record<string, string> = {
  title_quality: "후킹력",
  content_quality: "콘텐츠",
  visual_quality: "시각",
  tag_strategy: "해시태그",
  engagement_potential: "전환력",
};

const DIM_COLORS: Record<string, string> = {
  title_quality: "#10b981",
  content_quality: "#4f5bd5",
  visual_quality: "#fa7e1e",
  tag_strategy: "#962fbf",
  engagement_potential: "#ff6b6b",
};

/* ── 진단 단계 ── */
const STEPS = [
  { label: "데이터 사전 평가", desc: "실제 인스타 데이터 기반 트래픽 예측 모델" },
  { label: "게시물 내용 파싱", desc: "캡션, 해시태그, 포맷 정보 추출" },
  { label: "커버/썸네일 시각 분석", desc: "구도, 색감, 텍스트 가독성 평가" },
  { label: "카테고리 벤치마크 비교", desc: "동일 카테고리 기준 데이터와 비교" },
  { label: "후킹 전문가 진단", desc: "스크롤 저지력, 첫 문장 후킹력, CTA 분석" },
  { label: "비주얼 진단가 진단", desc: "커버 시각 완성도 및 첫인상 분석" },
  { label: "트렌드 에이전트 진단", desc: "지금 바이럴되는 포맷/패턴과의 트렌드 적합성" },
  { label: "인스타 중독 유저 반응", desc: "하루 3시간+ 인스타 유저의 날카로운 피드백 & 댓글" },
  { label: "전문가 토론", desc: "4명 전문가 상호 검토 및 반박" },
  { label: "종합 심사관 평가", desc: "의견 통합, 최종 진단 도출" },
  { label: "진단 보고서 생성", desc: "점수, 개선안, 최적화 방안 정리" },
];

const EVENT_STEP_MAP: Record<string, number> = {
  parse_start: 1,
  parse_done: 2,
  baseline_start: 3,
  baseline_done: 3,
  round1_start: 4,
  round1_content_done: 4,
  round1_visual_done: 5,
  round1_growth_done: 6,
  round1_user_done: 7,
  round1_done: 8,
  debate_start: 8,
  debate_agent_0: 8,
  debate_agent_1: 8,
  debate_agent_2: 8,
  debate_agent_3: 9,
  debate_done: 9,
  judge_start: 9,
  judge_done: 10,
  finalizing: 10,
};

/* ── 카테고리별 인스타그램 인사이트 팁 ── */
const TIPS: Record<string, string[]> = {
  food: [
    "음식 카테고리에서 캐러셀은 싱글 이미지 대비 평균 22% 더 높은 저장률을 기록합니다",
    "맛집 게시물의 평균 캡션 길이는 150-300자가 가장 높은 인게이지먼트를 보입니다",
    "위치 태그를 추가하면 음식 게시물의 도달 범위가 평균 30% 증가합니다",
    "음식 사진은 따뜻한 색조(노랑/주황 계열)가 차가운 색조보다 저장 유도에 효과적입니다",
    "해시태그 5-7개가 음식 카테고리 최적 — 너무 많으면 스팸으로 분류될 수 있습니다",
  ],
  fashion: [
    "패션 카테고리의 인게이지먼트 차이 중 시각 요소가 압도적 비중을 차지합니다",
    "OOTD 게시물은 첫 이미지에서 전신을 보여주는 것이 클릭률에 유리합니다",
    "패션 캐러셀의 마지막 슬라이드에 '저장해두세요' CTA를 넣으면 저장률이 높아집니다",
    "배경이 깔끔할수록 의류에 시선이 집중되어 인게이지먼트가 높습니다",
    "릴스 형태의 OOTD는 싱글 이미지 대비 3-5배 더 많은 도달 범위를 가집니다",
  ],
  fitness: [
    "운동 루틴 캐러셀은 저장률이 가장 높은 포맷입니다 — '나중에 따라 해보기' 심리 자극",
    "비포/애프터 구성은 팔로우 전환율을 높이는 강력한 포맷입니다",
    "운동 릴스에서 첫 3초 이내에 결과물(Before/After 또는 최종 동작)을 보여주세요",
    "캡션에 운동 횟수/세트 수/시간 등 구체적 수치를 포함하면 저장률이 높아집니다",
    "헬스/운동 해시태그는 대형 1개 + 중형 2개 + 니치 2개 믹스가 효과적입니다",
  ],
  business: [
    "소상공인 계정은 게시물에 명확한 CTA(링크 바이오, DM, 전화)를 포함하세요",
    "제품/서비스 소개 캐러셀은 '문제 → 해결책 → 증거 → CTA' 순서가 효과적입니다",
    "비즈니스 계정은 인사이트 분석으로 팔로워 활성 시간을 확인하고 그 시간에 게시하세요",
    "고객 후기/리뷰를 스크린샷으로 공유하면 신뢰도가 높아져 문의 전환율이 상승합니다",
    "스토리와 피드를 연계하는 전략이 팔로워 유지율에 효과적입니다",
  ],
  lifestyle: [
    "일상 카테고리에서 캐러셀의 평균 인게이지먼트(ER 2.17)가 릴스(0.57)보다 훨씬 높습니다",
    "공감을 유도하는 첫 줄('저만 그런가요?', '이거 진짜 꿀템') 이 저장을 유도합니다",
    "일상 릴스는 15-30초 길이에서 완료 시청률이 가장 높습니다",
    "육아/일상 콘텐츠는 진정성이 핵심 — 완벽한 연출보다 자연스러운 순간이 공감을 삽니다",
    "릴스 배경 음악은 트렌딩 오디오를 사용하면 발견 가능성이 높아집니다",
  ],
  travel: [
    "여행 카테고리의 캐러셀 스와이프율은 66.5%로 전체 카테고리 중 가장 높습니다",
    "여행지 이름을 위치 태그로 추가하면 해당 지역 탐색자에게 노출됩니다",
    "여행 캡션에 '가는 법', '비용', '추천 시즌' 등 실용 정보를 포함하면 저장률이 높아집니다",
    "여행 캐러셀은 8-10장으로 '이런 여행이었다' 스토리를 완성하는 것이 효과적입니다",
    "인기 여행지는 경쟁이 치열하므로 니치 해시태그 위주로 구성하세요",
  ],
  education: [
    "정보/교육 카테고리는 캡션이 길수록 (중앙값 430자) 저장률이 높습니다",
    "캐러셀 형태의 '꿀팁 N가지' 포맷은 저장을 유도하는 가장 강력한 구성입니다",
    "첫 슬라이드에 '저장 필수' 문구나 자석 구성을 배치하면 저장률이 올라갑니다",
    "교육 콘텐츠는 릴스보다 캐러셀의 완독률이 높습니다 — 정보 밀도 차이",
    "마지막 슬라이드에 '팔로우하면 더 많은 팁을 볼 수 있습니다' CTA를 추가하세요",
  ],
  shop: [
    "쇼핑/리뷰 카테고리는 제품 사용 전후(비포/애프터)가 가장 강력한 포맷입니다",
    "가격 정보를 캡션에 명시하면 댓글 문의가 줄고 직접 전환이 높아집니다",
    "언박싱 릴스는 제품 리뷰 중 가장 높은 도달 범위를 기록합니다",
    "제품 캐러셀 마지막 장에 '구매 링크 바이오에' CTA를 반드시 포함하세요",
    "솔직한 장단점 리뷰는 신뢰도를 높여 팔로워 전환율을 2배 이상 높입니다",
  ],
  _default: [
    "캐러셀 포맷의 평균 인게이지먼트(1.92%)는 싱글 이미지(0.40%)보다 약 5배 높습니다",
    "릴스 첫 3초 리텐션이 60% 이상이면 도달 범위가 5-10배 높아집니다",
    "인스타그램 2026 알고리즘은 저장 수와 DM 공유를 최우선 신호로 사용합니다",
    "해시태그는 3-5개(릴스), 5-7개(피드)가 현재 최적입니다",
    "게시물의 94%는 AI 추천으로 배포됩니다 — 탐색 탭과 릴스 피드가 핵심 채널입니다",
  ],
};

/* ── 인스타 통계 퀴즈 ── */
const FUN_FACTS = [
  { q: "캐러셀과 싱글 이미지, 평균 인게이지먼트 차이는?", a: "캐러셀 1.92% vs 싱글 0.40% — 약 5배 차이입니다!" },
  { q: "릴스 첫 3초 리텐션이 60% 이상이면?", a: "도달 범위가 5-10배 높아집니다! 첫 3초가 가장 중요합니다" },
  { q: "인스타 2026 알고리즘의 #1 랭킹 신호는?", a: "시청 시간(Watch Time)입니다 — DM 공유, 저장이 그 다음입니다" },
  { q: "해시태그 몇 개가 2026년 기준 최적일까요?", a: "릴스는 3-5개, 피드 포스트는 5-7개가 최적입니다" },
  { q: "인스타 게시물의 94%는 어떻게 배포될까요?", a: "팔로워가 아닌 AI 추천 피드로 배포됩니다!" },
  { q: "자막 없는 릴스 vs 자막 있는 릴스, 차이는?", a: "자막이 있으면 완료 시청률이 40% 이상 높아집니다 — 무음 시청 때문입니다" },
  { q: "카페/맛집 게시물에서 캐러셀을 쓰면?", a: "싱글 이미지 대비 저장률이 평균 22% 높아집니다" },
  { q: "릴스 최적 길이는?", a: "카테고리마다 다르지만, 15-30초가 완료 시청률 기준 최적입니다" },
];

/* ── Score ring component ── */
function ScoreRing({ score, size = 80 }: { score: number; size?: number }) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const pct = score / 100;
  const color = score >= 85 ? "#10b981" : score >= 70 ? "#fa7e1e" : "#ff6b6b";
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(214,41,118,0.12)" strokeWidth={6} />
      <motion.circle
        cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={6}
        strokeLinecap="round" strokeDasharray={c}
        initial={{ strokeDashoffset: c }}
        animate={{ strokeDashoffset: c * (1 - pct) }}
        transition={{ duration: 1.2, ease: "easeOut" }}
      />
      <text
        x={size / 2} y={size / 2 + 1}
        textAnchor="middle" dominantBaseline="middle"
        fill={color} fontSize={size * 0.28} fontWeight="800"
        style={{ transform: "rotate(90deg)", transformOrigin: "center" }}
      >
        {Math.round(score)}
      </text>
    </svg>
  );
}

export default function Diagnosing() {
  const location = useLocation();
  const navigate = useNavigate();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const params = location.state as {
    title: string;
    content: string;
    tags: string;
    category: string;
    coverFile: File | null;
    coverImages?: File[];
    videoFile?: File | null;
  } | null;

  const [step, setStep] = useState(0);
  const [tipIdx, setTipIdx] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [factIdx, setFactIdx] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [preScoreData, setPreScoreData] = useState<PreScoreResult | null>(null);
  const [streamMsg, setStreamMsg] = useState<string>("");
  const [debateMsgs, setDebateMsgs] = useState<string[]>([]);
  const apiDone = useRef(false);
  const hasRealtimeProgress = useRef(false);
  const resultRef = useRef<{ report: unknown; isFallback: boolean } | null>(null);
  const lastSseActivityRef = useRef<number>(Date.now());
  const stallTriggeredRef = useRef(false);
  const [terminalError, setTerminalError] = useState<string | null>(null);

  const tips = (params ? TIPS[params.category] : null) || TIPS._default;

  useEffect(() => {
    document.title = "진단 중... - Insta-Advisor";
    if (!params) { navigate("/app"); return; }
    let cancelled = false;
    const abortController = new AbortController();

    // Phase 1: 즉시 사전 평가
    preScore({
      title: params.title, content: params.content,
      category: params.category, tags: params.tags,
      image_count: params.coverImages?.length ?? (params.coverFile ? 1 : 0),
    }).then((ps) => {
      if (!cancelled) {
        setPreScoreData(ps);
        setStep(1);
      }
    }).catch(() => {});

    let streamEndedWithServerError = false;

    const touchSse = () => {
      lastSseActivityRef.current = Date.now();
    };

    // Phase 2: SSE 스트리밍 진단 (폴백: 일반 POST)
    (async () => {
      try {
        await diagnoseStream(
          {
            title: params.title, content: params.content,
            category: params.category, tags: params.tags,
            coverImage: params.coverFile ?? undefined,
            coverImages: params.coverImages ?? undefined,
            videoFile: params.videoFile ?? undefined,
          },
          (event: StreamEvent) => {
            if (cancelled) return;
            touchSse();
            if (event.type === "pre_score") {
              setPreScoreData(event.data as unknown as PreScoreResult);
              setStep(1);
            } else if (event.type === "progress") {
              hasRealtimeProgress.current = true;
              setStreamMsg(event.data.message);
              const mapped = EVENT_STEP_MAP[event.data.step];
              if (mapped !== undefined) {
                setStep((prev) => Math.max(prev, mapped));
              }
              if (event.data.step?.startsWith("debate_agent_")) {
                setDebateMsgs((prev) => [...prev, event.data.message]);
              }
            } else if (event.type === "result") {
              resultRef.current = { report: event.data, isFallback: false };
              apiDone.current = true;
            } else if (event.type === "error") {
              streamEndedWithServerError = true;
              const msg =
                typeof event.data?.message === "string"
                  ? event.data.message
                  : "서버 진단 중 오류가 발생했습니다";
              setTerminalError(msg);
              apiDone.current = true;
            }
          },
          abortController.signal,
        );
        if (streamEndedWithServerError) {
          return;
        }
        if (!resultRef.current) {
          const result = await diagnoseNote({
            title: params.title, content: params.content,
            category: params.category, tags: params.tags,
            coverImage: params.coverFile ?? undefined,
            coverImages: params.coverImages ?? undefined,
            videoFile: params.videoFile ?? undefined,
          });
          resultRef.current = { report: result, isFallback: false };
        }
      } catch (err) {
        console.warn("SSE 불가, 일반 요청으로 폴백", err);
        try {
          const result = await diagnoseNote({
            title: params.title, content: params.content,
            category: params.category, tags: params.tags,
            coverImage: params.coverFile ?? undefined,
            coverImages: params.coverImages ?? undefined,
            videoFile: params.videoFile ?? undefined,
          });
          resultRef.current = { report: result, isFallback: false };
        } catch (e2: unknown) {
          let msg = "진단 요청 실패. 네트워크와 백엔드 실행 여부를 확인하세요";
          if (axios.isAxiosError(e2)) {
            const d = e2.response?.data;
            if (d && typeof d === "object" && "detail" in d) {
              const det = (d as { detail: unknown }).detail;
              msg = typeof det === "string" ? det : JSON.stringify(det);
            } else if (e2.message) {
              msg = e2.message;
            }
          } else if (e2 instanceof Error && e2.message) {
            msg = e2.message;
          }
          setTerminalError(msg);
        }
      }
      apiDone.current = true;
    })();

    // 단계 타이머 (실제 이벤트 간 공백 채우기)
    const stepTimer = setInterval(() => {
      setStep((prev) => {
        if (apiDone.current && prev >= STEPS.length - 2) {
          clearInterval(stepTimer);
          setTimeout(() => {
            if (!cancelled && resultRef.current)
              navigate("/report", { state: { report: resultRef.current.report, params, isFallback: resultRef.current.isFallback } });
          }, 600);
          return STEPS.length - 1;
        }
        if (hasRealtimeProgress.current) return prev;
        if (prev >= STEPS.length - 1) return prev;
        if (!apiDone.current && prev >= STEPS.length - 2) return prev;
        return prev + 1;
      });
    }, 3500);

    const tipTimer = setInterval(() => setTipIdx((p) => (p + 1) % tips.length), 4500);
    const clockTimer = setInterval(() => setElapsed((p) => p + 1), 1000);
    const factTimer = setInterval(() => { setFactIdx((p) => (p + 1) % FUN_FACTS.length); setShowAnswer(false); }, 8000);

    // 전체 최장 대기 타임아웃
    const timeoutTimer = setTimeout(() => {
      if (!apiDone.current && !cancelled) {
        setTerminalError(
          `진단이 ${DIAGNOSE_CLIENT_MAX_MS / 1000}초를 초과했습니다. frontend/.env에서 VITE_DIAGNOSE_MAX_WAIT_MS를 늘리거나, 백엔드/모델 상태를 확인하세요.`,
        );
        apiDone.current = true;
      }
    }, DIAGNOSE_CLIENT_MAX_MS);

    // SSE 장기 무응답 감지 (기본 120초)
    const stallCheckMs = 120_000;
    const stallIv = setInterval(() => {
      if (cancelled || apiDone.current || stallTriggeredRef.current) return;
      if (Date.now() - lastSseActivityRef.current > stallCheckMs) {
        stallTriggeredRef.current = true;
        setTerminalError(
          "진단 스트림이 오랫동안 응답하지 않습니다. 백엔드 로그를 확인하거나 잠시 후 다시 시도하세요.",
        );
        apiDone.current = true;
      }
    }, 10_000);

    return () => {
      cancelled = true;
      abortController.abort();
      clearInterval(stepTimer);
      clearInterval(tipTimer);
      clearInterval(clockTimer);
      clearInterval(factTimer);
      clearInterval(stallIv);
      clearTimeout(timeoutTimer);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!params) return null;

  if (terminalError) {
    return (
      <Box
        sx={{
          minHeight: "100vh",
          bgcolor: "#fff8f8",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          px: 2,
          gap: 2,
        }}
      >
        <Alert severity="error" sx={{ maxWidth: 440, width: "100%", borderRadius: "12px" }}>
          {terminalError}
        </Alert>
        <Button
          variant="contained"
          onClick={() => navigate("/app", { replace: true })}
          sx={{
            bgcolor: "#d62976",
            textTransform: "none",
            fontWeight: 700,
            px: 3,
            borderRadius: "10px",
            "&:hover": { bgcolor: "#c21766" },
          }}
        >
          홈으로 돌아가기
        </Button>
      </Box>
    );
  }

  const progress = ((step + 1) / STEPS.length) * 100;

  return (
    <Box sx={{ position: "fixed", inset: 0, bgcolor: "#fff8f8", display: "flex", flexDirection: "column" }}>

      {/* ═══ Top bar ═══ */}
      <Box sx={{
        flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "space-between",
        px: { xs: 1.5, md: 3 }, height: 48,
        borderBottom: "1px solid rgba(214,41,118,0.12)",
      }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 0, flex: 1 }}>
          <motion.div
            animate={{ opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            style={{ flexShrink: 0, display: "flex" }}
          >
            <Box sx={{ width: 7, height: 7, borderRadius: "50%", bgcolor: "#d62976" }} />
          </motion.div>
          <Typography sx={{ fontSize: 13, fontWeight: 600, color: "#1a1a1a", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {params.title || "진단 중"}
          </Typography>
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, flexShrink: 0, ml: 1.5 }}>
          <Typography sx={{ fontSize: 12, color: "#b6a4ba", display: { xs: "none", sm: "block" } }}>
            {streamMsg || "예상 30-60초"}
          </Typography>
          <Typography sx={{ fontSize: 13, fontWeight: 700, color: "#555", fontVariantNumeric: "tabular-nums", bgcolor: "rgba(214,41,118,0.08)", px: 1, py: 0.25, borderRadius: "6px" }}>
            {elapsed}s
          </Typography>
        </Box>
      </Box>

      {/* ═══ Content ═══ */}
      <Box sx={{ flex: 1, overflow: "auto", display: "flex", justifyContent: "center" }}>
        <Box sx={{
          width: "100%", maxWidth: 960,
          display: "grid",
          gridTemplateColumns: { xs: "1fr", md: "300px 1fr" },
          gap: { xs: 2.5, md: 4 },
          px: { xs: 2, md: 3 },
          py: { xs: 2.5, md: 3.5 },
          alignContent: "start",
          alignItems: "start",
        }}>

          {/* ═══ Left: Score ═══ */}
          <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
            {preScoreData ? (
              <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5 }}
                style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}
              >
                <ScoreRing score={preScoreData.total_score} size={isDesktop ? 140 : 110} />
                <Box sx={{ textAlign: "center" }}>
                  <Typography sx={{ fontSize: 14, fontWeight: 700, color: "#1a1a1a", mb: 0.25,
                    maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {params.title || "제목 없음"}
                  </Typography>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, justifyContent: "center" }}>
                    <Typography sx={{ fontSize: 11, color: "#8f7b94" }}>
                      {preScoreData.category_cn}
                    </Typography>
                    <Box sx={{
                      px: 0.5, py: 0.1, borderRadius: "4px",
                      bgcolor: preScoreData.total_score >= 85 ? "#dcfce7" : preScoreData.total_score >= 70 ? "#fef3c7" : "#fee2e2",
                    }}>
                      <Typography sx={{
                        fontSize: 10, fontWeight: 700,
                        color: preScoreData.total_score >= 85 ? "#16a34a" : preScoreData.total_score >= 70 ? "#d97706" : "#dc2626",
                      }}>
                        {preScoreData.level}
                      </Typography>
                    </Box>
                  </Box>
                </Box>
              </motion.div>
            ) : (
              <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 1 }}>
                <motion.div animate={{ opacity: [0.3, 0.6, 0.3] }} transition={{ duration: 2, repeat: Infinity }}>
                  <Box sx={{
                    width: isDesktop ? 140 : 110, height: isDesktop ? 140 : 110,
                    borderRadius: "50%", border: "3px solid rgba(214,41,118,0.12)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <Typography sx={{ fontSize: 14, color: "#b6a4ba", fontWeight: 600 }}>평가 중</Typography>
                  </Box>
                </motion.div>
                <Typography sx={{ fontSize: 13, fontWeight: 600, color: "#8f7b94",
                  maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", textAlign: "center" }}>
                  {params.title || "분석 중..."}
                </Typography>
              </Box>
            )}

            {/* Dimension bars */}
            {preScoreData && (
              <Box sx={{ width: "100%", maxWidth: 280 }}>
                {Object.entries(preScoreData.dimensions).map(([key, val]) => (
                  <Box key={key} sx={{ display: "flex", alignItems: "center", gap: 0.75, mb: 0.6, "&:last-child": { mb: 0 } }}>
                    <Typography sx={{ fontSize: 11, color: "#8f7b94", minWidth: 44, textAlign: "right" }}>
                      {DIM_LABELS[key] || key}
                    </Typography>
                    <Box sx={{ flex: 1, height: 5, bgcolor: "rgba(214,41,118,0.08)", borderRadius: 3, overflow: "hidden" }}>
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${val}%` }}
                        transition={{ duration: 1, ease: "easeOut", delay: 0.2 }}
                        style={{ height: "100%", borderRadius: 3, background: DIM_COLORS[key] || "#10b981" }}
                      />
                    </Box>
                    <Typography sx={{ fontSize: 11, fontWeight: 600, color: "#666", minWidth: 24, textAlign: "right" }}>
                      {Math.round(val)}
                    </Typography>
                  </Box>
                ))}
                <Typography sx={{ fontSize: 10, color: "#b6a4ba", mt: 1, textAlign: "center" }}>
                  실제 인스타 데이터 기반 모델
                </Typography>
              </Box>
            )}
          </Box>


          {/* ═══ Right: Step Timeline ═══ */}
          <Box sx={{ display: "flex", flexDirection: "column", gap: 0 }}>

            {/* Progress bar */}
            <Box sx={{ mb: 2 }}>
              <Box sx={{ height: 4, bgcolor: "rgba(214,41,118,0.12)", borderRadius: 2, overflow: "hidden" }}>
                <Box sx={{
                  height: "100%", borderRadius: 2, bgcolor: "#d62976",
                  width: `${progress}%`,
                  transition: "width 0.5s ease",
                }} />
              </Box>
              <Box sx={{ display: "flex", justifyContent: "space-between", mt: 0.5 }}>
                <Typography sx={{ fontSize: 11, color: "#8f7b94" }}>{step + 1}/{STEPS.length}</Typography>
                <Typography sx={{ fontSize: 11, color: "#b6a4ba" }}>{elapsed}s</Typography>
              </Box>
            </Box>

            {/* Vertical step timeline */}
            {STEPS.map((s, i) => {
              const isDone = i < step;
              const isActive = i === step;
              const isDebatePhase = i === 8;
              const isJudgePhase = i === 9;

              return (
                <Box key={i} sx={{ display: "flex", gap: 1.5, pb: i < STEPS.length - 1 ? 0 : 0 }}>
                  <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", width: 20, flexShrink: 0 }}>
                    <Box sx={{
                      width: isDone ? 16 : isActive ? 18 : 12,
                      height: isDone ? 16 : isActive ? 18 : 12,
                      borderRadius: "50%",
                      bgcolor: isDone ? "#10b981" : isActive ? "#d62976" : "#e8e8e8",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      transition: "all 0.3s",
                      boxShadow: isActive ? "0 0 8px rgba(255,36,66,0.3)" : "none",
                    }}>
                      {isDone && (
                        <svg width="10" height="10" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
                      )}
                      {isActive && (
                        <Box sx={{ width: 6, height: 6, borderRadius: "50%", bgcolor: "#fff" }} />
                      )}
                    </Box>
                    {i < STEPS.length - 1 && (
                      <Box sx={{
                        width: 2, flex: 1, minHeight: 16,
                        bgcolor: isDone ? "#10b981" : "rgba(214,41,118,0.12)",
                        transition: "background-color 0.3s",
                      }} />
                    )}
                  </Box>

                  <Box sx={{ flex: 1, minWidth: 0, pb: 1.5 }}>
                    <Typography sx={{
                      fontSize: isActive ? 14 : 13,
                      fontWeight: isActive ? 700 : isDone ? 500 : 400,
                      color: isDone ? "#10b981" : isActive ? "#1a1a1a" : "#b6a4ba",
                      lineHeight: 1.3,
                      transition: "all 0.3s",
                    }}>
                      {s.label}
                    </Typography>
                    {isActive && (
                      <Typography sx={{ fontSize: 11, color: "#8f7b94", mt: 0.25 }}>
                        {s.desc}
                      </Typography>
                    )}

                    {/* 토론 단계: 실시간 메시지 표시 */}
                    {isDebatePhase && (isDone || isActive) && debateMsgs.length > 0 && (
                      <Box sx={{ mt: 1, display: "flex", flexDirection: "column", gap: 0.75 }}>
                        {debateMsgs.map((msg, j) => {
                          const colors = ["#d62976", "#962fbf", "#fa7e1e", "#4f5bd5"];
                          const bgColors = ["#fff5f6", "#faf5ff", "#fffbeb", "#eff6ff"];
                          return (
                            <Box key={j} sx={{
                              px: 1.25, py: 0.75, borderRadius: "8px",
                              bgcolor: bgColors[j % 4],
                              borderLeft: `2px solid ${colors[j % 4]}`,
                            }}>
                              <Typography sx={{ fontSize: 11, color: "#444", lineHeight: 1.5 }}>
                                {msg}
                              </Typography>
                            </Box>
                          );
                        })}
                      </Box>
                    )}

                    {/* 종합 심사 단계: 진행 상태 표시 */}
                    {isJudgePhase && isActive && (
                      <Box sx={{ mt: 0.5, display: "flex", alignItems: "center", gap: 0.5 }}>
                        <motion.div animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 1.5, repeat: Infinity }}>
                          <Box sx={{ width: 5, height: 5, borderRadius: "50%", bgcolor: "#10b981" }} />
                        </motion.div>
                        <Typography sx={{ fontSize: 11, color: "#10b981" }}>
                          종합 심사관이 최종 보고서를 작성 중...
                        </Typography>
                      </Box>
                    )}
                  </Box>
                </Box>
              );
            })}

            {/* 인스타 인사이트 팁 */}
            <Box sx={{ mt: 2, pt: 2, borderTop: "1px solid rgba(214,41,118,0.12)" }}>
              <Typography sx={{ fontSize: 10, fontWeight: 600, color: "#10b981", mb: 0.5, letterSpacing: "0.04em" }}>
                인스타그램 인사이트
              </Typography>
              <AnimatePresence mode="wait">
                <motion.div key={tipIdx} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
                  <Typography sx={{ fontSize: 12, color: "#666", lineHeight: 1.6 }}>
                    {tips[tipIdx]}
                  </Typography>
                </motion.div>
              </AnimatePresence>
            </Box>

            {/* 인스타 통계 퀴즈 */}
            <Box
              onClick={() => setShowAnswer(true)}
              sx={{
                mt: 1.5, p: 1.5, borderRadius: "10px", cursor: "pointer",
                bgcolor: showAnswer ? "#fff5f6" : "#f9f9f9",
                border: showAnswer ? "1px solid #fecaca" : "1px solid transparent",
                transition: "all 0.3s",
              }}
            >
              <Typography sx={{ fontSize: 10, fontWeight: 700, color: showAnswer ? "#d62976" : "#b6a4ba", mb: 0.25 }}>
                {showAnswer ? "정답" : "인스타 퀴즈"}
              </Typography>
              <AnimatePresence mode="wait">
                <motion.div key={`${factIdx}-${showAnswer}`}
                  initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.2 }}>
                  <Typography sx={{ fontSize: 13, fontWeight: showAnswer ? 700 : 500,
                    color: showAnswer ? "#d62976" : "#1a1a1a", lineHeight: 1.5 }}>
                    {showAnswer ? FUN_FACTS[factIdx].a : FUN_FACTS[factIdx].q}
                  </Typography>
                </motion.div>
              </AnimatePresence>
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
