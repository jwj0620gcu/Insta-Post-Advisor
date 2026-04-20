import { Box, Typography, Stack } from "@mui/material";

interface Suggestion {
  priority: number;
  description: string;
  expected_impact: string;
}

interface Props {
  suggestions: Suggestion[];
}

const PRIORITY_COLOR: Record<number, string> = {
  1: "#d62976",
  2: "#fa7e1e",
  3: "#4f5bd5",
};

export default function SuggestionList({ suggestions }: Props) {
  if (!suggestions.length) {
    return <Typography sx={{ fontSize: 14, color: "#8f7b94" }}>개선 제안이 없습니다</Typography>;
  }

  const sorted = [...suggestions].sort((a, b) => a.priority - b.priority);

  return (
    <Stack spacing={1.5}>
      {sorted.map((s, i) => {
        const color = PRIORITY_COLOR[s.priority] || PRIORITY_COLOR[3];
        return (
          <Box
            key={i}
            sx={{
              borderLeft: `3px solid ${color}`,
              pl: { xs: 1.5, sm: 2 },
              py: 0.75,
              borderRadius: "0 10px 10px 0",
              bgcolor: `${color}08`,
              transition: "background-color 0.2s ease",
              "&:hover": { bgcolor: `${color}12` },
            }}
          >
            <Typography sx={{ fontSize: { xs: 13, sm: 14 }, color: "#4e3a54", lineHeight: 1.6 }}>
              {s.description}
            </Typography>
            {s.expected_impact && (
              <Typography sx={{ fontSize: { xs: 12, sm: 13 }, color: "#8f7b94", mt: 0.25 }}>
                {s.expected_impact}
              </Typography>
            )}
          </Box>
        );
      })}
    </Stack>
  );
}
