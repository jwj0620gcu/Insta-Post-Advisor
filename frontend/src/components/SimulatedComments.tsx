import { useState, useCallback } from "react";
import { Box, Typography, Button, CircularProgress } from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import type { SimulatedComment, CommentWithReplies } from "../utils/api";
import { generateComments } from "../utils/api";

interface Props {
  comments: SimulatedComment[];
  noteTitle?: string;
  noteContent?: string;
  noteCategory?: string;
}

/* ── Avatar colors ── */
const AVATAR_COLORS = [
  "#d62976", "#fa7e1e", "#f56040", "#962fbf", "#4f5bd5",
  "#c21766", "#b23fae", "#e66a2d", "#6a6fe5", "#ad2a99",
];

function avatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function avatarInitial(name: string): string {
  return name.charAt(0) || "?";
}

/* ── State types ── */
interface CommentState extends CommentWithReplies {
  _likes: number;
  _liked: boolean;
  _showReplies: boolean;
  _replies: Array<SimulatedComment & { _likes: number; _liked: boolean }>;
}

function toCommentState(c: SimulatedComment | CommentWithReplies): CommentState {
  const replies = ("replies" in c && Array.isArray(c.replies) ? c.replies : []).map((r) => ({
    ...r,
    _likes: r.likes ?? Math.floor(Math.random() * 80),
    _liked: false,
  }));
  return {
    ...c,
    _likes: c.likes ?? Math.floor(Math.random() * 200),
    _liked: false,
    _showReplies: replies.length > 0,
    _replies: replies,
  };
}

