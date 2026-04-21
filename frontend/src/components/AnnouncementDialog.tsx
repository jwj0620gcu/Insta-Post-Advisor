import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  Box,
  Typography,
  Button,
  IconButton,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import FavoriteIcon from "@mui/icons-material/Favorite";
import GitHubIcon from "@mui/icons-material/GitHub";
import EmailOutlinedIcon from "@mui/icons-material/EmailOutlined";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import WhatshotIcon from "@mui/icons-material/Whatshot";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import CodeIcon from "@mui/icons-material/Code";

const STORAGE_KEY = "insta-advisor_announcement_seen_v1";

const WaveSvg = () => (
  <svg
    viewBox="0 0 600 80"
    preserveAspectRatio="none"
    style={{ position: "absolute", bottom: -1, left: 0, width: "100%", height: 48 }}
  >
    <path d="M0 40 C150 80 350 0 600 40 L600 80 L0 80Z" fill="#fff" />
  </svg>
);

function LinkCard({
  icon,
  label,
  sublabel,
  href,
}: {
  icon: React.ReactNode;
  label: string;
  sublabel: string;
  href: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      style={{ textDecoration: "none", flex: 1, minWidth: 0 }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          px: 2,
          py: 1.5,
          borderRadius: "14px",
          border: "1px solid rgba(214,41,118,0.14)",
          background: "#fff8fb",
          transition: "all 0.22s ease",
          cursor: "pointer",
          "&:hover": {
            borderColor: "rgba(214,41,118,0.28)",
            background: "rgba(214,41,118,0.07)",
            transform: "translateY(-2px)",
            boxShadow: "0 4px 16px rgba(214,41,118,0.14)",
          },
        }}
      >
        <Box
          sx={{
            width: 38,
            height: 38,
            borderRadius: "10px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "linear-gradient(135deg, rgba(214,41,118,0.14), rgba(79,91,213,0.14))",
            flexShrink: 0,
          }}
        >
          {icon}
        </Box>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography
            sx={{ fontWeight: 700, fontSize: "0.82rem", color: "#241628", lineHeight: 1.3 }}
          >
            {label}
          </Typography>
          <Typography
            sx={{
              fontSize: "0.7rem",
              color: "#8f7b94",
              fontWeight: 500,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {sublabel}
          </Typography>
        </Box>
        <OpenInNewIcon sx={{ fontSize: 14, color: "#b6a4ba", flexShrink: 0 }} />
      </Box>
    </a>
  );
}

const STATS = [
  {
    icon: <WhatshotIcon sx={{ fontSize: 20, color: "#d62976" }} />,
    val: "5-Agent",
    label: "멀티에이전트",
  },
  {
    icon: <TrendingUpIcon sx={{ fontSize: 20, color: "#f56040" }} />,
    val: "인스타그램",
    label: "한국어 특화",
  },
  {
    icon: <CodeIcon sx={{ fontSize: 20, color: "#962fbf" }} />,
    val: "오픈소스",
    label: "MIT License",
  },
];

export default function AnnouncementDialog() {
  const [open, setOpen] = useState(false);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));

  useEffect(() => {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) {
        const timer = setTimeout(() => setOpen(true), 800);
        return () => clearTimeout(timer);
      }
    } catch {
      /* localStorage unavailable */
    }
  }, []);

  const handleClose = () => {
    setOpen(false);
  };

  const handleNeverShow = () => {
    setOpen(false);
    try {
      localStorage.setItem(STORAGE_KEY, Date.now().toString());
    } catch {
      /* ignore */
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      fullScreen={isMobile}
      slotProps={{
        paper: {
          sx: {
            borderRadius: isMobile ? 0 : "24px",
            overflow: "hidden",
            maxHeight: isMobile ? "100%" : "92vh",
            boxShadow: "0 24px 80px rgba(214,41,118,0.2)",
          },
        },
      }}
    >
      {/* ───── Hero ───── */}
      <Box
        sx={{
          background: "linear-gradient(145deg, #d62976 0%, #f56040 40%, #962fbf 100%)",
          px: { xs: 3, sm: 4 },
          pt: { xs: 4, sm: 5 },
          pb: { xs: 5, sm: 6 },
          position: "relative",
          textAlign: "center",
          overflow: "hidden",
        }}
      >
        <Box
          sx={{
            position: "absolute", width: 260, height: 260, borderRadius: "50%",
            background: "rgba(255,255,255,0.07)", top: -100, right: -60,
          }}
        />
        <Box
          sx={{
            position: "absolute", width: 160, height: 160, borderRadius: "50%",
            background: "rgba(255,255,255,0.05)", bottom: 10, left: -50,
          }}
        />
        <Box
          sx={{
            position: "absolute", width: 80, height: 80, borderRadius: "50%",
            background: "rgba(255,255,255,0.06)", top: "30%", left: "20%",
          }}
        />
        <WaveSvg />

        <IconButton
          onClick={handleClose}
          size="small"
          sx={{
            position: "absolute", top: 12, right: 12,
            color: "rgba(255,255,255,0.7)",
            backdropFilter: "blur(8px)",
            background: "rgba(255,255,255,0.1)",
            "&:hover": { color: "#fff", background: "rgba(255,255,255,0.2)" },
          }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>

        <Box sx={{ position: "relative", zIndex: 1 }}>
          <Box
            sx={{
              width: 56, height: 56, borderRadius: "16px",
              background: "rgba(255,255,255,0.2)",
              backdropFilter: "blur(12px)",
              display: "flex", alignItems: "center", justifyContent: "center",
              mx: "auto", mb: 2,
            }}
          >
            <FavoriteIcon sx={{ color: "#fff", fontSize: 28 }} />
          </Box>
          <Typography
            sx={{
              color: "#fff", fontWeight: 800,
              fontSize: { xs: "1.35rem", sm: "1.5rem" },
              letterSpacing: "-0.5px", mb: 1,
            }}
          >
            Insta-Advisor에 오신 것을 환영합니다
          </Typography>
          <Typography
            sx={{
              color: "rgba(255,255,255,0.88)",
              fontSize: { xs: "0.85rem", sm: "0.9rem" },
              lineHeight: 1.7, maxWidth: 380, mx: "auto",
            }}
          >
            한국 인스타그램 특화 · 5-Agent 진단 · 완전 무료
          </Typography>
        </Box>
      </Box>

      {/* ───── Content ───── */}
      <DialogContent
        sx={{
          px: { xs: 2.5, sm: 3.5 },
          py: { xs: 2.5, sm: 3 },
          "&::-webkit-scrollbar": { width: 4 },
          "&::-webkit-scrollbar-thumb": { background: "rgba(214,41,118,0.28)", borderRadius: 2 },
        }}
      >
        {/* Stats row */}
        <Box sx={{ display: "flex", gap: { xs: 1, sm: 1.5 }, mb: 2.5 }}>
          {STATS.map((s) => (
            <Box
              key={s.label}
              sx={{
                flex: 1, textAlign: "center",
                py: { xs: 1.2, sm: 1.5 }, px: 0.5,
                borderRadius: "14px", background: "#fff",
                border: "1px solid rgba(214,41,118,0.14)",
                boxShadow: "0 2px 8px rgba(214,41,118,0.08)",
              }}
            >
              <Box sx={{ display: "flex", justifyContent: "center", mb: 0.5 }}>
                {s.icon}
              </Box>
              <Typography
                sx={{
                  fontWeight: 800,
                  fontSize: { xs: "0.85rem", sm: "1rem" },
                  color: "#d62976", lineHeight: 1.3,
                }}
              >
                {s.val}
              </Typography>
              <Typography
                sx={{
                  fontSize: "0.65rem", color: "#a995af", mt: 0.2,
                  fontWeight: 600, letterSpacing: "0.3px",
                }}
              >
                {s.label}
              </Typography>
            </Box>
          ))}
        </Box>

        {/* Links */}
        <Box
          sx={{
            display: "flex", gap: 1.5, mb: 2.5,
            flexDirection: { xs: "column", sm: "row" },
          }}
        >
          <LinkCard
            icon={<GitHubIcon sx={{ fontSize: 20, color: "#594560" }} />}
            label="오픈소스 저장소"
            sublabel="github.com/cocone-m/insta-advisor"
            href="https://github.com"
          />
        </Box>

        {/* About note */}
        <Box
          sx={{
            background: "linear-gradient(135deg, #fff2de, #ffe9f3)",
            border: "1px solid rgba(214,41,118,0.18)",
            borderRadius: "14px", px: 2.5, py: 2, mb: 2.5,
          }}
        >
          <Typography
            sx={{ fontSize: "0.85rem", color: "#5e4965", lineHeight: 1.75, fontWeight: 500 }}
          >
            인스타그램 게시물을 올리면 5개 에이전트가 점수를 매기고 캡션·해시태그·커버 개선안을 제안합니다.
          </Typography>
        </Box>

        {/* Contact email */}
        <Box
          sx={{
            display: "flex", alignItems: "center", justifyContent: "center",
            gap: 1, py: 1.2, borderRadius: "12px",
            background: "rgba(214,41,118,0.07)",
            border: "1px solid rgba(214,41,118,0.14)", mb: 3,
          }}
        >
          <EmailOutlinedIcon sx={{ fontSize: 16, color: "#d62976" }} />
          <Typography sx={{ fontSize: "0.82rem", color: "#6c5773" }}>
            문의{" "}
            <a
              href="mailto:jwj0620@gachon.ac.kr"
              style={{ color: "#d62976", fontWeight: 700, textDecoration: "none" }}
            >
              jwj0620@gachon.ac.kr
            </a>
          </Typography>
        </Box>

        {/* CTA */}
        <Box sx={{ display: "flex", gap: 1.5 }}>
          <Button
            variant="outlined"
            size="large"
            onClick={handleNeverShow}
            sx={{
              flex: 1, py: 1.5, fontSize: "0.85rem", fontWeight: 600,
              borderRadius: "14px", textTransform: "none",
              borderColor: "rgba(214,41,118,0.3)", color: "#a07aaa",
              "&:hover": {
                borderColor: "rgba(214,41,118,0.6)",
                background: "rgba(214,41,118,0.05)",
              },
            }}
          >
            다시 안보기
          </Button>
          <Button
            variant="contained"
            color="primary"
            size="large"
            onClick={handleClose}
            sx={{
              flex: 2, py: 1.5, fontSize: "0.95rem", fontWeight: 700,
              borderRadius: "14px", textTransform: "none",
            }}
          >
            시작하기
          </Button>
        </Box>
      </DialogContent>
    </Dialog>
  );
}
