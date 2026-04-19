import { Box, Typography } from "@mui/material";

interface Props {
  value: string;
  onChange: (v: string) => void;
}

/* Instagram용 주요 카테고리 */
const CATEGORIES = [
  { key: "food", label: "맛집/카페" },
  { key: "fashion", label: "패션/뷰티" },
  { key: "fitness", label: "운동/건강" },
  { key: "business", label: "사업/마케팅" },
  { key: "lifestyle", label: "일상" },
  { key: "travel", label: "여행" },
  { key: "education", label: "정보/교육" },
  { key: "shop", label: "쇼핑/리뷰" },
];

export default function CategoryPicker({ value, onChange }: Props) {
  return (
    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
      {CATEGORIES.map((cat) => {
        const selected = value === cat.key;
        return (
          <Box
            key={cat.key}
            onClick={() => onChange(cat.key)}
            sx={{
              px: 1.75,
              py: 0.7,
              borderRadius: "999px",
              cursor: "pointer",
              fontSize: "0.82rem",
              fontWeight: 600,
              transition: "all 0.25s cubic-bezier(0.2,0,0.2,1)",
              userSelect: "none",
              border: "1.5px solid transparent",
              ...(selected
                ? {
                    background: "linear-gradient(135deg, #ff8fc7 0%, #ff5fa2 36%, #c06bff 70%, #7e8dff 100%)",
                    color: "#fff",
                    boxShadow: "0 6px 16px rgba(214, 87, 177, 0.28)",
                    borderColor: "rgba(255,255,255,0.34)",
                    transform: "scale(1.02)",
                  }
                : {
                    bgcolor: "rgba(255,255,255,0.88)",
                    color: "#7f5f88",
                    borderColor: "rgba(192,145,206,0.34)",
                    "&:hover": {
                      bgcolor: "#ffffff",
                      color: "#4b3552",
                      borderColor: "rgba(255,95,162,0.4)",
                      transform: "translateY(-1px)",
                      boxShadow: "0 4px 12px rgba(255,95,162,0.16)",
                    },
                    "&:active": {
                      transform: "scale(0.97)",
                    },
                  }),
            }}
          >
            <Typography sx={{ fontSize: "inherit", fontWeight: "inherit", lineHeight: 1.5 }}>
              {cat.label}
            </Typography>
          </Box>
        );
      })}
    </Box>
  );
}