export default function SimulatedComments({ comments: initial, noteTitle = "", noteContent = "", noteCategory = "food" }: Props) {
  const [comments, setComments] = useState<CommentState[]>(() => (initial || []).map(toCommentState));
  const [loading, setLoading] = useState(false);

  const toggleLike = useCallback((idx: number) => {
    setComments((prev) => prev.map((c, i) =>
      i === idx ? { ...c, _liked: !c._liked, _likes: c._liked ? c._likes - 1 : c._likes + 1 } : c
    ));
  }, []);

  const toggleReplyLike = useCallback((ci: number, ri: number) => {
    setComments((prev) => prev.map((c, i) => {
      if (i !== ci) return c;
      const nr = c._replies.map((r, j) =>
        j === ri ? { ...r, _liked: !r._liked, _likes: r._liked ? r._likes - 1 : r._likes + 1 } : r
      );
      return { ...c, _replies: nr };
    }));
  }, []);

  const toggleShowReplies = useCallback((idx: number) => {
    setComments((prev) => prev.map((c, i) =>
      i === idx ? { ...c, _showReplies: !c._showReplies } : c
    ));
  }, []);

  const handleLoadMore = async () => {
    setLoading(true);
    try {
      const nc = await generateComments({ title: noteTitle, content: noteContent, category: noteCategory, existing_count: comments.length });
      setComments((prev) => [...prev, ...nc.map(toCommentState)]);
    } catch { /* ignore */ } finally { setLoading(false); }
  };

  if (!comments.length) return <Typography sx={{ fontSize: 14, color: "#8f7b94" }}>시뮬레이션 댓글이 없습니다</Typography>;

  const totalLikes = comments.reduce((sum, c) => sum + (c._likes || 0), 0);

  return (
    <Box>
      {/* AI 예상 요약 */}
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 0.5, mb: 1.5, pb: 1, borderBottom: "1px solid rgba(214,41,118,0.12)" }}>
        <Typography sx={{ fontSize: { xs: 10, sm: 11 }, color: "#8f7b94" }}>
          예상 댓글 {comments.length}개
        </Typography>
        <Typography sx={{ fontSize: { xs: 10, sm: 11 }, color: "#d62976", fontWeight: 600 }}>
          예상 총 좋아요 {totalLikes.toLocaleString()}
        </Typography>
      </Box>

      {comments.map((c, i) => (
        <Box key={`${c.username}-${i}`} sx={{ py: 1.25, borderBottom: "1px solid rgba(214,41,118,0.08)", "&:last-child": { borderBottom: "none" } }}>
          {/* Main comment */}
          <Box sx={{ display: "flex", gap: 1, alignItems: "flex-start" }}>
            {/* Color avatar */}
            <Box sx={{
              width: { xs: 28, sm: 32 }, height: { xs: 28, sm: 32 }, borderRadius: "50%", flexShrink: 0,
              bgcolor: avatarColor(c.username),
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Typography sx={{ color: "#fff", fontSize: 13, fontWeight: 700 }}>
                {avatarInitial(c.username)}
              </Typography>
            </Box>

            <Box sx={{ flex: 1, minWidth: 0 }}>
              {/* Name + meta */}
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, flexWrap: "wrap" }}>
                <Typography sx={{ fontWeight: 600, fontSize: 13, color: "#241628" }}>
                  {c.username}
                </Typography>
                {c.is_author && (
                  <Box sx={{ px: 0.5, py: 0.1, borderRadius: "4px", bgcolor: "#ffe9f3" }}>
                    <Typography sx={{ fontSize: 9, fontWeight: 700, color: "#d62976" }}>작성자</Typography>
                  </Box>
                )}
                {c.ip_location && (
                  <Typography sx={{ fontSize: 10, color: "#b6a4ba" }}>{c.ip_location}</Typography>
                )}
              </Box>

              {/* Comment text */}
              <Typography sx={{ fontSize: 13, color: "#4e3a54", lineHeight: 1.6, mt: 0.25 }}>
                {c.comment}
              </Typography>

              {/* Actions row */}
              <Box sx={{ display: "flex", alignItems: "center", gap: 2, mt: 0.5 }}>
                <Typography sx={{ fontSize: 10, color: "#b6a4ba" }}>
                  {c.time_ago || "방금"}
                </Typography>
                <Box
                  onClick={() => toggleLike(i)}
                  sx={{
                    display: "flex", alignItems: "center", gap: 0.3, cursor: "pointer", userSelect: "none",
                    color: c._liked ? "#d62976" : "#b6a4ba",
                    "&:hover": { color: c._liked ? "#c21766" : "#8f7b94" },
                    transition: "color 0.15s",
                  }}
                >
                  <HeartIcon filled={c._liked} size={13} />
                  <Typography sx={{ fontSize: 11, fontWeight: 500 }}>{c._likes || ""}</Typography>
                </Box>
                {c._replies.length > 0 && (
                  <Typography
                    onClick={() => toggleShowReplies(i)}
                    sx={{ fontSize: 11, color: "#8f7b94", cursor: "pointer", "&:hover": { color: "#d62976" } }}
                  >
                    {c._showReplies ? "접기" : `${c._replies.length}개 댓글`}
                  </Typography>
                )}
              </Box>

              {/* Replies */}
              {c._showReplies && c._replies.length > 0 && (
                <Box sx={{ mt: 1, pl: 1, borderLeft: "2px solid rgba(214,41,118,0.16)" }}>
                  {c._replies.map((r, j) => (
                    <Box key={j} sx={{ py: 0.75 }}>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                        <Box sx={{
                          width: 20, height: 20, borderRadius: "50%",
                          bgcolor: avatarColor(r.username),
                          display: "flex", alignItems: "center", justifyContent: "center",
                        }}>
                          <Typography sx={{ color: "#fff", fontSize: 9, fontWeight: 700 }}>
                            {avatarInitial(r.username)}
                          </Typography>
                        </Box>
                        <Typography sx={{ fontSize: 12, fontWeight: 600, color: "#241628" }}>
                          {r.username}
                        </Typography>
                        {r.is_author && (
                          <Box sx={{ px: 0.4, py: 0.05, borderRadius: "3px", bgcolor: "#ffe9f3" }}>
                            <Typography sx={{ fontSize: 8, fontWeight: 700, color: "#d62976" }}>작성자</Typography>
                          </Box>
                        )}
                      </Box>
                      <Typography sx={{ fontSize: 12, color: "#594560", lineHeight: 1.5, mt: 0.2, pl: 3.25 }}>
                        {r.comment}
                      </Typography>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mt: 0.3, pl: 3.25 }}>
                        <Typography sx={{ fontSize: 10, color: "#b6a4ba" }}>{r.time_ago || "방금"}</Typography>
                        <Box onClick={() => toggleReplyLike(i, j)}
                          sx={{ display: "inline-flex", alignItems: "center", gap: 0.3, cursor: "pointer",
                            color: r._liked ? "#d62976" : "#b6a4ba", "&:hover": { color: r._liked ? "#c21766" : "#8f7b94" } }}>
                          <HeartIcon filled={r._liked} size={11} />
                          <Typography sx={{ fontSize: 10, fontWeight: 500 }}>{r._likes || ""}</Typography>
                        </Box>
                      </Box>
                    </Box>
                  ))}
                </Box>
              )}
            </Box>
          </Box>
        </Box>
      ))}

      {/* Load more */}
      <Box sx={{ pt: 1.5, textAlign: "center" }}>
        <Button size="small"
          startIcon={loading ? <CircularProgress size={13} color="inherit" /> : <RefreshIcon sx={{ fontSize: 15 }} />}
          disabled={loading} onClick={handleLoadMore}
          sx={{ color: "#8f7b94", fontSize: 12, fontWeight: 500, borderRadius: "8px", "&:hover": { color: "#d62976", bgcolor: "rgba(214,41,118,0.08)" } }}
        >
          {loading ? "생성 중..." : "더 보기"}
        </Button>
      </Box>
    </Box>
  );
}

function HeartIcon({ filled, size = 13 }: { filled: boolean; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth={2}>
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  );
}
