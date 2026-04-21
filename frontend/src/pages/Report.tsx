import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Box, Typography, Button, Alert, Stack, IconButton, Tooltip,
  Skeleton,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import ReplayIcon from "@mui/icons-material/Replay";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import { motion } from "framer-motion";
import type { DiagnoseResult, OptimizePlan } from "../utils/api";
import { preScore, optimizeDiagnosis } from "../utils/api";
import AutoFixHighIcon from "@mui/icons-material/AutoFixHigh";
import StarIcon from "@mui/icons-material/Star";
import CircularProgress from "@mui/material/CircularProgress";
import {
  migrateLegacyLocalStorage,
  createLocalDiagnosisId,
  putLocalDiagnosis,
} from "../utils/localMemory";
import ScoreCard from "../components/ScoreCard";
import DimensionBars from "../components/DimensionBars";
import RadarChart from "../components/RadarChart";
import BaselineComparison from "../components/BaselineComparison";
import AgentDebate from "../components/AgentDebate";
import SimulatedComments from "../components/SimulatedComments";
import SuggestionList from "../components/SuggestionList";
import DiagnoseCard from "../components/DiagnoseCard";
import { showToast } from "../components/Toast";

const card = {
  bgcolor: "rgba(255,255,255,0.9)",
  border: "1px solid rgba(214,41,118,0.14)",
  borderRadius: { xs: "14px", md: "18px" },
  boxShadow: "0 8px 26px rgba(214,41,118,0.09)",
  p: { xs: 2.5, md: 3 },
};

const sectionGap = 2.5;

