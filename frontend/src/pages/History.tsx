import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  Button,
  CircularProgress,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DeleteOutlinedIcon from "@mui/icons-material/DeleteOutlined";
import InboxOutlinedIcon from "@mui/icons-material/InboxOutlined";
import { motion } from "framer-motion";
import type { HistoryListItem } from "../utils/api";
import {
  migrateLegacyLocalStorage,
  listLocalDiagnoses,
  getLocalDiagnosis,
  deleteLocalDiagnosis,
  localRecordToListItem,
} from "../utils/localMemory";

const CATEGORY_LABEL: Record<string, string> = {
  food: "맛집/카페",
  fashion: "패션/뷰티",
  fitness: "운동/건강",
  business: "사업/마케팅",
  lifestyle: "일상",
  travel: "여행",
  education: "정보/교육",
  shop: "쇼핑/리뷰",
  tech: "테크",
  beauty: "뷰티",
  home: "리빙",
};

const GRADE_COLOR: Record<string, string> = {
  S: "#fa7e1e",
  A: "#d62976",
  B: "#4f5bd5",
  C: "#962fbf",
  D: "#c21766",
};

/** 생성 시간 역순 정렬 */
function sortListItems(a: HistoryListItem, b: HistoryListItem): number {
  const ta = new Date(
    a.created_at.includes("T") ? a.created_at : a.created_at.replace(" ", "T"),
  ).getTime();
  const tb = new Date(
    b.created_at.includes("T") ? b.created_at : b.created_at.replace(" ", "T"),
  ).getTime();
  return tb - ta;
}

/**
 * 진단 이력 페이지 (IndexedDB만, 서버 동기화 없음)
 */
