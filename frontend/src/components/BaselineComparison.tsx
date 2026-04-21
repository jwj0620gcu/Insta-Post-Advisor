import { useEffect, useState } from "react";
import { Box, Typography, Stack } from "@mui/material";
import { getBaseline } from "../utils/api";

interface Props {
  category: string;
  userTitle: string;
  userTags: string[];
}

interface Metric {
  label: string;
  userValue: number;
  avgValue: number;
  viralValue?: number;
  unit: string;
}

export default function BaselineComparison({ category, userTitle, userTags }: Props) {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const raw = await getBaseline(category);
        if (cancelled) return;
        // API 응답이 { category, stats: { ... } } 형태이면 stats만 추출
        const data = raw.stats || raw;

        const m: Metric[] = [
          {
            label: "캡션 길이",
            userValue: userTitle.length,
            avgValue: Math.round(data.avg_title_length || 0),
            viralValue: Math.round(data.viral_avg_title_length || 0),
            unit: "자",
          },
          {
            label: "해시태그 수",
            userValue: userTags.length,
            avgValue: Math.round(data.avg_tag_count || 0),
            unit: "개",
          },
        ];

        if (data.viral_rate !== undefined) {
          m.push({
            label: "카테고리 바이럴율",
            userValue: 0,
            avgValue: Math.round(data.viral_rate * 10) / 10,
            unit: "%",
          });
        }

        setMetrics(m);
      } catch {
        // baseline not available
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [category, userTitle, userTags]);

  if (loading || metrics.length === 0) return null;

  const maxVal = Math.max(...metrics.flatMap((m) => [m.userValue, m.avgValue, m.viralValue ?? 0])) * 1.2 || 100;

  return (
    <Stack spacing={2}>
      {metrics.filter((m) => m.userValue > 0).map((m) => (
        <Box key={m.label}>
          <Typography sx={{ fontSize: 13, fontWeight: 500, color: "#4e3a54", mb: 1 }}>
            {m.label}
          </Typography>
          <Stack spacing={0.75}>
            <BarRow label="내 게시물" value={m.userValue} maxVal={maxVal} color="#d62976" unit={m.unit} />
            <BarRow label="카테고리 평균" value={m.avgValue} maxVal={maxVal} color="#b9abd5" unit={m.unit} />
            {m.viralValue !== undefined && m.viralValue > 0 && (
              <BarRow label="바이럴 평균" value={m.viralValue} maxVal={maxVal} color="#fa7e1e" unit={m.unit} />
            )}
          </Stack>
        </Box>
      ))}
    </Stack>
  );
}

function BarRow({ label, value, maxVal, color, unit }: {
  label: string; value: number; maxVal: number; color: string; unit: string;
}) {
  const pct = Math.min((value / maxVal) * 100, 100);
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
      <Typography sx={{ fontSize: { xs: 10, sm: 11 }, color: "#8f7b94", width: { xs: 48, sm: 56 }, flexShrink: 0 }}>
        {label}
      </Typography>
      <Box sx={{ flex: 1, height: 8, bgcolor: "rgba(214,41,118,0.08)", borderRadius: 4, overflow: "hidden" }}>
        <Box sx={{ height: "100%", bgcolor: color, borderRadius: 4, width: `${pct}%`, transition: "width 0.8s ease" }} />
      </Box>
      <Typography sx={{ fontSize: 12, fontWeight: 600, color: "#241628", width: { xs: 36, sm: 40 }, textAlign: "right", flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>
        {value}{unit}
      </Typography>
    </Box>
  );
}
