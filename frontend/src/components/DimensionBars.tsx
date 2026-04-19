import { useEffect, useRef, useState } from "react";
import { Box, Typography, Stack } from "@mui/material";

interface Props {
  data: Record<string, number>;
}

const DIMENSIONS = [
  { key: "content", label: "콘텐츠 품질", color: "#d62976" },
  { key: "visual", label: "시각 완성도", color: "#962fbf" },
  { key: "growth", label: "성장 전략", color: "#fa7e1e" },
  { key: "user_reaction", label: "오디언스 반응", color: "#4f5bd5" },
  { key: "overall", label: "종합 점수", color: "#f56040" },
];

function scoreLabel(score: number): string {
  if (score >= 90) return "우수";
  if (score >= 75) return "양호";
  if (score >= 60) return "보통";
  if (score >= 40) return "미흡";
  return "부진";
}

export default function DimensionBars({ data }: Props) {
  const [animated, setAnimated] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(true), 200);
    return () => clearTimeout(timer);
  }, []);

  return (
    <Stack ref={ref} spacing={2}>
      {DIMENSIONS.map((dim) => {
        const score = Math.round(data[dim.key] ?? 0);
        return (
          <Box key={dim.key}>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", mb: 0.5 }}>
              <Typography sx={{ fontSize: 13, fontWeight: 500, color: "#4e3a54" }}>
                {dim.label}
              </Typography>
              <Box sx={{ display: "flex", alignItems: "baseline", gap: 0.5 }}>
                <Typography sx={{ fontSize: 15, fontWeight: 700, color: dim.color, fontVariantNumeric: "tabular-nums" }}>
                  {score}
                </Typography>
                <Typography sx={{ fontSize: 11, color: "#a28ca9" }}>
                  {scoreLabel(score)}
                </Typography>
              </Box>
            </Box>
            <Box sx={{ height: 7, bgcolor: "rgba(214,41,118,0.09)", borderRadius: 4, overflow: "hidden" }}>
              <Box
                sx={{
                  height: "100%",
                  bgcolor: dim.color,
                  borderRadius: 4,
                  width: animated ? `${score}%` : "0%",
                  transition: "width 1.2s cubic-bezier(0.2,0,0.2,1)",
                  boxShadow: animated ? `0 0 8px ${dim.color}30` : "none",
                }}
              />
            </Box>
          </Box>
        );
      })}
    </Stack>
  );
}
