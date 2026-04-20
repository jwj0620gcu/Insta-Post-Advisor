import { useState, useCallback, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box, Typography, Button, Stack, Chip, CircularProgress,
  Alert, TextField, LinearProgress, IconButton,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CloseIcon from "@mui/icons-material/Close";
import PhotoCameraIcon from "@mui/icons-material/PhotoCamera";
import ArticleIcon from "@mui/icons-material/Article";
import PersonIcon from "@mui/icons-material/Person";
import ChatBubbleIcon from "@mui/icons-material/ChatBubble";
import VideocamIcon from "@mui/icons-material/Videocam";
import { motion, AnimatePresence } from "framer-motion";
import {
  quickRecognize,
  deepAnalyze,
} from "../utils/api";
import type {
  SlotType,
  QuickRecognizeResult,
  DeepAnalysisResult,
} from "../utils/api";

type Scenario = "pre_publish" | "post_publish";

interface SlotConfig {
  key: SlotType;
  label: string;
  desc: string;
  icon: React.ReactNode;
  required: boolean;
}

const SLOTS: SlotConfig[] = [
  { key: "cover", label: "커버 스크린샷", desc: "시각 스타일과 첫 이미지 흡인력 분석에 사용됩니다", icon: <PhotoCameraIcon />, required: true },
  { key: "content", label: "본문 스크린샷", desc: "캡션, 해시태그 등 텍스트 분석에 사용됩니다", icon: <ArticleIcon />, required: true },
  { key: "profile", label: "프로필 스크린샷", desc: "계정 영향력 및 작성자 프로필 분석에 사용됩니다", icon: <PersonIcon />, required: false },
  { key: "comments", label: "댓글 스크린샷", desc: "사용자 반응 및 참여도 분석에 사용됩니다", icon: <ChatBubbleIcon />, required: false },
];

const LINK_REGEX = /https?:\/\/\S+/gi;
const ORDERED_SLOT_KEYS: SlotType[] = ["cover", "content", "profile", "comments"];
const DRAFT_KEY = "instarx_screenshot_draft_v1";

/**
 * 스크린샷 다차원 분석 페이지
 */
export default function ScreenshotAnalysis() {
  const navigate = useNavigate();

  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [recognitions, setRecognitions] = useState<Record<string, QuickRecognizeResult>>({});
  const [recognizing, setRecognizing] = useState<Record<string, boolean>>({});
  const [recognitionErrors, setRecognitionErrors] = useState<Record<string, string>>({});
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [extraText, setExtraText] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<DeepAnalysisResult | null>(null);
  const [error, setError] = useState("");
  const inputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const videoInputRef = useRef<HTMLInputElement | null>(null);
  const slotCardRefs = useRef<Record<string, HTMLDivElement | null>>({});

  /**
   * 세션 복원: 장면 선택과 추가 텍스트 유지.
   * 파일 객체는 브라우저 보안 제한으로 새로 고침 시 복원 불가.
   */
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(DRAFT_KEY);
      if (!raw) return;
      const draft = JSON.parse(raw) as { scenario?: Scenario; extraText?: string };
      if (draft.scenario) setScenario(draft.scenario);
      if (typeof draft.extraText === "string") setExtraText(draft.extraText);
    } catch {
      // ignore
    }
  }, []);

  /** 사용자 입력 임시 저장 */
  useEffect(() => {
    try {
      sessionStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({ scenario, extraText }),
      );
    } catch {
      // ignore
    }
  }, [scenario, extraText]);

  const currentGuideIndex = ORDERED_SLOT_KEYS.findIndex((key) => !files[key]);

  /** 업로드 후 다음 단계로 자동 스크롤 */
  useEffect(() => {
    if (!scenario || currentGuideIndex < 0) return;
    const nextKey = ORDERED_SLOT_KEYS[currentGuideIndex];
    const nextCard = slotCardRefs.current[nextKey];
    if (nextCard) {
      nextCard.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [scenario, currentGuideIndex]);

  const handleFile = useCallback(async (slot: SlotType, file: File) => {
    setFiles((p) => ({ ...p, [slot]: file }));
    const reader = new FileReader();
    reader.onload = (e) => setPreviews((p) => ({ ...p, [slot]: e.target?.result as string }));
    reader.readAsDataURL(file);

    setRecognizing((p) => ({ ...p, [slot]: true }));
    try {
      const res = await quickRecognize(file, slot);
      setRecognitions((p) => ({ ...p, [slot]: res }));
      setRecognitionErrors((p) => {
        const n = { ...p };
        delete n[slot];
        return n;
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "AI 인식 실패, 다시 시도해 주세요";
      setRecognitionErrors((p) => ({ ...p, [slot]: msg }));
    } finally {
      setRecognizing((p) => ({ ...p, [slot]: false }));
    }
  }, []);

  /** 단일 스크린샷 AI 인식 재시도 */
  const retryRecognize = useCallback(async (slot: SlotType) => {
    const file = files[slot];
    if (!file) return;
    setRecognizing((p) => ({ ...p, [slot]: true }));
    try {
      const res = await quickRecognize(file, slot);
      setRecognitions((p) => ({ ...p, [slot]: res }));
      setRecognitionErrors((p) => {
        const n = { ...p };
        delete n[slot];
        return n;
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "AI 인식 실패, 다시 시도해 주세요";
      setRecognitionErrors((p) => ({ ...p, [slot]: msg }));
    } finally {
      setRecognizing((p) => ({ ...p, [slot]: false }));
    }
  }, [files]);

  const removeFile = useCallback((slot: string) => {
    setFiles((p) => { const n = { ...p }; delete n[slot]; return n; });
    setPreviews((p) => { const n = { ...p }; delete n[slot]; return n; });
    setRecognitions((p) => { const n = { ...p }; delete n[slot]; return n; });
    setRecognitionErrors((p) => { const n = { ...p }; delete n[slot]; return n; });
  }, []);

  const filledCount = Object.values(files).filter(Boolean).length;
  const canSubmit = filledCount >= 1 && !analyzing;
  const visibleGuideCount = currentGuideIndex === -1 ? ORDERED_SLOT_KEYS.length : currentGuideIndex + 1;
  const nextSlotLabel = currentGuideIndex === -1
    ? ""
    : (SLOTS.find((s) => s.key === ORDERED_SLOT_KEYS[currentGuideIndex])?.label ?? "다음 단계");
  const submitLabel = currentGuideIndex === -1
    ? "심층 분석 시작"
    : (filledCount === 0 ? `계속 업로드 (${nextSlotLabel} 필요)` : `심층 분석 시작 (${nextSlotLabel} 추가 권장)`);

  const handleSubmit = async () => {
    if (!scenario) return;
    setAnalyzing(true);
    setError("");
    try {
      const res = await deepAnalyze({
        scenario,
        cover: files.cover ?? undefined,
        contentImg: files.content ?? undefined,
        profile: files.profile ?? undefined,
        comments: files.comments ?? undefined,
        video: videoFile ?? undefined,
        extraText: extraText.replace(LINK_REGEX, ""),
      });
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "분석 실패");
    } finally {
      setAnalyzing(false);
    }
  };

  /* ====== 분석 모드 선택 ====== */
  if (!scenario) {
    return (
      <Box sx={{ minHeight: "100vh", bgcolor: "#fff8f8", display: "flex", flexDirection: "column", alignItems: "center", px: 2, py: { xs: 5, md: 8 } }}>
        <Box sx={{ textAlign: "center", mb: 4 }}>
          <Typography sx={{ fontSize: "1.4rem", fontWeight: 700, color: "#241628" }}>분석 모드 선택</Typography>
          <Typography sx={{ fontSize: "0.85rem", color: "#8f7b94", mt: 0.5 }}>스크린샷으로 다차원 콘텐츠 분석</Typography>
        </Box>
        <Stack spacing={2} sx={{ width: "100%", maxWidth: 440 }}>
          {([
            { val: "pre_publish" as Scenario, title: "게시 전 분석", desc: "초안·미리보기 단계 — AI 사전 검증으로 게시 전 최적화", color: "#2563eb" },
            { val: "post_publish" as Scenario, title: "게시 후 분석", desc: "이미 게시된 콘텐츠 — 트래픽 데이터를 반영한 심층 분석", color: "#16a34a" },
          ]).map((s) => (
            <Box
              key={s.val}
              onClick={() => setScenario(s.val)}
              sx={{
                p: 3, borderRadius: "16px", bgcolor: "#fff", border: "1px solid rgba(214,41,118,0.12)",
                cursor: "pointer", transition: "all 0.15s",
                "&:hover": { borderColor: s.color, boxShadow: `0 0 0 1px ${s.color}20` },
              }}
            >
              <Typography sx={{ fontWeight: 700, fontSize: 16, color: "#241628" }}>{s.title}</Typography>
              <Typography sx={{ fontSize: 13, color: "#8f7b94", mt: 0.5 }}>{s.desc}</Typography>
            </Box>
          ))}
        </Stack>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate("/app")} sx={{ mt: 4, color: "#8f7b94" }}>
          홈으로 돌아가기
        </Button>
      </Box>
    );
  }

  /* ====== 결과 표시 ====== */
  if (result) {
    return (
      <Box sx={{ minHeight: "100vh", bgcolor: "#fff8f8", pb: 6 }}>
        <Box sx={{ position: "sticky", top: 0, zIndex: 10, bgcolor: "#fff", borderBottom: "1px solid rgba(214,41,118,0.12)" }}>
          <Box sx={{ maxWidth: 720, mx: "auto", px: 2, py: 1.5, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Button startIcon={<ArrowBackIcon />} onClick={() => { setResult(null); }} size="small" sx={{ color: "#241628" }}>돌아가기</Button>
            <Typography sx={{ fontWeight: 700, color: "#241628", fontSize: 16 }}>분석 결과</Typography>
            <Box sx={{ width: 64 }} />
          </Box>
        </Box>
        <Box sx={{ maxWidth: 720, mx: "auto", px: 2, mt: 3 }}>
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
            <Stack spacing={2}>
              {/* 종합 정보 */}
              <Box sx={{ p: 3, borderRadius: "16px", bgcolor: "#fff", border: "1px solid rgba(214,41,118,0.12)" }}>
                <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
                  <Typography sx={{ fontWeight: 700, fontSize: 16, color: "#241628" }}>{result.overall.scenario}</Typography>
                  <Chip label={`완성도 ${result.overall.completeness}%`} size="small"
                    sx={{ bgcolor: result.overall.completeness >= 75 ? "#dcfce7" : "#fef3c7", color: result.overall.completeness >= 75 ? "#16a34a" : "#d97706", fontWeight: 600 }}
                  />
                </Box>
                <LinearProgress variant="determinate" value={result.overall.completeness} sx={{ height: 6, borderRadius: 3, mb: 2, bgcolor: "rgba(214,41,118,0.12)", "& .MuiLinearProgress-bar": { bgcolor: result.overall.completeness >= 75 ? "#16a34a" : "#d97706", borderRadius: 3 } }} />
                {result.overall.tips.length > 0 && (
                  <Stack spacing={0.5}>
                    {result.overall.tips.map((t, i) => (
                      <Typography key={i} sx={{ fontSize: 13, color: "#8f7b94" }}>· {t}</Typography>
                    ))}
                  </Stack>
                )}
              </Box>

              {/* 각 차원 분석 */}
              {Object.entries(result.analyses).map(([slot, data]) => {
                const config = SLOTS.find((s) => s.key === slot);
                const hasError = data && typeof data === "object" && "error" in data;
                return (
                  <Box key={slot} sx={{ p: 3, borderRadius: "16px", bgcolor: "#fff", border: "1px solid rgba(214,41,118,0.12)" }}>
                    <Typography sx={{ fontWeight: 600, fontSize: 15, color: "#241628", mb: 1.5 }}>
                      {config?.label || slot}
                    </Typography>
                    {hasError ? (
                      <Alert severity="error" sx={{ borderRadius: "12px" }}>{String((data as Record<string, unknown>).error)}</Alert>
                    ) : (
                      <Box sx={{ p: 2, borderRadius: "12px", bgcolor: "#fff8f8", border: "1px solid rgba(214,41,118,0.08)" }}>
                        {Object.entries(data as Record<string, unknown>).map(([k, v]) => (
                          <Box key={k} sx={{ mb: 1 }}>
                            <Typography component="span" sx={{ fontSize: 12, fontWeight: 600, color: "#8f7b94" }}>
                              {k}:
                            </Typography>
                            <Typography component="span" sx={{ fontSize: 13, color: "#505050" }}>
                              {Array.isArray(v) ? (v as string[]).join(", ") : String(v)}
                            </Typography>
                          </Box>
                        ))}
                      </Box>
                    )}
                  </Box>
                );
              })}

              {/* 동영상 정보 */}
              {result.video_info && (
                <Box sx={{ p: 3, borderRadius: "16px", bgcolor: "#fff", border: "1px solid rgba(214,41,118,0.12)" }}>
                  <Typography sx={{ fontWeight: 600, fontSize: 15, color: "#241628", mb: 1 }}>동영상 정보</Typography>
                  <Typography sx={{ fontSize: 13, color: "#666" }}>
                    {result.video_info.filename} ({result.video_info.size_mb} MB)
                  </Typography>
                </Box>
              )}

              <Button variant="contained" fullWidth onClick={() => navigate("/app")}
                sx={{ py: 1.4, fontSize: "0.95rem", fontWeight: 600, borderRadius: "12px", bgcolor: "#d62976", "&:hover": { bgcolor: "#d91a36" } }}
              >
                홈으로 돌아가기
              </Button>
            </Stack>
          </motion.div>
        </Box>
      </Box>
    );
  }

  /* ====== 업로드 화면 ====== */
  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "#fff8f8", pb: 6 }}>
      {/* 상단 바 */}
      <Box sx={{ position: "sticky", top: 0, zIndex: 10, bgcolor: "#fff", borderBottom: "1px solid rgba(214,41,118,0.12)" }}>
        <Box sx={{ maxWidth: 720, mx: "auto", px: 2, py: 1.5, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Button startIcon={<ArrowBackIcon />} onClick={() => setScenario(null)} size="small" sx={{ color: "#241628" }}>
            돌아가기
          </Button>
          <Typography sx={{ fontWeight: 700, color: "#241628", fontSize: 16 }}>
            {scenario === "pre_publish" ? "게시 전 분석" : "게시 후 분석"}
          </Typography>
          <Box sx={{ width: 64 }} />
        </Box>
      </Box>

      <Box sx={{ maxWidth: 720, mx: "auto", px: 2, mt: 3 }}>
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
          <Stack spacing={2}>
            <Box sx={{ p: 2, borderRadius: "14px", bgcolor: "#fff", border: "1px solid rgba(214,41,118,0.12)" }}>
              <Typography sx={{ fontSize: 13, color: "#666", mb: 1 }}>
                분석 흐름: 모드 선택 → 스크린샷 업로드 (커버/본문/프로필/댓글) → AI 빠른 인식 → 심층 분석
              </Typography>
              <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                {ORDERED_SLOT_KEYS.map((key, idx) => {
                  const done = Boolean(files[key]);
                  const active = idx === currentGuideIndex || (currentGuideIndex === -1 && idx === ORDERED_SLOT_KEYS.length - 1);
                  const label = SLOTS.find((s) => s.key === key)?.label ?? key;
                  return (
                    <Chip
                      key={key}
                      label={`${idx + 1}. ${label}`}
                      size="small"
                      sx={{
                        bgcolor: done ? "#f0fdf4" : active ? "#fff0f1" : "rgba(214,41,118,0.08)",
                        color: done ? "#16a34a" : active ? "#d62976" : "#8f7b94",
                        fontWeight: done || active ? 600 : 500,
                      }}
                    />
                  );
                })}
              </Box>
            </Box>

            {/* 스크린샷 업로드 카드 */}
            {SLOTS.filter((_, idx) => idx < visibleGuideCount).map((slot, idx) => {
              const file = files[slot.key];
              const preview = previews[slot.key];
              const recog = recognitions[slot.key];
              const isRecog = recognizing[slot.key];
              const recogError = recognitionErrors[slot.key];
              const isLocked = idx > 0 && !files[ORDERED_SLOT_KEYS[idx - 1]];

              return (
                <Box
                  key={slot.key}
                  ref={(el: HTMLDivElement | null) => { slotCardRefs.current[slot.key] = el; }}
                  sx={{ p: 2.5, borderRadius: "16px", bgcolor: "#fff", border: "1px solid rgba(214,41,118,0.12)" }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 1.5 }}>
                    <Box sx={{ color: "#d62976", display: "flex" }}>{slot.icon}</Box>
                    <Box sx={{ flex: 1 }}>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                        <Typography sx={{ fontWeight: 600, fontSize: 14, color: "#241628" }}>{slot.label}</Typography>
                        <Chip label={`단계 ${idx + 1}`} size="small" sx={{ height: 20, fontSize: 11, bgcolor: "rgba(214,41,118,0.08)", color: "#666" }} />
                        {slot.required && <Chip label="권장" size="small" sx={{ height: 20, fontSize: 11, bgcolor: "#fff0f1", color: "#d62976" }} />}
                      </Box>
                      <Typography sx={{ fontSize: 12, color: "#8f7b94" }}>{slot.desc}</Typography>
                    </Box>
                  </Box>

                  <AnimatePresence mode="wait">
                    {file && preview ? (
                      <motion.div key="preview" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
                        <Box sx={{ position: "relative", display: "inline-block" }}>
                          <Box component="img" src={preview} alt={slot.label}
                            sx={{ maxHeight: 160, maxWidth: "100%", borderRadius: "12px", display: "block", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}
                          />
                          <IconButton size="small" onClick={() => removeFile(slot.key)}
                            sx={{ position: "absolute", top: -8, right: -8, bgcolor: "#ff6b6b", color: "#fff", width: 24, height: 24, "&:hover": { bgcolor: "#e55a5a" } }}
                          >
                            <CloseIcon sx={{ fontSize: 14 }} />
                          </IconButton>
                        </Box>

                        {/* AI 인식 결과 */}
                        <Box sx={{ mt: 1.5 }}>
                          {isRecog ? (
                            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                              <CircularProgress size={14} sx={{ color: "#8f7b94" }} />
                              <Typography sx={{ fontSize: 12, color: "#8f7b94" }}>AI 인식 중...</Typography>
                            </Box>
                          ) : recog ? (
                            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, alignItems: "center" }}>
                              <CheckCircleIcon sx={{ fontSize: 16, color: "#16a34a" }} />
                              <Typography sx={{ fontSize: 12, color: "#16a34a", fontWeight: 600 }}>카테고리 인식됨</Typography>
                              {recog.category && (
                                <Chip label={recog.category} size="small" sx={{ height: 22, fontSize: 11, bgcolor: "#f0fdf4", color: "#16a34a", fontWeight: 600 }} />
                              )}
                              {recog.summary && (
                                <Typography sx={{ fontSize: 12, color: "#666" }}>{recog.summary}</Typography>
                              )}
                            </Box>
                          ) : recogError ? (
                            <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
                              <Typography sx={{ fontSize: 12, color: "#dc2626" }}>인식 실패: {recogError}</Typography>
                              <Button size="small" onClick={() => retryRecognize(slot.key)} sx={{ minWidth: 0, px: 1 }}>
                                재시도
                              </Button>
                            </Box>
                          ) : null}
                        </Box>
                      </motion.div>
                    ) : (
                      <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                        <Box
                          onClick={() => {
                            if (!isLocked) inputRefs.current[slot.key]?.click();
                          }}
                          sx={{
                            border: "2px dashed #e0e0e0", borderRadius: "12px",
                            py: 3, display: "flex", flexDirection: "column", alignItems: "center",
                            cursor: "pointer", transition: "all 0.15s",
                            opacity: isLocked ? 0.5 : 1,
                            pointerEvents: isLocked ? "none" : "auto",
                            "&:hover": { borderColor: "#d62976", bgcolor: "#fff5f6" },
                          }}
                        >
                          <CloudUploadIcon sx={{ fontSize: 28, color: "#b6a4ba" }} />
                          <Typography sx={{ fontSize: 13, color: "#8f7b94", mt: 0.5 }}>
                            {isLocked ? "이전 단계를 먼저 완료해 주세요" : `${slot.label} 업로드`}
                          </Typography>
                        </Box>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <input
                    ref={(el) => { inputRefs.current[slot.key] = el; }}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    hidden
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) handleFile(slot.key, f);
                      e.target.value = "";
                    }}
                  />
                </Box>
              );
            })}

            {/* 동영상 업로드 */}
            <Box sx={{ p: 2.5, borderRadius: "16px", bgcolor: "#fff", border: "1px solid rgba(214,41,118,0.12)" }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 1.5 }}>
                <Box sx={{ color: "#d62976", display: "flex" }}><VideocamIcon /></Box>
                <Box>
                  <Typography sx={{ fontWeight: 600, fontSize: 14, color: "#241628" }}>동영상 업로드</Typography>
                  <Typography sx={{ fontSize: 12, color: "#8f7b94" }}>선택 사항 — 릴스 또는 화면 녹화 동영상 업로드 (최대 100MB)</Typography>
                </Box>
              </Box>
              {videoFile ? (
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, p: 1.5, borderRadius: "10px", bgcolor: "#fff8f8", border: "1px solid rgba(214,41,118,0.12)" }}>
                  <VideocamIcon sx={{ fontSize: 20, color: "#666" }} />
                  <Typography sx={{ fontSize: 13, color: "#241628", flex: 1 }}>
                    {videoFile.name} ({(videoFile.size / 1024 / 1024).toFixed(1)} MB)
                  </Typography>
                  <IconButton size="small" onClick={() => setVideoFile(null)} sx={{ color: "#8f7b94" }}>
                    <CloseIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                </Box>
              ) : (
                <Box
                  onClick={() => videoInputRef.current?.click()}
                  sx={{
                    border: "2px dashed #e0e0e0", borderRadius: "12px", py: 2.5,
                    display: "flex", flexDirection: "column", alignItems: "center",
                    cursor: "pointer", "&:hover": { borderColor: "#d62976", bgcolor: "#fff5f6" },
                  }}
                >
                  <CloudUploadIcon sx={{ fontSize: 24, color: "#b6a4ba" }} />
                  <Typography sx={{ fontSize: 12, color: "#8f7b94", mt: 0.5 }}>동영상 업로드</Typography>
                </Box>
              )}
              <input ref={videoInputRef} type="file" accept="video/mp4,video/webm,video/quicktime" hidden
                onChange={(e) => { const f = e.target.files?.[0]; if (f) setVideoFile(f); if (e.target) e.target.value = ""; }}
              />
            </Box>

            {/* 추가 설명 */}
            <Box sx={{ p: 2.5, borderRadius: "16px", bgcolor: "#fff", border: "1px solid rgba(214,41,118,0.12)" }}>
              <Typography sx={{ fontWeight: 600, fontSize: 14, color: "#241628", mb: 1 }}>추가 설명 (선택)</Typography>
              <TextField
                fullWidth multiline rows={3}
                placeholder="보충 설명을 입력하세요 (링크는 자동으로 제거됩니다)"
                value={extraText}
                onChange={(e) => setExtraText(e.target.value.replace(LINK_REGEX, ""))}
                sx={{ "& .MuiOutlinedInput-root": { borderRadius: "12px" } }}
              />
            </Box>

            {error && <Alert severity="error" sx={{ borderRadius: "12px" }}>{error}</Alert>}

            {/* 제출 */}
            <Box sx={{ display: "flex", gap: 1.5 }}>
              <Typography sx={{ fontSize: 13, color: "#8f7b94", flex: 1, alignSelf: "center" }}>
                스크린샷 {filledCount}/4 업로드됨
                {videoFile ? " + 동영상" : ""}
              </Typography>
              <Button
                variant="contained" disabled={!canSubmit} onClick={handleSubmit}
                sx={{
                  px: 4, py: 1.4, fontSize: "0.95rem", fontWeight: 600, borderRadius: "12px",
                  bgcolor: "#d62976", "&:hover": { bgcolor: "#d91a36" },
                  "&.Mui-disabled": { bgcolor: "rgba(214,41,118,0.12)", color: "#b6a4ba" },
                }}
              >
                {analyzing ? <CircularProgress size={22} color="inherit" /> : submitLabel}
              </Button>
            </Box>
          </Stack>
        </motion.div>
      </Box>
    </Box>
  );
}
