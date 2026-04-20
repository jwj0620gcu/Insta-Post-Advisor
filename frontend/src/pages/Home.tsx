import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Box, Typography, TextField, Button, Chip,
  CircularProgress, useTheme,
  useMediaQuery, Alert,
} from "@mui/material";
import HistoryOutlined from "@mui/icons-material/HistoryOutlined";
import EmailOutlinedIcon from "@mui/icons-material/EmailOutlined";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CategoryPicker from "../components/CategoryPicker";
import UploadZone from "../components/UploadZone";
import { quickRecognize, quickRecognizeVideo, getApiHealth } from "../utils/api";
import type { QuickRecognizeResult } from "../utils/api";

/** @returns A stable key for a File object */
function fkey(f: File) {
  return `${f.name}_${f.size}_${f.lastModified}`;
}

function hasHangul(text: string): boolean {
  return /[가-힣]/.test(text);
}

/** 카테고리 라벨 -> 내부 key 매핑 */
const CAT_MAP: Record<string, string> = {
  // Korean
  "맛집": "food", "카페": "food", "맛집/카페": "food", "음식": "food",
  "패션": "fashion", "뷰티": "fashion", "패션/뷰티": "fashion", "코디": "fashion",
  "운동": "fitness", "헬스": "fitness", "운동/건강": "fitness", "건강": "fitness",
  "사업": "business", "마케팅": "business", "사업/마케팅": "business",
  "일상": "lifestyle", "브이로그": "lifestyle",
  "여행": "travel", "trip": "travel",
  "정보": "education", "교육": "education", "정보/교육": "education",
  "쇼핑": "shop", "리뷰": "shop", "쇼핑/리뷰": "shop",

  // English keys pass through
  "food": "food",
  "fashion": "fashion",
  "fitness": "fitness",
  "business": "business",
  "lifestyle": "lifestyle",
  "travel": "travel",
  "education": "education",
  "shop": "shop",
  "tech": "tech",
  "beauty": "beauty",
  "home": "home",
};

/** 병렬 이미지 분석 동시 실행 수 */
const QUICK_RECOGNIZE_CONCURRENCY = 10;

/** AI 분석 중 순환 문구 */
const ANALYSIS_MESSAGES = [
  "인스타 게시물 내용을 분석하는 중...",
  "카테고리 트렌드 모델을 호출하는 중...",
  "커버/썸네일 시각 요소를 인식하는 중...",
  "캡션과 해시태그를 추출하는 중...",
  "동일 카테고리 데이터와 비교하는 중...",
  "인게이지먼트 잠재력을 평가하는 중...",
];

/** 부드러운 진행바: 90%까지 선형 증가, 파일 1건 완료 시 실제 진행률 반영, 마지막 100% */
function SmoothProgressBar({ done, total }: { done: number; total: number }) {
  const [smooth, setSmooth] = useState(0);
  const realPct = total === 0 ? 0 : (done / total) * 100;
  const targetRef = useRef(realPct);
  targetRef.current = realPct;

  useEffect(() => {
    // Tick every 200ms, creep toward 90% slowly, jump to real when real > smooth
    const timer = setInterval(() => {
      setSmooth((prev) => {
        const target = targetRef.current;
        if (target >= 100) return 100;
        if (target > prev) return target; // real progress jumped ahead, snap to it
        if (prev >= 90) return prev; // cap fake progress at 90%
        return prev + 0.8; // creep ~4%/sec
      });
    }, 200);
    return () => clearInterval(timer);
  }, []);

  // Snap to 100 when all done
  useEffect(() => {
    if (realPct >= 100) setSmooth(100);
  }, [realPct]);

  return (
    <Box sx={{ height: 4, bgcolor: "rgba(214,41,118,0.12)", borderRadius: 2, overflow: "hidden" }}>
      <Box sx={{
        height: "100%", borderRadius: 2,
        background: "linear-gradient(90deg, #d62976, #ff6b81)",
        width: `${Math.min(smooth, 100)}%`,
        transition: "width 0.4s cubic-bezier(0.4,0,0.2,1)",
        position: "relative",
        "&::after": {
          content: '""', position: "absolute", inset: 0,
          background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent)",
          animation: "shimmer 1.5s infinite",
        },
      }} />
    </Box>
  );
}

function AnalysisStatusText() {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % ANALYSIS_MESSAGES.length), 3000);
    return () => clearInterval(t);
  }, []);
  return (
    <AnimatePresence mode="wait">
      <motion.div key={idx} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.2 }}>
        <Typography sx={{ fontSize: 11, color: "#8f7b94", fontWeight: 500 }}>
          {ANALYSIS_MESSAGES[idx]}
        </Typography>
      </motion.div>
    </AnimatePresence>
  );
}