export default function History() {
  const navigate = useNavigate();
  const [items, setItems] = useState<HistoryListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [navigating, setNavigating] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<HistoryListItem | null>(null);

  const fetchList = async () => {
    setLoading(true);
    try {
      await migrateLegacyLocalStorage();
      const locals = await listLocalDiagnoses();
      setItems(locals.map(localRecordToListItem).sort(sortListItems));
    } catch (e) {
      console.error("로컬 이력 읽기 실패", e);
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchList();
  }, []);

  /** 카드 클릭: IndexedDB에서 전체 보고서 읽기 후 Report 페이지로 이동 */
  const handleOpen = async (item: HistoryListItem) => {
    setNavigating(item.id);
    try {

      const rec = await getLocalDiagnosis(item.id);
      if (!rec) throw new Error("로컬 기록 없음");
      const p = rec.params;
      const title = typeof p.title === "string" ? p.title : rec.title;
      const category = typeof p.category === "string" ? p.category : rec.category;
      const content = typeof p.content === "string" ? p.content : undefined;
      const tags = p.tags;
      navigate("/report", {
        state: {
          report: rec.report,
          params: { title, category, content, tags },
          isFallback: false,
        },
      });
    } catch (e) {
      console.error("로컬 기록 열기 실패", e);
      setNavigating(null);
    }
  };

  /** 삭제 확인 (로컬 IndexedDB만) */
  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      const id = deleteTarget.id;
      await deleteLocalDiagnosis(id);
      setItems((prev) => prev.filter((i) => i.id !== id));
    } catch (e) {
      console.error("삭제 실패", e);
    }
    setDeleteTarget(null);
  };

  const formatTime = (ts: string) => {
    if (!ts) return "";
    const d = new Date(ts.includes("T") ? ts : ts.replace(" ", "T"));
    return d.toLocaleString("ko-KR", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "#fff8f8" }}>
      {/* 상단 바 */}
      <Box
        sx={{
          position: "sticky",
          top: 0,
          zIndex: 10,
          bgcolor: "rgba(255,255,255,0.86)",
          borderBottom: "1px solid rgba(214,41,118,0.12)",
          backdropFilter: "blur(8px)",
        }}
      >
        <Box
          sx={{
            maxWidth: 640,
            mx: "auto",
            px: 2,
            py: 1.5,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate("/app")}
            size="small"
            sx={{ color: "#241628" }}
          >
            홈
          </Button>
          <Box sx={{ textAlign: "center" }}>
            <Typography sx={{ fontWeight: 700, color: "#241628", fontSize: 16 }}>
              진단 이력
            </Typography>
            <Typography sx={{ fontSize: 11, color: "#8f7b94", mt: 0.25 }}>
              이 기기 브라우저에만 저장됨
            </Typography>
          </Box>
          <Box sx={{ width: 64 }} />
        </Box>
      </Box>

      <Box sx={{ maxWidth: 640, mx: "auto", px: 2, mt: 3, pb: 10 }}>
        {loading ? (
          <Box sx={{ textAlign: "center", py: 10 }}>
            <CircularProgress size={28} sx={{ color: "#d62976" }} />
            <Typography sx={{ mt: 2, color: "#8f7b94", fontSize: 14 }}>
              불러오는 중...
            </Typography>
          </Box>
        ) : items.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
          >
            <Box sx={{ textAlign: "center", py: 10 }}>
              <InboxOutlinedIcon sx={{ fontSize: 56, color: "#b6a4ba" }} />
              <Typography sx={{ mt: 1.5, color: "#8f7b94", fontSize: 14 }}>
                진단 기록이 없습니다
              </Typography>
              <Button
                variant="contained"
                disableElevation
                sx={{
                  mt: 3,
                  bgcolor: "#d62976",
                  borderRadius: "8px",
                  textTransform: "none",
                  "&:hover": { bgcolor: "#c21766" },
                }}
                onClick={() => navigate("/app")}
              >
                진단 시작
              </Button>
            </Box>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
          >
            <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
              {items.map((item) => {
                const gradeColor = GRADE_COLOR[item.grade] || "#8f7b94";
                return (
                  <Box
                    key={item.id}
                    onClick={() => !navigating && handleOpen(item)}
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1.5,
                      px: 2,
                      py: 1.5,
                      bgcolor: "rgba(255,255,255,0.9)",
                      border: "1px solid rgba(214,41,118,0.12)",
                      borderRadius: "12px",
                      cursor: navigating === item.id ? "wait" : "pointer",
                      transition: "border-color 0.15s",
                      "&:hover": { borderColor: "rgba(214,41,118,0.28)" },
                    }}
                  >
                    {/* 점수 */}
                    <Typography
                      sx={{
                        fontWeight: 800,
                        fontSize: 22,
                        lineHeight: 1,
                        color: gradeColor,
                        minWidth: 36,
                        textAlign: "center",
                        flexShrink: 0,
                      }}
                    >
                      {Math.round(item.overall_score)}
                    </Typography>

                    {/* 제목 + 태그 + 날짜 */}
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography
                        sx={{
                          fontWeight: 600,
                          fontSize: 14,
                          color: "#241628",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {item.title}
                      </Typography>
                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 1,
                          mt: 0.5,
                        }}
                      >
                        <Typography
                          component="span"
                          sx={{
                            fontSize: 11,
                            color: "#8f7b94",
                            border: "1px solid rgba(214,41,118,0.16)",
                            borderRadius: "4px",
                            px: 0.75,
                            py: 0.1,
                            lineHeight: "18px",
                          }}
                        >
                          {CATEGORY_LABEL[item.category] || item.category}
                        </Typography>
                        <Typography sx={{ fontSize: 11, color: "#8f7b94" }}>
                          {formatTime(item.created_at)}
                        </Typography>
                      </Box>
                    </Box>

                    {navigating === item.id && (
                      <CircularProgress size={16} sx={{ color: "#d62976" }} />
                    )}

                    {/* 삭제 버튼 */}
                    <IconButton
                      size="small"
                      sx={{
                        color: "#b6a4ba",
                        flexShrink: 0,
                        "&:hover": { color: "#d62976" },
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteTarget(item);
                      }}
                    >
                      <DeleteOutlinedIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                  </Box>
                );
              })}
            </Box>
          </motion.div>
        )}
      </Box>

      {/* 삭제 확인 다이얼로그 */}
      <Dialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        slotProps={{
          paper: {
            sx: {
              borderRadius: "12px",
              maxWidth: 360,
            },
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 700, fontSize: 16, color: "#241628" }}>
          기록 삭제
        </DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ fontSize: 14, color: "#8f7b94" }}>
            「{deleteTarget?.title}」의 진단 기록을 삭제할까요? 이 작업은 되돌릴 수 없습니다.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            onClick={() => setDeleteTarget(null)}
            sx={{ color: "#8f7b94", textTransform: "none" }}
          >
            취소
          </Button>
          <Button
            onClick={handleDelete}
            variant="contained"
            disableElevation
            sx={{
              bgcolor: "#d62976",
              textTransform: "none",
              borderRadius: "8px",
              "&:hover": { bgcolor: "#c21766" },
            }}
          >
            삭제
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
