import { useEffect, useRef, useState } from "react";
import { Box, Typography } from "@mui/material";

interface Props {
  score: number;
  grade: string;
  title: string;
}

const GRADE_CONFIG: Record<string, { bg: string; color: string; label: string }> = {
  S: { bg: "#fff2de", color: "#fa7e1e", label: "바이럴 가능성" },
  A: { bg: "#ffe7f2", color: "#d62976", label: "우수 성과" },
  B: { bg: "#eee8ff", color: "#4f5bd5", label: "평균 수준" },
  C: { bg: "#f4e8ff", color: "#962fbf", label: "개선 필요" },
  D: { bg: "#ffe3ea", color: "#c21766", label: "집중 개선" },
};

export default function ScoreCard({ score, grade, title }: Props) {
  const config = GRADE_CONFIG[grade] || GRADE_CONFIG.B;
  const [display, setDisplay] = useState(0);
  const rafRef = useRef(0);

  useEffect(() => {
    const target = Math.round(score);
    if (target <= 0) { setDisplay(target); return; }

    const duration = 1200;
    const start = performance.now();

    const tick = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(eased * target));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [score]);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", py: 2.5, gap: 1 }}>
      <Typography
        sx={{
          fontSize: { xs: 52, md: 64 },
          fontWeight: 800,
          lineHeight: 1,
          fontVariantNumeric: "tabular-nums",
          background: `linear-gradient(135deg, ${config.color} 0%, #4f5bd5 100%)`,
          backgroundClip: "text",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}
      >
        {display}
      </Typography>

      <Box sx={{ display: "inline-flex", alignItems: "center", gap: 1 }}>
        <Box sx={{
          px: 1.5, py: 0.4, borderRadius: "10px", bgcolor: config.bg,
          boxShadow: `0 0 12px ${config.color}18`,
        }}>
          <Typography sx={{ fontSize: 14, fontWeight: 800, color: config.color, letterSpacing: "0.02em" }}>
            {grade}
          </Typography>
        </Box>
        <Typography sx={{ fontSize: 13, color: "#715f79", fontWeight: 500 }}>
          {config.label}
        </Typography>
      </Box>

      <Typography
        sx={{
          fontSize: 13, color: "#9e8ca5", mt: 0.25,
          maxWidth: 360, textAlign: "center",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}
      >
        {title}
      </Typography>
    </Box>
  );
}