export default function Report() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as {
    report: DiagnoseResult;
    params: { title: string; category: string; content?: string; tags?: string };
    isFallback?: boolean;
  } | null;

  useEffect(() => {
    document.title = `진단 리포트 - Insta-Advisor`;
    if (!state || state.isFallback) return;
    const { report, params } = state;
    void (async () => {
      await migrateLegacyLocalStorage();
      const id = createLocalDiagnosisId();
      await putLocalDiagnosis({
        id,
        serverId: null,
        title: params.title,
        category: params.category,
        overall_score: report.overall_score,
        grade: report.grade,
        createdAt: Date.now(),
        report,
        params: params as Record<string, unknown>,
      });
      // 서버 업로드는 중단(#58). 로컬에만 저장
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!state) {
    return (
      <Box sx={{ minHeight: "100vh", bgcolor: "#fff8f8", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Box sx={{ textAlign: "center" }}>
          <Typography sx={{ color: "#8f7b94", fontSize: 14, mb: 2 }}>진단 데이터가 없습니다</Typography>
          <Button onClick={() => navigate("/app")} sx={{ color: "#d62976", fontWeight: 600 }}>홈으로 가기</Button>
        </Box>
      </Box>
    );
  }

  const { report, params, isFallback } = state;
  const userTags = typeof params.tags === "string"
    ? params.tags.split(",").filter(Boolean)
    : Array.isArray(params.tags) ? params.tags : [];

  // 원본·최적화 모두 동일 preScore 모델로 재채점해야 공정한 비교가 가능
  const [originalPreScore, setOriginalPreScore] = useState<number | null>(null);
  const [optimizedPreScore, setOptimizedPreScore] = useState<number | null>(null);
  const [rescoring, setRescoring] = useState(false);

  useEffect(() => {
    if (!report.optimized_title && !report.optimized_content) return;
    setRescoring(true);
    const baseParams = { category: params.category, tags: params.tags || "", image_count: 0 };
    Promise.all([
      preScore({ title: params.title, content: params.content || "", ...baseParams }),
      preScore({ title: report.optimized_title || params.title, content: report.optimized_content || params.content || "", ...baseParams }),
    ]).then(([orig, opt]) => {
      setOriginalPreScore(orig.total_score);
      setOptimizedPreScore(opt.total_score);
    }).catch(() => {}).finally(() => setRescoring(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // 최적화 점수가 실제로 높을 때만 비교 표시
  const scoreDelta = (originalPreScore != null && optimizedPreScore != null) ? Math.round(optimizedPreScore - originalPreScore) : null;
  const showScoreComparison = scoreDelta != null && scoreDelta > 0;

  // 섹션 순차 등장
  const [visibleSections, setVisibleSections] = useState(0);
  useEffect(() => {
    let i = 0;
    const timer = setInterval(() => {
      i++;
      setVisibleSections(i);
      if (i >= 6) clearInterval(timer);
    }, 150);
    return () => clearInterval(timer);
  }, []);

  // 최적화 엔진 상태
  const [optimizing, setOptimizing] = useState(false);
  const [optimizePlans, setOptimizePlans] = useState<OptimizePlan[]>([]);
  const [showOptPanel, setShowOptPanel] = useState(false);

  const handleOptimize = async () => {
    setOptimizing(true);
    setShowOptPanel(true);
    try {
      const result = await optimizeDiagnosis({
        title: params.title,
        content: params.content || "",
        category: params.category,
        issues: JSON.stringify(report.issues?.slice(0, 5) || []),
        suggestions: JSON.stringify(report.suggestions?.slice(0, 5) || []),
        overall_score: report.overall_score,
      });
      setOptimizePlans(result.plans);
    } catch (e) {
      console.warn("최적화 실패", e);
    } finally {
      setOptimizing(false);
    }
  };

  const copyText = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    showToast(`${label} 복사됨`);
  };

  const sectionAnim = (index: number) => ({
    initial: { opacity: 0, y: 16 },
    animate: visibleSections >= index ? { opacity: 1, y: 0 } : { opacity: 0, y: 16 },
    transition: { duration: 0.4, ease: "easeOut" as const },
  });

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "#fff8f8", pb: 6 }}>
      {/* Top bar */}
      <Box sx={{ position: "sticky", top: 0, zIndex: 50, bgcolor: "rgba(255,255,255,0.86)", backdropFilter: "blur(10px)", borderBottom: "1px solid rgba(214,41,118,0.12)" }}>
        <Box sx={{ maxWidth: 960, mx: "auto", px: { xs: 2, md: 3 }, py: 1.25, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Button
            startIcon={<ArrowBackIcon sx={{ fontSize: { xs: 18, md: 16 } }} />}
            onClick={() => navigate("/app")}
            sx={{ color: "#8f7b94", fontWeight: 500, fontSize: 13, "&:hover": { color: "#d62976" } }}
          >
            <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>홈</Box>
          </Button>
          <Typography sx={{ fontWeight: 600, fontSize: 15, color: "#241628", flex: 1, textAlign: "center" }}>진단 보고서</Typography>
          <Button
            startIcon={<ReplayIcon sx={{ fontSize: { xs: 18, md: 16 } }} />}
            onClick={() => navigate("/diagnosing", { state: params })}
            sx={{ color: "#8f7b94", fontWeight: 500, fontSize: 13, "&:hover": { color: "#d62976" } }}
          >
            <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>다시 진단</Box>
          </Button>
        </Box>
      </Box>

      {isFallback && (
        <Box sx={{ maxWidth: 960, mx: "auto", px: { xs: 2, md: 3 }, mt: 2 }}>
          <Alert severity="warning" sx={{ borderRadius: "12px" }}>현재 데모 데이터를 표시하고 있습니다</Alert>
        </Box>
      )}

      <Box sx={{ maxWidth: 960, mx: "auto", px: { xs: 2, md: 3 }, mt: 2.5 }}>

          {/* Row 1: Score + Dimension + Radar */}
          <motion.div {...sectionAnim(1)}>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr 1fr" }, gap: sectionGap, mb: sectionGap }}>
            <Box sx={card}>
              <ScoreCard score={report.overall_score} grade={report.grade} title={params.title} />
            </Box>
            <Box sx={card}>
              <Typography sx={{ fontWeight: 600, fontSize: 15, color: "#241628", mb: 2 }}>차원 점수</Typography>
              <DimensionBars data={report.radar_data} />
            </Box>
            <Box sx={card}>
              <Typography sx={{ fontWeight: 600, fontSize: 15, color: "#241628", mb: 1 }}>레이더 차트</Typography>
              <RadarChart data={report.radar_data} />
            </Box>
          </Box>

          </motion.div>

          {/* Row 2: Baseline + Suggestions */}
          <motion.div {...sectionAnim(2)}>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "2fr 3fr" }, gap: sectionGap, mb: sectionGap }}>
            <Box sx={card}>
              <Typography sx={{ fontWeight: 600, fontSize: 15, color: "#241628", mb: 2 }}>벤치마크 비교</Typography>
              <BaselineComparison category={params.category} userTitle={params.title} userTags={userTags} />
              <Typography sx={{ fontSize: 11, color: "#b6a4ba", mt: 2 }}>
                동일 카테고리 데이터와 비교
              </Typography>
            </Box>
            <Box sx={card}>
              <Typography sx={{ fontWeight: 600, fontSize: 15, color: "#241628", mb: 2 }}>개선 제안</Typography>
              <SuggestionList suggestions={report.suggestions || []} />
            </Box>
          </Box>

          </motion.div>

          {/* Row 3: Optimized content + score comparison */}
          <motion.div {...sectionAnim(3)}>
          {(report.optimized_title || report.optimized_content ||
            (report.cover_direction && (
              report.cover_direction.layout?.trim() ||
              report.cover_direction.color_scheme?.trim() ||
              report.cover_direction.text_style?.trim() ||
              (report.cover_direction.tips?.length ?? 0) > 0
            ))) && (
            <Box sx={{ ...card, mb: sectionGap }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
                <Typography sx={{ fontWeight: 600, fontSize: 15, color: "#241628" }}>최적화 방안</Typography>
                {report.optimized_title && report.optimized_content && (
                  <Button
                    size="small"
                    startIcon={<ContentCopyIcon sx={{ fontSize: 14 }} />}
                    onClick={() => {
                      const all = `제목: ${report.optimized_title}\n\n${report.optimized_content}`;
                      navigator.clipboard.writeText(all);
                      showToast("제목과 캡션 복사됨");
                    }}
                    sx={{ color: "#8f7b94", fontSize: 12, "&:hover": { color: "#d62976" } }}
                  >
                    전체 복사
                  </Button>
                )}
              </Box>
              {/* Score comparison — only show if optimized is actually higher */}
              {(showScoreComparison || rescoring) && (
                <Box sx={{
                  display: "flex", alignItems: "center", justifyContent: "center",
                  gap: 1.5, mb: 2, py: 1.5, px: 2,
                  borderRadius: "12px", bgcolor: "#fff0f6", border: "1px solid #f3b5d1",
                }}>
                  <Box sx={{ textAlign: "center" }}>
                    <Typography sx={{ fontSize: 11, color: "#8f7b94", mb: 0.25 }}>현재</Typography>
                    <Typography sx={{ fontSize: 22, fontWeight: 800, color: "#6c5773" }}>
                      {originalPreScore != null ? Math.round(originalPreScore) : Math.round(report.overall_score)}
                    </Typography>
                  </Box>
                  <ArrowForwardIcon sx={{ fontSize: 18, color: "#d62976" }} />
                  <Box sx={{ textAlign: "center" }}>
                    <Typography sx={{ fontSize: 11, color: "#d62976", mb: 0.25, fontWeight: 600 }}>최적화 후 예상</Typography>
                    {rescoring ? (
                      <Skeleton variant="text" width={40} height={32} sx={{ mx: "auto" }} />
                    ) : optimizedPreScore != null ? (
                      <Typography sx={{ fontSize: 22, fontWeight: 800, color: "#d62976" }}>
                        {Math.round(optimizedPreScore)}
                      </Typography>
                    ) : null}
                  </Box>
                  {scoreDelta != null && scoreDelta > 0 && (
                    <Box sx={{ px: 1, py: 0.4, borderRadius: "8px", bgcolor: "#ffe2ef" }}>
                      <Typography sx={{ fontSize: 12, fontWeight: 700, color: "#d62976" }}>
                        +{scoreDelta}
                      </Typography>
                    </Box>
                  )}
                </Box>
              )}

              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 1.5 }}>
                {report.optimized_title && (
                  <Box sx={{ p: 2, borderRadius: "12px", bgcolor: "#fff6fa", border: "1px solid rgba(214,41,118,0.15)", display: "flex", justifyContent: "space-between", gap: 1 }}>
                    <Box sx={{ minWidth: 0 }}>
                      <Typography sx={{ fontSize: 12, fontWeight: 600, color: "#d62976", mb: 0.5 }}>추천 제목</Typography>
                      <Typography sx={{ fontSize: 14, color: "#241628", lineHeight: 1.6 }}>{report.optimized_title}</Typography>
                    </Box>
                    <Tooltip title="복사">
                      <IconButton size="small" onClick={() => copyText(report.optimized_title || "", "제목")} sx={{ color: "#b6a4ba", flexShrink: 0 }}>
                        <ContentCopyIcon sx={{ fontSize: 15 }} />
                      </IconButton>
                    </Tooltip>
                  </Box>
                )}
                {report.optimized_content && (
                  <Box sx={{ p: 2, borderRadius: "12px", bgcolor: "#f3f0ff", border: "1px solid rgba(79,91,213,0.18)", display: "flex", justifyContent: "space-between", gap: 1 }}>
                    <Box sx={{ minWidth: 0 }}>
                      <Typography sx={{ fontSize: 12, fontWeight: 600, color: "#4f5bd5", mb: 0.5 }}>최적화 캡션</Typography>
                      <Typography sx={{ fontSize: 13, color: "#4e3a54", whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{report.optimized_content}</Typography>
                    </Box>
                    <Tooltip title="복사">
                      <IconButton size="small" onClick={() => copyText(report.optimized_content || "", "캡션")} sx={{ color: "#b6a4ba", flexShrink: 0 }}>
                        <ContentCopyIcon sx={{ fontSize: 15 }} />
                      </IconButton>
                    </Tooltip>
                  </Box>
                )}
              </Box>
              {report.cover_direction && (
                report.cover_direction.layout?.trim() ||
                report.cover_direction.color_scheme?.trim() ||
                report.cover_direction.text_style?.trim() ||
                (report.cover_direction.tips?.length ?? 0) > 0
              ) && (
                <Box sx={{ mt: 1.5, p: 2, borderRadius: "12px", bgcolor: "#fff6fa", border: "1px solid rgba(214,41,118,0.14)" }}>
                  <Typography sx={{ fontSize: 12, fontWeight: 600, color: "#8f7b94", mb: 1 }}>커버/썸네일 방향</Typography>
                  <Stack spacing={0.5}>
                    {report.cover_direction.layout?.trim() && <Typography sx={{ fontSize: 13, color: "#4e3a54" }}><strong>구도: </strong>{report.cover_direction.layout}</Typography>}
                    {report.cover_direction.color_scheme?.trim() && <Typography sx={{ fontSize: 13, color: "#4e3a54" }}><strong>색상: </strong>{report.cover_direction.color_scheme}</Typography>}
                    {report.cover_direction.text_style?.trim() && <Typography sx={{ fontSize: 13, color: "#4e3a54" }}><strong>텍스트: </strong>{report.cover_direction.text_style}</Typography>}
                    {report.cover_direction.tips?.map((tip: string, i: number) => (
                      <Typography key={i} sx={{ fontSize: 13, color: "#4e3a54" }}>· {tip}</Typography>
                    ))}
                  </Stack>
                </Box>
              )}
            </Box>
          )}

          {/* 추가 최적화 버튼: AI 최적화 제안 바로 아래 배치 */}
          {!showOptPanel ? (
            <Button
              variant="contained" fullWidth
              startIcon={<AutoFixHighIcon />}
              onClick={handleOptimize}
              sx={{
                py: 1.25, fontSize: 14, fontWeight: 700, borderRadius: "12px", mb: sectionGap,
                background: "linear-gradient(135deg, #feda75 0%, #fa7e1e 22%, #f56040 40%, #d62976 62%, #962fbf 82%, #4f5bd5 100%)",
                boxShadow: "0 6px 18px rgba(214,41,118,0.25)",
                "&:hover": { boxShadow: "0 8px 26px rgba(150,47,191,0.3)", transform: "translateY(-1px)" },
              }}
            >
              추가 최적화 방안 보기
            </Button>
          ) : (
            <Box sx={{ ...card, mb: sectionGap }}>
              <Typography sx={{ fontWeight: 700, fontSize: 15, color: "#241628", mb: 2 }}>
                최적화 방안
              </Typography>
              {optimizing && (
                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 1.5, py: 3 }}>
                  <CircularProgress size={18} sx={{ color: "#d62976" }} />
                  <Typography sx={{ fontSize: 13, color: "#6c5773" }}>생성 중...</Typography>
                </Box>
              )}
              {optimizePlans.length > 0 && (
                <Stack spacing={1.5}>
                  {optimizePlans.map((plan, i) => (
                    <Box key={i} sx={{
                      p: 2, borderRadius: "12px",
                      bgcolor: plan.recommended ? "#fff0f6" : "#fff9fc",
                      border: plan.recommended ? "1.5px solid #f3b5d1" : "1px solid rgba(214,41,118,0.12)",
                      position: "relative",
                    }}>
                      {plan.recommended && (
                        <Box sx={{ position: "absolute", top: -1, right: 12, px: 1, py: 0.25, borderRadius: "0 0 6px 6px", bgcolor: "#d62976" }}>
                          <Typography sx={{ fontSize: 10, fontWeight: 700, color: "#fff", display: "flex", alignItems: "center", gap: 0.3 }}>
                            <StarIcon sx={{ fontSize: 10 }} /> 추천
                          </Typography>
                        </Box>
                      )}
                      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1 }}>
                        <Typography sx={{ fontSize: 13, fontWeight: 700, color: "#241628" }}>{plan.strategy}</Typography>
                        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
                          <Typography sx={{ fontSize: 18, fontWeight: 800, color: plan.score_delta > 0 ? "#d62976" : "#6c5773" }}>{plan.score}</Typography>
                          {plan.score_delta > 0 && (
                            <Box sx={{ px: 0.5, py: 0.15, borderRadius: "6px", bgcolor: "#ffe2ef" }}>
                              <Typography sx={{ fontSize: 10, fontWeight: 700, color: "#d62976" }}>+{plan.score_delta}</Typography>
                            </Box>
                          )}
                        </Box>
                      </Box>
                      <Typography sx={{ fontSize: 13, fontWeight: 600, color: "#d62976", mb: 0.5 }}>{plan.optimized_title}</Typography>
                      <Typography sx={{ fontSize: 12, color: "#6c5773", lineHeight: 1.6, mb: 1,
                        display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                        {plan.optimized_content}
                      </Typography>
                      <Button size="small" onClick={() => copyText(`${plan.optimized_title}\n\n${plan.optimized_content}`, "방안")}
                        startIcon={<ContentCopyIcon sx={{ fontSize: 13 }} />}
                        sx={{ fontSize: 11, color: "#8f7b94", "&:hover": { color: "#d62976" } }}>
                        복사
                      </Button>
                    </Box>
                  ))}
                </Stack>
              )}
            </Box>
          )}

          </motion.div>

          {/* Row 4: Agent debate + Comments */}
          <motion.div {...sectionAnim(4)}>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "3fr 2fr" }, gap: sectionGap, mb: sectionGap }}>
            <Box sx={card}>
              <Typography sx={{ fontWeight: 600, fontSize: 15, color: "#241628", mb: 2 }}>전문가 진단 상세</Typography>
              <AgentDebate opinions={report.agent_opinions || []} summary={report.debate_summary || ""} timeline={report.debate_timeline || []} />
            </Box>
            <Box sx={card}>
              <Typography sx={{ fontWeight: 600, fontSize: 15, color: "#241628", mb: 2 }}>댓글 시뮬레이션</Typography>
              <SimulatedComments
                comments={report.simulated_comments || []}
                noteTitle={params.title}
                noteContent={params.content || ""}
                noteCategory={params.category}
              />
            </Box>
          </Box>

          </motion.div>

          {/* Row 5: Export */}
          <motion.div {...sectionAnim(5)}>
          <Box sx={card}>
            <DiagnoseCard report={report} title={params.title} />
          </Box>

          </motion.div>

          <motion.div {...sectionAnim(6)}>
          <Typography sx={{ textAlign: "center", fontSize: 11, color: "#b6a4ba", mt: 3 }}>
            Insta-Advisor · 참고용으로만 활용하세요 ·{" "}
            <Typography component="a" href="mailto:jwj0620@gachon.ac.kr"
              sx={{ fontSize: 11, color: "#a995af", textDecoration: "none", "&:hover": { color: "#d62976" } }}>
              문의
            </Typography>
          </Typography>
          </motion.div>
        </Box>
    </Box>
  );
}
