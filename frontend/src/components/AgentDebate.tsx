import { useState } from "react";
import { Box, Typography, Stack } from "@mui/material";
import { AnimatePresence, motion } from "framer-motion";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import type { AgentOpinion, DebateEntry } from "../utils/api";

interface Props {
  opinions: AgentOpinion[];
  summary: string;
  timeline?: DebateEntry[];
}

const AGENT_COLORS: Record<string, { bg: string; accent: string; text: string }> = {
  "캡션 분석가": { bg: "#fff1f7", accent: "#d62976", text: "#b61f63" },
  "비주얼 진단가": { bg: "#f6efff", accent: "#962fbf", text: "#7f25a3" },
  "성장 전략가": { bg: "#fff5e8", accent: "#fa7e1e", text: "#d05f0f" },
  "오디언스 시뮬레이터": { bg: "#eef0ff", accent: "#4f5bd5", text: "#3a46bb" },
  "종합 심사관": { bg: "#ffeef4", accent: "#f56040", text: "#cf4b30" },
};

const KIND_STYLE: Record<string, { color: string; bg: string; label: string }> = {
  agree: { color: "#d62976", bg: "#fff0f6", label: "동의" },
  rebuttal: { color: "#c21766", bg: "#ffe8f1", label: "반박" },
  add: { color: "#4f5bd5", bg: "#eef0ff", label: "보완" },
};

function agentInitial(name: string): string {
  return name.charAt(0) || "?";
}

export default function AgentDebate({ opinions, summary, timeline }: Props) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [showAllTimeline, setShowAllTimeline] = useState(false);

  return (
    <Stack spacing={2}>
      {summary && (
        <Box sx={{ bgcolor: "rgba(214,41,118,0.06)", borderRadius: "10px", px: 2, py: 1.5 }}>
          <Typography sx={{ fontSize: 13, color: "#594560", lineHeight: 1.7 }}>{summary}</Typography>
        </Box>
      )}

      {/* Agent opinion cards */}
      {opinions.map((op, idx) => {
        const isOpen = expandedIdx === idx;
        const colors = AGENT_COLORS[op.agent_name] || { bg: "#f5f2f7", accent: "#7a6381", text: "#413348" };
        const scoreColor = op.score >= 75 ? "#d62976" : op.score >= 50 ? "#962fbf" : "#c21766";
        return (
          <Box key={idx}>
            <Box onClick={() => setExpandedIdx(isOpen ? null : idx)} sx={{
              display: "flex", alignItems: "center", gap: { xs: 1, sm: 1.25 },
              px: { xs: 1.25, sm: 1.5 }, py: 1.25, cursor: "pointer",
              borderRadius: isOpen ? "12px 12px 0 0" : "12px",
              bgcolor: colors.bg, border: `1px solid ${colors.accent}20`,
              "&:hover": { bgcolor: `${colors.accent}10` },
            }}>
              <Box sx={{ width: 32, height: 32, borderRadius: "8px", flexShrink: 0,
                bgcolor: colors.accent, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Typography sx={{ color: "#fff", fontSize: 13, fontWeight: 700 }}>{agentInitial(op.agent_name)}</Typography>
              </Box>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{ fontWeight: 600, fontSize: 13, color: "#241628" }}>{op.agent_name}</Typography>
                <Typography sx={{ fontSize: 11, color: "#8f7b94" }}>{op.dimension}</Typography>
              </Box>
              <Typography sx={{ fontWeight: 800, fontSize: { xs: 14, sm: 16 }, color: scoreColor }}>{Math.round(op.score)}</Typography>
              <ExpandMoreIcon sx={{ color: "#af9ab4", fontSize: 18, transform: isOpen ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
            </Box>
            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }} style={{ overflow: "hidden" }}>
                  <Box sx={{ px: 2, py: 1.5, border: `1px solid ${colors.accent}20`, borderTop: "none", borderRadius: "0 0 12px 12px", bgcolor: "#fff" }}>
                    <Stack spacing={1.25}>
                      {op.issues.length > 0 && (
                        <Box>
                          <Typography sx={{ fontSize: 11, fontWeight: 600, color: "#c21766", mb: 0.5 }}>문제점</Typography>
                          {op.issues.map((issue, i) => (
                            <Typography key={i} sx={{ fontSize: 12, color: "#594560", lineHeight: 1.6, pl: 1, borderLeft: "2px solid #f4b4d0", mb: 0.5 }}>{issue}</Typography>
                          ))}
                        </Box>
                      )}
                      {op.suggestions.length > 0 && (
                        <Box>
                          <Typography sx={{ fontSize: 11, fontWeight: 600, color: colors.text, mb: 0.5 }}>개선안</Typography>
                          {op.suggestions.map((sug, i) => (
                            <Typography key={i} sx={{ fontSize: 12, color: "#594560", lineHeight: 1.6, pl: 1, borderLeft: `2px solid ${colors.accent}40`, mb: 0.5 }}>{sug}</Typography>
                          ))}
                        </Box>
                      )}
                    </Stack>
                  </Box>
                </motion.div>
              )}
            </AnimatePresence>
          </Box>
        );
      })}

      {/* Debate timeline — simple list, no carousel, no auto-scroll */}
      {timeline && timeline.length > 0 && (
        <Box>
          <Typography sx={{ fontWeight: 600, fontSize: 14, color: "#241628", mb: 1.5 }}>
            토론 과정 · {timeline.length}개
          </Typography>
          <Stack spacing={1}>
            {(showAllTimeline ? timeline : timeline.slice(0, 3)).map((entry, i) => {
              const kind = KIND_STYLE[entry.kind] || KIND_STYLE.add;
              const colors = AGENT_COLORS[entry.agent_name] || { accent: "#7a6381", bg: "#f5f2f7", text: "#413348" };
              return (
                <Box key={i} sx={{ display: "flex", gap: 1, alignItems: "flex-start" }}>
                  <Box sx={{
                    width: 24, height: 24, borderRadius: "6px", flexShrink: 0, mt: 0.25,
                    bgcolor: colors.accent, display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <Typography sx={{ color: "#fff", fontSize: 10, fontWeight: 700 }}>{agentInitial(entry.agent_name)}</Typography>
                  </Box>
                  <Box sx={{
                    flex: 1, minWidth: 0, px: 1.5, py: 1,
                    borderRadius: "4px 10px 10px 10px",
                    bgcolor: kind.bg, border: `1px solid ${kind.color}15`,
                  }}>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 0.25 }}>
                      <Typography sx={{ fontSize: 11, fontWeight: 600, color: "#241628" }}>{entry.agent_name}</Typography>
                      <Box sx={{ fontSize: 9, fontWeight: 700, color: kind.color, bgcolor: `${kind.color}12`, borderRadius: "4px", px: 0.5, py: 0.1 }}>
                        {kind.label}
                      </Box>
                    </Box>
                    <Typography sx={{ fontSize: 12, color: "#594560", lineHeight: 1.6 }}>{entry.text}</Typography>
                  </Box>
                </Box>
              );
            })}
          </Stack>
          {timeline.length > 3 && (
            <Typography onClick={() => setShowAllTimeline(!showAllTimeline)}
              sx={{ fontSize: 12, color: "#8f7b94", mt: 1, cursor: "pointer", "&:hover": { color: "#d62976" } }}>
              {showAllTimeline ? "접기" : `전체 ${timeline.length}개 펼치기`}
            </Typography>
          )}
        </Box>
      )}
    </Stack>
  );
}