/** 홈 화면: 데스크톱 2열, 모바일 단일 페이지 레이아웃 */
export default function Home() {
  const navigate = useNavigate();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));

  const [files, setFiles] = useState<File[]>([]);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("food");

  const [aiRecogs, setAiRecogs] = useState<Record<string, QuickRecognizeResult>>({});
  const [aiLoading, setAiLoading] = useState<Record<string, boolean>>({});
  const [uploadingPulse, setUploadingPulse] = useState(false);
  const [analyzingPulse, setAnalyzingPulse] = useState(false);

  const [userEdited, setUserEdited] = useState({ title: false, content: false, category: false });
  /** null=탐지 중, false=로컬 API 미도달(주로 서버 미기동 또는 Vite 프록시 포트 불일치) */
  const [apiReachable, setApiReachable] = useState<boolean | null>(null);

  const uploadPulseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const analyzePulseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recognizeInFlightRef = useRef<Set<string>>(new Set());
  const prevPendingRecognitionRef = useRef(false);

  useEffect(() => { document.title = "InstaRx"; }, []);

  useEffect(() => {
    void getApiHealth().then(setApiReachable);
  }, []);

  useEffect(() => {
    return () => {
      if (uploadPulseTimerRef.current) clearTimeout(uploadPulseTimerRef.current);
      if (analyzePulseTimerRef.current) clearTimeout(analyzePulseTimerRef.current);
    };
  }, []);

  const triggerUploadPulse = useCallback(() => {
    if (uploadPulseTimerRef.current) clearTimeout(uploadPulseTimerRef.current);
    setUploadingPulse(true);
    uploadPulseTimerRef.current = setTimeout(() => {
      setUploadingPulse(false);
      uploadPulseTimerRef.current = null;
    }, 500);
  }, []);

  const handleFilesChange = useCallback(
    (newFiles: File[]) => {
      setFiles(newFiles.slice(0, 9));
      if (newFiles.length > 0) triggerUploadPulse();
    },
    [triggerUploadPulse],
  );

  const appendFiles = useCallback(
    (incoming: File[]) => {
      if (incoming.length === 0) return;
      setFiles((prev) => [...prev, ...incoming].slice(0, 9));
      triggerUploadPulse();
    },
    [triggerUploadPulse],
  );

  /** Ctrl+V paste images */
  useEffect(() => {
    const handlePaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      const pasted: File[] = [];
      for (const item of items) {
        if (item.type.startsWith("image/") || item.type.startsWith("video/")) {
          const file = item.getAsFile();
          if (file) pasted.push(file);
        }
      }
      appendFiles(pasted);
    };
    window.addEventListener("paste", handlePaste);
    return () => window.removeEventListener("paste", handlePaste);
  }, [appendFiles]);

  const anyLoading = useMemo(() => Object.values(aiLoading).some(Boolean), [aiLoading]);
  const allResults = useMemo(() => Object.values(aiRecogs), [aiRecogs]);
  const successRecogEntries = useMemo(
    () => Object.entries(aiRecogs).filter(([, r]) => r.success),
    [aiRecogs],
  );
  const successResults = useMemo(
    () => successRecogEntries.map(([, r]) => r),
    [successRecogEntries],
  );

  const aggregated = useMemo(() => {
    let bestTitle = "";
    const contentParts: string[] = [];  // 여러 이미지에서 추출한 본문 병합용
    let bestCategory = "";
    let bestSummary = "";
    let engLikes = 0, engCollects = 0, engComments = 0;

    // Pass 1: content 타입 우선 처리 - 제목은 첫 값, 본문은 모두 병합
    for (const [, r] of successRecogEntries) {
      if ((r.slot_type || "").toLowerCase() === "content") {
        if (!bestTitle && r.title?.trim()) bestTitle = r.title.trim();
        if (r.content_text?.trim()) contentParts.push(r.content_text.trim());
      }
      if (!bestCategory && r.category?.trim()) bestCategory = r.category.trim();
      if (!bestSummary && r.summary?.trim()) bestSummary = r.summary.trim();
      // 참여 지표는 최대값 기준으로 반영
      const eng = r.engagement_signal;
      if (eng) {
        engLikes = Math.max(engLikes, eng.likes_visible || 0);
        engCollects = Math.max(engCollects, eng.collects_visible || 0);
        engComments = Math.max(engComments, eng.comments_visible || 0);
      }
    }

    // Pass 2: fallback - non-content 타입으로 누락값 보강
    if (!bestTitle) {
      for (const [, r] of successRecogEntries) {
        if (!bestTitle && r.title?.trim()) bestTitle = r.title.trim();
      }
    }
    if (contentParts.length === 0) {
      for (const [, r] of successRecogEntries) {
        if (r.content_text?.trim()) contentParts.push(r.content_text.trim());
      }
    }

    // 본문 병합(중복 제거: 두 조각이 50% 이상 겹치면 스킵)
    const mergedParts: string[] = [];
    for (const part of contentParts) {
      const isDuplicate = mergedParts.some((existing) => {
        const shorter = part.length < existing.length ? part : existing;
        return existing.includes(shorter.slice(0, 30)) || part.includes(existing.slice(0, 30));
      });
      if (!isDuplicate) mergedParts.push(part);
    }
    let bestContent = mergedParts.join("\n");

    /**
     * 커버 슬롯은 모델 특성상 title/content_text 없이 summary만 반환하는 경우가 잦다.
     * 이를 보정하지 않으면 카테고리 인식 완료 상태에서도 제목/본문이 비어 보일 수 있다.
     */
    /** 영상만 있을 때 summary는 장면 요약인 경우가 많아 제목으로 직접 사용하지 않는다. */
    const videoOnlySuccess =
      successRecogEntries.length > 0 &&
      successRecogEntries.every(([, r]) => r.success && r.media_source === "video");

    if (!bestTitle && bestSummary && !videoOnlySuccess && hasHangul(bestSummary)) {
      const s = bestSummary.replace(/\s+/g, " ").trim();
      if (s) {
        const firstPhrase = (s.split(/[。！？\n]/)[0] || s).trim();
        bestTitle = (firstPhrase || s).slice(0, 100);
      }
    }
    if (!bestContent.trim() && bestSummary.trim() && hasHangul(bestSummary)) {
      bestContent = bestSummary.trim();
    }

    return {
      bestTitle, bestContent, bestCategory, bestSummary,
      engagementData: { likes: engLikes, collects: engCollects, comments: engComments },
    };
  }, [successRecogEntries]);

  const imageFileKeys = useMemo(
    () => new Set(files.filter((f) => f.type.startsWith("image/")).map(fkey)),
    [files],
  );

  /** 빠른 인식 대상 비디오(UploadZone 정책과 동일하게 최대 1개) */
  const videoFileKeys = useMemo(
    () => new Set(files.filter((f) => f.type.startsWith("video/")).map(fkey)),
    [files],
  );

  /** 이미지/비디오 빠른 인식이 모두 끝난 뒤 폼 잠금 해제 */
  const recognizeFileKeys = useMemo(() => {
    const s = new Set<string>();
    imageFileKeys.forEach((k) => s.add(k));
    videoFileKeys.forEach((k) => s.add(k));
    return s;
  }, [imageFileKeys, videoFileKeys]);

  const pendingRecognition = useMemo(() => {
    if (recognizeFileKeys.size === 0) return false;
    for (const key of recognizeFileKeys) {
      if (aiLoading[key] || !aiRecogs[key]) return true;
    }
    return false;
  }, [recognizeFileKeys, aiLoading, aiRecogs]);

  const allRecognitionDone = useMemo(() => {
    if (recognizeFileKeys.size === 0) return true;
    for (const k of recognizeFileKeys) {
      if (!aiRecogs[k] && !aiLoading[k]) return false;
      if (aiLoading[k]) return false;
    }
    return true;
  }, [recognizeFileKeys, aiRecogs, aiLoading]);

  useEffect(() => {
    const { bestTitle, bestContent, bestCategory } = aggregated;

    if (!userEdited.title && bestTitle) {
      setTitle(bestTitle.slice(0, 100));
    }
    if (!userEdited.content && bestContent) {
      setContent(bestContent);
    }
    if (!userEdited.category && bestCategory) {
      const mapped = CAT_MAP[bestCategory];
      if (mapped) setCategory(mapped);
    }
  }, [aggregated, userEdited]);

  const allFailed = allRecognitionDone && successResults.length === 0 && allResults.length > 0;

  /** 전부 실패하면 첫 오류 원인을 노출해 API 연결 문제와 모델/키 오류를 구분한다. */
  const firstRecognizeError = useMemo(() => {
    for (const r of Object.values(aiRecogs)) {
      if (!r.success && r.error?.trim()) return r.error.trim();
    }
    return null;
  }, [aiRecogs]);

  const showWarnings = allRecognitionDone && files.length > 0 && !allFailed;
  const warnings = useMemo(() => {
    if (!showWarnings) return { title: false, content: false, category: false };
    const { bestTitle, bestContent, bestCategory, bestSummary } = aggregated;
    return {
      title: !bestTitle && !bestSummary,
      content: !bestContent,
      category: !bestCategory,
    };
  }, [showWarnings, aggregated]);

  const autoFilled = useMemo(() => {
    const { bestTitle, bestContent, bestCategory } = aggregated;
    return {
      /** 제목에 실제 반영 가능한 필드가 있을 때만 '자동 입력됨'으로 표시한다. */
      title: !userEdited.title && !!bestTitle,
      content: !userEdited.content && !!bestContent,
      category: !userEdited.category && !!bestCategory && !!CAT_MAP[bestCategory],
    };
  }, [aggregated, userEdited]);

  /** 비디오만 있고 스크린샷이 없으면 제목 정보가 영상 프레임에 없을 가능성이 높다. */
  const videoWithoutImage = videoFileKeys.size > 0 && imageFileKeys.size === 0;

  const runRecognition = useCallback(async (file: File, slotHint?: "cover" | "content" | "profile" | "comments") => {
    const key = fkey(file);
    if (recognizeInFlightRef.current.has(key)) return;
    recognizeInFlightRef.current.add(key);
    setAiLoading((p) => {
      if (p[key]) return p;
      return { ...p, [key]: true };
    });
    try {
      const res = file.type.startsWith("video/")
        ? await quickRecognizeVideo(file)
        : await quickRecognize(file, slotHint);
      const merged =
        !res.success && !res.error?.trim()
          ? {
              ...res,
              error: "분석 결과가 없습니다. OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL_OMNI 설정을 확인하세요",
            }
          : res;
      setAiRecogs((p) => ({ ...p, [key]: merged }));
    } catch {
      setAiRecogs((p) => ({
        ...p,
        [key]: {
          success: false,
          slot_type: "unknown",
          extra_slots: [],
          category: "",
          summary: "",
          error: "분석에 실패했습니다",
        },
      }));
    } finally {
      recognizeInFlightRef.current.delete(key);
      setAiLoading((p) => ({ ...p, [key]: false }));
    }
  }, []);

  useEffect(() => {
    const validKeys = new Set(files.map(fkey));
    setAiRecogs((prev) => {
      let changed = false;
      const next: Record<string, QuickRecognizeResult> = {};
      Object.entries(prev).forEach(([key, value]) => {
        if (validKeys.has(key)) next[key] = value;
        else changed = true;
      });
      return changed ? next : prev;
    });
    setAiLoading((prev) => {
      let changed = false;
      const next: Record<string, boolean> = {};
      Object.entries(prev).forEach(([key, value]) => {
        if (validKeys.has(key)) next[key] = value;
        else changed = true;
      });
      return changed ? next : prev;
    });
    recognizeInFlightRef.current.forEach((key) => {
      if (!validKeys.has(key)) recognizeInFlightRef.current.delete(key);
    });
  }, [files]);

  useEffect(() => {
    const mediaFiles = files.filter(
      (f) => f.type.startsWith("image/") || f.type.startsWith("video/"),
    );
    const inFlight = mediaFiles.filter((f) => aiLoading[fkey(f)]).length;
    const freeSlots = Math.max(0, QUICK_RECOGNIZE_CONCURRENCY - inFlight);
    const need = mediaFiles.filter((f) => {
      const k = fkey(f);
      return !aiRecogs[k] && !aiLoading[k];
    });
    need.slice(0, freeSlots).forEach((file) => {
      const hint = file.type.startsWith("image/") ? "content" : undefined;
      void runRecognition(file, hint);
    });
  }, [files, aiRecogs, aiLoading, runRecognition]);

  useEffect(() => {
    if (!prevPendingRecognitionRef.current && pendingRecognition && analyzePulseTimerRef.current) {
      clearTimeout(analyzePulseTimerRef.current);
      analyzePulseTimerRef.current = null;
      setAnalyzingPulse(false);
    }
    if (prevPendingRecognitionRef.current && !pendingRecognition && recognizeFileKeys.size > 0) {
      if (analyzePulseTimerRef.current) clearTimeout(analyzePulseTimerRef.current);
      setAnalyzingPulse(true);
      analyzePulseTimerRef.current = setTimeout(() => {
        setAnalyzingPulse(false);
        analyzePulseTimerRef.current = null;
      }, 700);
    }
    prevPendingRecognitionRef.current = pendingRecognition;
  }, [pendingRecognition, recognizeFileKeys.size]);

  useEffect(() => {
    if (files.length === 0) {
      setAiRecogs({});
      setAiLoading({});
      recognizeInFlightRef.current.clear();
      setUserEdited({ title: false, content: false, category: false });
      setTitle("");
      setContent("");
      setCategory("food");
      setUploadingPulse(false);
      setAnalyzingPulse(false);
      if (uploadPulseTimerRef.current) {
        clearTimeout(uploadPulseTimerRef.current);
        uploadPulseTimerRef.current = null;
      }
      if (analyzePulseTimerRef.current) {
        clearTimeout(analyzePulseTimerRef.current);
        analyzePulseTimerRef.current = null;
      }
    }
  }, [files.length]);

  const processingStatus = useMemo(() => {
    if (files.length === 0) return null;
    if (uploadingPulse) {
      return { label: "업로드 중", tone: "info" as const, text: "미디어를 수신했습니다. 분석을 준비하는 중..." };
    }
    if (pendingRecognition) {
      const videoPending = [...videoFileKeys].some((k) => aiLoading[k] || !aiRecogs[k]);
      const imagePending = [...imageFileKeys].some((k) => aiLoading[k] || !aiRecogs[k]);
      if (videoPending && !imagePending && imageFileKeys.size === 0) {
        return { label: "분석 중", tone: "info" as const, text: "AI가 릴스 영상을 분석하는 중입니다 (화면+자막)..." };
      }
      return { label: "분석 중", tone: "info" as const, text: "AI가 이미지/영상을 자동 분석하는 중..." };
    }
    if (analyzingPulse) {
      return { label: "처리 중", tone: "info" as const, text: "분석 결과를 취합하여 폼을 자동 입력하는 중..." };
    }
    if (allRecognitionDone) {
      return { label: "준비 완료", tone: "success" as const, text: "분석 완료. 진단을 시작할 수 있습니다." };
    }
    return null;
  }, [
    files.length,
    uploadingPulse,
    pendingRecognition,
    analyzingPulse,
    allRecognitionDone,
    videoFileKeys,
    imageFileKeys,
    aiLoading,
    aiRecogs,
  ]);

  const lockInputs = !!processingStatus && processingStatus.label !== "준비 완료";
  const isFormBlocked = files.length > 0 && !allRecognitionDone;

  const [submitError, setSubmitError] = useState("");
  // Auto-clear error when user fixes the condition
  useEffect(() => { if (submitError) setSubmitError(""); }, [files.length, title]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = () => {
    if (files.length === 0) { setSubmitError("게시물 이미지를 먼저 업로드하세요"); return; }
    if (!title.trim()) { setSubmitError("제목/첫 문장을 입력하세요"); return; }
    if (lockInputs || isFormBlocked) { setSubmitError("AI 분석 중입니다. 잠시 기다려주세요"); return; }
    setSubmitError("");
    // Check if any recognition result shows high engagement
    const hasHighEngagement = successResults.some(r => r.engagement_signal?.is_high_engagement);
    navigate("/diagnosing", {
      state: {
        title, content, tags: "", category,
        coverFile: files.find((f) => f.type.startsWith("image/")) ?? null,
        coverImages: files.filter((f) => f.type.startsWith("image/")),
        videoFile: files.find((f) => f.type.startsWith("video/")) ?? null,
        hasHighEngagement,
      },
    });
  };

  const recognizedSlots = useMemo(
    () => new Set(
      successRecogEntries
        .map(([, r]) => (typeof r.slot_type === "string" ? r.slot_type.toLowerCase() : ""))
        .filter(Boolean),
    ),
    [successRecogEntries],
  );
  const hasDetailScreenshot = recognizedSlots.has("content");
  const canSubmit = files.length > 0 && title.trim().length > 0 && !lockInputs && !isFormBlocked;
  /* aiSuggestion removed — detail screenshot warning shown inline below CTA */
  const slotLabelMap: Record<string, string> = {
    content: "상세",
    cover: "커버",
    profile: "프로필",
    comments: "댓글",
  };

  /** 모든 소재의 빠른 인식 요청이 종료됨(전부 실패 포함) */
  const isReady = files.length > 0 && allRecognitionDone;
  /** 최소 1건 성공 시에만 '분석 완료' 상태를 보여 실패 상태와 동시에 표시되지 않게 한다. */
  const hasRecogSuccess = successResults.length > 0;
  const [leaving, setLeaving] = useState(false);

  // Reset leaving on mount (browser back button fix)
  useEffect(() => { setLeaving(false); }, []);

  return (
    <Box sx={{
      height: { md: "100dvh" },
      minHeight: { xs: "100dvh" },
      display: "flex",
      flexDirection: "column",
      bgcolor: "#fff8f8",
      overflow: { xs: "auto", md: "hidden" },
      transition: "transform 0.35s ease, opacity 0.3s ease",
      transform: leaving ? "translateY(-40px)" : "none",
      opacity: leaving ? 0 : 1,
    }}>

      {/* ═══ Header - 핵심 상태 정보를 한 줄에 배치 ═══ */}
      <Box component="header" sx={{
        flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        px: { xs: 1.5, md: 3 }, height: 48,
        bgcolor: "#fff", borderBottom: "1px solid rgba(214,41,118,0.12)",
      }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: { xs: 0.75, md: 1.5 } }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, flexShrink: 0 }}>
            <Box sx={{
              width: 24, height: 24, borderRadius: "6px",
              background: "linear-gradient(135deg, #f56040, #c21766)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Typography sx={{ color: "#fff", fontSize: 10, fontWeight: 800, fontFamily: "Inter" }}>Rx</Typography>
            </Box>
            <Typography sx={{ fontSize: 14, fontWeight: 800, color: "#241628", letterSpacing: "-0.02em" }}>
              InstaRx
            </Typography>
          </Box>
          {/* Desktop: inline description */}
          <Typography sx={{
            display: { xs: "none", md: "block" },
            fontSize: 12, color: "#8f7b94", fontWeight: 500,
          }}>
            인스타 게시물 진단 및 반응 예측 모델
          </Typography>
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <Button startIcon={<HistoryOutlined sx={{ fontSize: 14 }} />}
            onClick={() => navigate("/history")} size="small"
            sx={{ color: "#8f7b94", fontSize: 12, fontWeight: 600, minWidth: "auto", px: 1, borderRadius: "8px",
              "&:hover": { color: "#241628", bgcolor: "rgba(214,41,118,0.08)" } }}
          >
            <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>히스토리</Box>
          </Button>
          <Button startIcon={<EmailOutlinedIcon sx={{ fontSize: 14 }} />}
            component="a" href="mailto:jwj0620@gachon.ac.kr" size="small"
            sx={{ color: "#8f7b94", fontSize: 12, fontWeight: 600, minWidth: "auto", px: 1, borderRadius: "8px",
              textDecoration: "none",
              "&:hover": { color: "#d62976", bgcolor: "#fff0f2" } }}
          >
            <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>문의</Box>
          </Button>
        </Box>
      </Box>

      {/* ═══ Work area - 남은 높이를 채우고 데스크톱에서 과도한 스크롤 방지 ═══ */}
      <Box sx={{
        flex: 1,
        display: "flex", justifyContent: "center", alignItems: "stretch",
        px: { xs: 0, md: 3 },
        py: { xs: 0, md: 2 },
        pb: { xs: "100px", md: 2 },
        overflow: { xs: "auto", md: "hidden" },
        minHeight: 0,
      }}>
        <Box sx={{
          width: "100%", maxWidth: 1000,
          display: "grid",
          gridTemplateColumns: { xs: "1fr", md: "1.2fr 1fr" },
          gap: { xs: 0, md: 2 },
          alignItems: "stretch",
          minHeight: 0,
        }}>

          {/* ═══ Left: Upload ═══ */}
          <Box sx={{
            bgcolor: "#fff",
            border: { md: "1px solid rgba(214,41,118,0.12)" },
            borderBottom: { xs: "1px solid rgba(214,41,118,0.12)", md: "1px solid rgba(214,41,118,0.12)" },
            borderRadius: { xs: 0, md: "14px" },
            p: { xs: 2, md: 2.5 },
            display: "flex", flexDirection: "column",
            gap: 1.5,
            minHeight: 0,
            overflow: "hidden",
          }}>
            <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
              <Box>
                <Typography sx={{ fontSize: 14, fontWeight: 700, color: "#241628" }}>
                  게시물 소재 업로드
                </Typography>
                <Typography sx={{ fontSize: 12, color: "#8f7b94", mt: 0.25 }}>
                  이미지/릴스를 올리면 제목·본문·카테고리가 자동으로 입력됩니다
                </Typography>
              </Box>
              {files.length > 0 && (
                <Chip size="small" label={`${files.length}/9`} sx={{
                  height: 22, fontSize: 10, fontWeight: 700,
                  bgcolor: isReady && hasRecogSuccess ? "#f0fdf4" : isReady ? "#fff7ed" : "#eff6ff",
                  color: isReady && hasRecogSuccess ? "#16a34a" : isReady ? "#c2410c" : "#2563eb",
                  border: isReady && hasRecogSuccess ? "1px solid #bbf7d0" : isReady ? "1px solid #fed7aa" : "1px solid #bfdbfe",
                }} />
              )}
            </Box>

            {apiReachable === false && (
              <Alert severity="warning" sx={{ fontSize: 12, py: 0.5, borderRadius: "10px" }}>
                서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.
              </Alert>
            )}

            <Box sx={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
              <UploadZone files={files} onFilesChange={handleFilesChange} maxFiles={9} compact={isDesktop} />
            </Box>

            {/* Slot chips */}
            <AnimatePresence>
              {files.length > 0 && (
                <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.2 }}
                  style={{ flexShrink: 0 }}>
                  <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap", alignItems: "center" }}>
                    {Object.entries(slotLabelMap).map(([slot, label]) => (
                      <Chip key={slot} size="small" label={label}
                        color={recognizedSlots.has(slot) ? "success" : "default"}
                        variant={recognizedSlots.has(slot) ? "filled" : "outlined"}
                        sx={{ fontSize: 10, height: 20 }} />
                    ))}
                  </Box>
                </motion.div>
              )}
            </AnimatePresence>

            {/* AI analysis progress bar — smooth */}
            <AnimatePresence>
              {(anyLoading || pendingRecognition) && files.length > 0 && (
                <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.25 }}
                  style={{ flexShrink: 0 }}>
                  <Box sx={{ px: 0.5 }}>
                    <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 0.5 }}>
                      <AnalysisStatusText />
                      <Typography sx={{ fontSize: 10, color: "#b6a4ba", fontVariantNumeric: "tabular-nums" }}>
                        {Object.keys(aiRecogs).length}/{Math.max(recognizeFileKeys.size, 1)}
                      </Typography>
                    </Box>
                    <SmoothProgressBar
                      done={Object.keys(aiRecogs).length}
                      total={Math.max(recognizeFileKeys.size, 1)}
                    />
                  </Box>
                </motion.div>
              )}
            </AnimatePresence>

            {/* 성공 인식이 있을 때만 완료 표시; 전부 실패는 아래 빨간 글로 */}
            {isReady && files.length > 0 && hasRecogSuccess && (
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, px: 0.5 }}>
                <CheckCircleIcon sx={{ fontSize: 13, color: "#16a34a" }} />
                <Typography sx={{ fontSize: 11, color: "#16a34a", fontWeight: 600 }}>분석 완료 — 진단을 시작하세요</Typography>
              </Box>
            )}
            {allFailed && (
              <Typography sx={{ fontSize: 11, color: "#dc2626", px: 0.5, lineHeight: 1.5 }}>
                {firstRecognizeError
                  ? `분석 실패: ${firstRecognizeError}`
                  : "분석에 실패했습니다. 직접 입력해 주세요"}
              </Typography>
            )}

          </Box>

          {/* ═══ Right: Form ═══ */}
          <Box sx={{
            bgcolor: "#fff",
            border: { md: "1px solid rgba(214,41,118,0.12)" },
            borderRadius: { xs: 0, md: "14px" },
            p: { xs: 2, md: 2.5 },
            display: "flex", flexDirection: "column",
            gap: 1.75,
            minHeight: 0,
            overflow: { xs: "visible", md: "auto" },
          }}>
            <Typography sx={{ fontSize: 14, fontWeight: 700, color: "#241628", flexShrink: 0 }}>
              게시물 정보
            </Typography>

            {videoWithoutImage && allRecognitionDone && !allFailed && (
              <Alert severity="info" sx={{ fontSize: 12, py: 0.75, borderRadius: "10px", flexShrink: 0 }}>
                캡션이 보이는 스크린샷을 함께 올리면 더 정확하게 분석됩니다.
              </Alert>
            )}

            {isFormBlocked && (
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, px: 1, py: 0.5, borderRadius: "8px", bgcolor: "#eff6ff", flexShrink: 0 }}>
                <CircularProgress size={12} thickness={5} sx={{ color: "#4f5bd5" }} />
                <Typography sx={{ fontSize: 12, color: "#4f5bd5", fontWeight: 500 }}>분석 완료 후 자동으로 입력됩니다</Typography>
              </Box>
            )}

            <Box sx={{
              flex: 1, minHeight: 0,
              opacity: isFormBlocked ? 0.4 : 1,
              pointerEvents: isFormBlocked ? "none" : "auto",
              transition: "opacity 0.3s",
              display: "flex", flexDirection: "column", gap: 1.75,
            }}>
              <Box>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 0.5 }}>
                  <Typography sx={{ fontSize: 13, fontWeight: 600, color: "#241628" }}>제목 / 첫 문장</Typography>
                  {autoFilled.title && <Typography sx={{ fontSize: 10, color: "#16a34a", fontWeight: 600 }}>자동 입력</Typography>}
                </Box>
                <TextField required fullWidth size="small" disabled={lockInputs} value={title}
                  onChange={(e) => { setTitle(e.target.value); setUserEdited((p) => ({ ...p, title: true })); }}
                  placeholder="캡션 첫 줄 (스크롤 전 보이는 문장)" slotProps={{ htmlInput: { maxLength: 100 } }} />
                {showWarnings && warnings.title && !title.trim() && !userEdited.title && (
                  <Typography sx={{ fontSize: 11, color: "#d97706", mt: 0.5 }}>제목을 직접 입력하세요</Typography>
                )}
              </Box>

              <Box>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 0.5 }}>
                  <Typography sx={{ fontSize: 13, fontWeight: 600, color: "#241628" }}>캡션 본문</Typography>
                  {autoFilled.content && <Typography sx={{ fontSize: 10, color: "#16a34a", fontWeight: 600 }}>자동 입력</Typography>}
                </Box>
                <TextField fullWidth multiline rows={isDesktop ? 3 : 3} size="small" disabled={lockInputs} value={content}
                  onChange={(e) => { setContent(e.target.value); setUserEdited((p) => ({ ...p, content: true })); }}
                  placeholder="캡션 본문 (해시태그 포함, 선택사항)" />
              </Box>

              <Box>
                <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 0.75 }}>
                  <Typography sx={{ fontSize: 13, fontWeight: 600, color: "#241628" }}>카테고리</Typography>
                  {autoFilled.category && <Typography sx={{ fontSize: 10, color: "#16a34a", fontWeight: 600 }}>자동 인식</Typography>}
                </Box>
                <CategoryPicker value={category} onChange={(v) => { setCategory(v); setUserEdited((p) => ({ ...p, category: true })); }} />
              </Box>
            </Box>

            {/* Desktop CTA */}
            <Box sx={{ display: { xs: "none", md: "flex" }, flexDirection: "column", gap: 1, flexShrink: 0, pt: 0.5 }}>
              <Button variant="contained" fullWidth disabled={!canSubmit} onClick={handleSubmit}
                sx={{
                  py: 1.1, fontSize: 14, fontWeight: 700, borderRadius: "10px", minHeight: 42,
                  background: "#d62976", boxShadow: "0 4px 16px rgba(255,36,66,0.25)",
                  "&:hover": { background: "#c21766", transform: "translateY(-1px)", boxShadow: "0 6px 24px rgba(255,36,66,0.35)" },
                  "&:active": { transform: "translateY(0)" },
                  "&.Mui-disabled": { background: "#eee", boxShadow: "none", color: "#b6a4ba" },
                }}
              >
                진단 시작
              </Button>
              {files.length > 0 && allRecognitionDone && !hasDetailScreenshot && (
                <Typography sx={{ fontSize: 10, color: "#d97706", textAlign: "center" }}>캡션이 보이는 상세 스크린샷을 추가하면 더 정확합니다</Typography>
              )}
            </Box>
          </Box>
        </Box>
      </Box>

      {/* ═══ Mobile fixed CTA ═══ */}
      <Box sx={{
        display: { xs: "block", md: "none" },
        position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 30,
        px: 1.5, pt: 1,
        pb: "max(8px, env(safe-area-inset-bottom))",
        bgcolor: "rgba(255,255,255,0.95)", borderTop: "1px solid rgba(214,41,118,0.12)",
      }}>
        <Button variant="contained" fullWidth onClick={handleSubmit}
          sx={{
            py: 1.1, fontSize: 15, fontWeight: 700, borderRadius: "10px", minHeight: 46,
            background: canSubmit ? "#d62976" : "#eee",
            boxShadow: canSubmit ? "0 4px 16px rgba(255,36,66,0.25)" : "none",
            color: canSubmit ? "#fff" : "#b6a4ba",
            "&:hover": { background: canSubmit ? "#c21766" : "#eee" },
          }}
        >
          진단 시작
        </Button>
        {submitError && (
          <Typography sx={{ fontSize: 11, color: "#dc2626", textAlign: "center", mt: 0.5 }}>
            {submitError}
          </Typography>
        )}
      </Box>

      {/* ═══ Footer — legal links ═══ */}
      <Box sx={{
        display: { xs: "none", md: "flex" },
        justifyContent: "center", alignItems: "center", gap: 1.5,
        py: 0.8, flexShrink: 0,
        borderTop: "1px solid rgba(214,41,118,0.12)", bgcolor: "#fff",
      }}>
        <Typography
          component="a" href="/terms"
          sx={{ fontSize: 11, color: "#b6a4ba", textDecoration: "none", "&:hover": { color: "#d62976" } }}
        >
          서비스 약관
        </Typography>
        <Typography sx={{ fontSize: 11, color: "#ddd" }}>|</Typography>
        <Typography
          component="a" href="/privacy"
          sx={{ fontSize: 11, color: "#b6a4ba", textDecoration: "none", "&:hover": { color: "#d62976" } }}
        >
          개인정보처리방침
        </Typography>
        <Typography sx={{ fontSize: 11, color: "#ddd" }}>|</Typography>
        <Typography
          component="a" href="https://github.com" target="_blank"
          sx={{ fontSize: 11, color: "#b6a4ba", textDecoration: "none", "&:hover": { color: "#d62976" } }}
        >
          GitHub
        </Typography>
        <Typography sx={{ fontSize: 11, color: "#ddd" }}>|</Typography>
        <Typography
          component="a" href="mailto:jwj0620@gachon.ac.kr"
          sx={{ fontSize: 11, color: "#b6a4ba", textDecoration: "none", "&:hover": { color: "#d62976" } }}
        >
          문의 jwj0620@gachon.ac.kr
        </Typography>
      </Box>

    </Box>
  );
}
