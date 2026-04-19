import { useState, useCallback, useEffect, useRef } from "react";
import { Box, Typography, IconButton } from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import CloseIcon from "@mui/icons-material/Close";
import AddPhotoAlternateIcon from "@mui/icons-material/AddPhotoAlternate";
import VideocamOutlinedIcon from "@mui/icons-material/VideocamOutlined";
import { motion, AnimatePresence } from "framer-motion";

interface UploadZoneProps {
  /** Controlled file list from parent */
  files?: File[];
  /** Called whenever the file list changes */
  onFilesChange: (files: File[]) => void;
  /** Max number of files allowed */
  maxFiles?: number;
  /** Desktop compact mode: denser grid and smaller empty state */
  compact?: boolean;
}

function formatSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];
const VIDEO_TYPES = ["video/mp4", "video/quicktime", "video/webm"];
const ALL_ACCEPT = [...IMAGE_TYPES, ...VIDEO_TYPES].join(",");
const MAX_IMAGE = 10 * 1024 * 1024;
/** 백엔드 MAX_VIDEO_UPLOAD_MB 기본값(300)과 정렬. 변경 시 backend/.env 와 함께 수정 */
const VIDEO_MAX_MB = 300;
const MAX_VIDEO = VIDEO_MAX_MB * 1024 * 1024;

/**
 * 로컬 비디오에서 첫 프레임(또는 짧은 seek)을 디코딩해 JPEG object URL을 만든다.
 * 업로드 영역 썸네일 렌더링에 사용한다.
 * @param file - 사용자가 선택한 비디오 파일
 * @returns JPEG Blob object URL (호출 측에서 적절한 시점에 revoke 필요)
 */
async function captureVideoFirstFrameAsObjectUrl(file: File): Promise<string> {
  const blobUrl = URL.createObjectURL(file);
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.setAttribute("playsinline", "true");
  video.preload = "auto";

  return new Promise((resolve, reject) => {
    const teardownVideo = () => {
      video.removeAttribute("src");
      video.load();
    };

    const finishFail = (err: Error) => {
      URL.revokeObjectURL(blobUrl);
      teardownVideo();
      reject(err);
    };

    const drawFrame = () => {
      try {
        const w = video.videoWidth;
        const h = video.videoHeight;
        if (!w || !h) {
          finishFail(new Error("no video dimensions"));
          return;
        }
        const canvas = document.createElement("canvas");
        const maxEdge = 1024;
        let tw = w;
        let th = h;
        if (Math.max(w, h) > maxEdge) {
          const scale = maxEdge / Math.max(w, h);
          tw = Math.round(w * scale);
          th = Math.round(h * scale);
        }
        canvas.width = tw;
        canvas.height = th;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          finishFail(new Error("no canvas context"));
          return;
        }
        ctx.drawImage(video, 0, 0, tw, th);
        canvas.toBlob(
          (jpeg) => {
            URL.revokeObjectURL(blobUrl);
            teardownVideo();
            if (!jpeg) {
              reject(new Error("toBlob failed"));
              return;
            }
            resolve(URL.createObjectURL(jpeg));
          },
          "image/jpeg",
          0.88,
        );
      } catch (e) {
        finishFail(e instanceof Error ? e : new Error(String(e)));
      }
    };

    const onSeeked = () => {
      video.removeEventListener("seeked", onSeeked);
      drawFrame();
    };

    video.addEventListener("seeked", onSeeked);

    video.onerror = () => finishFail(new Error("video decode error"));

    video.addEventListener(
      "loadeddata",
      () => {
        const d = video.duration;
        const t =
          d && !Number.isNaN(d) && Number.isFinite(d) && d > 0
            ? Math.min(0.08, Math.max(0.001, d * 0.02))
            : 0;
        try {
          video.currentTime = t;
        } catch {
          finishFail(new Error("seek failed"));
        }
      },
      { once: true },
    );

    video.src = blobUrl;
    video.load();
  });
}

/**
 * Multi-file upload zone with grid preview.
 * Supports images and one video. Shows thumbnails in a responsive grid.
 */
export default function UploadZone({
  files = [],
  onFilesChange,
  maxFiles = 9,
  compact = false,
}: UploadZoneProps) {
  const [previews, setPreviews] = useState<Record<string, string>>({});
  /** 비디오 첫 프레임 추출 실패 키 기록(카메라 아이콘으로 폴백) */
  const [videoPosterFailed, setVideoPosterFailed] = useState<Record<string, true>>({});
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  /** 이미지는 object URL 생성, 비디오는 비동기로 첫 프레임 JPEG 썸네일 생성 */
  useEffect(() => {
    const keysNow = new Set(files.map((f) => `${f.name}_${f.size}_${f.lastModified}`));
    let cancelled = false;

    setPreviews((prev) => {
      const next: Record<string, string> = {};
      const toRevoke: string[] = [];
      Object.entries(prev).forEach(([k, url]) => {
        if (!keysNow.has(k)) toRevoke.push(url);
      });
      toRevoke.forEach((u) => URL.revokeObjectURL(u));

      files.forEach((f) => {
        const key = `${f.name}_${f.size}_${f.lastModified}`;
        if (prev[key]) {
          next[key] = prev[key];
        } else if (IMAGE_TYPES.includes(f.type)) {
          next[key] = URL.createObjectURL(f);
        }
      });
      return next;
    });

    setVideoPosterFailed((prev) => {
      const next: Record<string, true> = { ...prev };
      Object.keys(prev).forEach((k) => {
        if (!keysNow.has(k)) delete next[k];
      });
      return next;
    });

    files.forEach((f) => {
      if (!VIDEO_TYPES.includes(f.type)) return;
      const key = `${f.name}_${f.size}_${f.lastModified}`;
      captureVideoFirstFrameAsObjectUrl(f)
        .then((url) => {
          if (cancelled) {
            URL.revokeObjectURL(url);
            return;
          }
          setPreviews((prev) => {
            if (prev[key]) {
              URL.revokeObjectURL(url);
              return prev;
            }
            return { ...prev, [key]: url };
          });
        })
        .catch(() => {
          if (!cancelled) {
            setVideoPosterFailed((p) => ({ ...p, [key]: true }));
          }
        });
    });

    return () => {
      cancelled = true;
    };
  }, [files]);

  const fileKey = (f: File) => `${f.name}_${f.size}_${f.lastModified}`;

  const validateAndAdd = useCallback(
    (incoming: File[]) => {
      setError("");
      const valid: File[] = [];
      for (const f of incoming) {
        const isVideo = VIDEO_TYPES.includes(f.type);
        const isImage = IMAGE_TYPES.includes(f.type);
        if (!isImage && !isVideo) {
          setError("이미지(JPG/PNG/WebP) 또는 동영상(MP4/MOV/WebM)만 지원합니다");
          continue;
        }
        if (isImage && f.size > MAX_IMAGE) {
          setError(`이미지 크기 초과(${formatSize(f.size)}), 최대 10MB`);
          continue;
        }
        if (isVideo && f.size > MAX_VIDEO) {
          setError(`동영상 크기 초과(${formatSize(f.size)}), 최대 ${VIDEO_MAX_MB}MB`);
          continue;
        }
        if (isVideo && files.some((ex) => VIDEO_TYPES.includes(ex.type))) {
          setError("동영상은 1개만 업로드할 수 있습니다");
          continue;
        }
        valid.push(f);
      }
      if (valid.length === 0) return;
      const merged = [...files, ...valid].slice(0, maxFiles);
      onFilesChange(merged);
    },
    [files, maxFiles, onFilesChange],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      validateAndAdd(Array.from(e.dataTransfer.files));
    },
    [validateAndAdd],
  );

  const removeFile = useCallback(
    (idx: number) => {
      const next = files.filter((_, i) => i !== idx);
      onFilesChange(next);
    },
    [files, onFilesChange],
  );

  const hasFiles = files.length > 0;

  return (
    <>
      <Box
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        sx={{
          borderRadius: "14px",
          border: `2px dashed ${isDragging ? "rgba(214, 41, 118, 0.7)" : error ? "#e11d48" : "rgba(214, 41, 118, 0.22)"}`,
          bgcolor: isDragging ? "rgba(214,41,118,0.08)" : "rgba(255,255,255,0.72)",
          backdropFilter: "blur(6px)",
          boxShadow: isDragging
            ? "0 0 0 3px rgba(214,41,118,0.16), inset 0 1px 0 rgba(255,255,255,0.9)"
            : "inset 0 1px 0 rgba(255,255,255,0.85)",
          transition: "border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease",
          overflow: "hidden",
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ALL_ACCEPT}
          multiple
          hidden
          onChange={(e) => {
            if (e.target.files) validateAndAdd(Array.from(e.target.files));
            e.target.value = "";
          }}
        />

        <AnimatePresence mode="wait">
          {hasFiles ? (
            <motion.div
              key="grid"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <Box
                sx={{
                  display: "grid",
                  gridTemplateColumns: compact ? "repeat(4, 1fr)" : "repeat(3, 1fr)",
                  gap: compact ? 0.75 : 1,
                  p: compact ? 1 : 1.5,
                  maxHeight: compact ? 220 : "none",
                  overflowY: compact ? "auto" : "visible",
                }}
              >
                {files.map((f, idx) => {
                  const key = fileKey(f);
                  const isVideo = VIDEO_TYPES.includes(f.type);
                  return (
                    <Box
                      key={key}
                      sx={{
                        position: "relative",
                        aspectRatio: "1",
                        borderRadius: "12px",
                        overflow: "hidden",
                        bgcolor: "#f7eef8",
                        boxShadow: "0 2px 8px rgba(214,41,118,0.09)",
                        transition: "transform 0.2s ease, box-shadow 0.2s ease",
                        "&:hover": { transform: "scale(1.02)", boxShadow: "0 4px 14px rgba(214,41,118,0.16)" },
                      }}
                    >
                      {isVideo && videoPosterFailed[key] ? (
                        <Box sx={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <VideocamOutlinedIcon sx={{ fontSize: 28, color: "#9d88a3" }} />
                        </Box>
                      ) : isVideo && previews[key] ? (
                        <Box
                          component="img"
                          src={previews[key]}
                          alt=""
                          sx={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                        />
                      ) : isVideo ? (
                        <Box sx={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <Typography sx={{ fontSize: 11, color: "#9d88a3" }}>로딩 중</Typography>
                        </Box>
                      ) : previews[key] ? (
                        <Box
                          component="img"
                          src={previews[key]}
                          alt={f.name}
                          sx={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                        />
                      ) : (
                        <Box sx={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <Typography sx={{ fontSize: 11, color: "#9d88a3" }}>로딩 중</Typography>
                        </Box>
                      )}
                      <IconButton
                        size="small"
                        aria-label="파일 삭제"
                        onClick={() => removeFile(idx)}
                        sx={{
                          position: "absolute", top: 2, right: 2,
                          bgcolor: "rgba(36,22,40,0.55)", color: "#fff",
                          width: 24, height: 24, minWidth: 24,
                          padding: 0,
                          "&:hover": { bgcolor: "rgba(36,22,40,0.75)" },
                        }}
                      >
                        <CloseIcon sx={{ fontSize: 14 }} />
                      </IconButton>
                    </Box>
                  );
                })}
                {files.length < maxFiles && (
                  <Box
                    role="button"
                    tabIndex={0}
                    aria-label="파일 추가"
                    onClick={() => inputRef.current?.click()}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
                    sx={{
                      aspectRatio: "1",
                      borderRadius: "12px",
                      border: "1px dashed rgba(214,41,118,0.4)",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                      cursor: "pointer",
                      bgcolor: "rgba(214,41,118,0.08)",
                      transition: "all 0.2s ease",
                      "&:hover": {
                        borderColor: "primary.main",
                        bgcolor: "rgba(214,41,118,0.13)",
                        boxShadow: "0 2px 12px rgba(214,41,118,0.18)",
                      },
                      "&:focus-visible": { outline: "2px solid #d62976", outlineOffset: 2 },
                    }}
                  >
                    <AddPhotoAlternateIcon sx={{ fontSize: 24, color: "#a995af" }} />
                    <Typography sx={{ fontSize: 11, color: "#8f7b94", mt: 0.25 }}>
                      {files.length}/{maxFiles}
                    </Typography>
                  </Box>
                )}
              </Box>
            </motion.div>
          ) : (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                padding: compact ? "24px 16px" : "40px 24px",
                gap: compact ? 6 : 10,
                cursor: "pointer",
              }}
              onClick={() => inputRef.current?.click()}
            >
              <Box sx={{
                width: compact ? 52 : 64,
                height: compact ? 52 : 64,
                borderRadius: compact ? "14px" : "18px",
                background: "linear-gradient(135deg, rgba(250,126,30,0.14) 0%, rgba(214,41,118,0.12) 52%, rgba(79,91,213,0.12) 100%)",
                border: "1.5px solid rgba(214,41,118,0.16)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}>
                <CloudUploadIcon sx={{ fontSize: compact ? 26 : 32, color: "#d62976" }} />
              </Box>
              <Box sx={{ textAlign: "center" }}>
                <Typography sx={{
                  color: "#241628", fontWeight: 700,
                  fontSize: compact ? 14 : 16,
                  lineHeight: 1.3, mb: 0.5,
                }}>
                  스크린샷을 드래그해서 진단 시작
                </Typography>
                <Typography sx={{
                  color: "#8f7b94",
                  fontSize: compact ? 12 : 13,
                  lineHeight: 1.5,
                }}>
                  드래그 · 클릭 · Ctrl+V 붙여넣기
                </Typography>
                <Typography sx={{
                  color: "#a995af",
                  fontSize: compact ? 11 : 12,
                  mt: 0.25,
                }}>
                  이미지 최대 {maxFiles}장 · 동영상 1개
                </Typography>
              </Box>
            </motion.div>
          )}
        </AnimatePresence>
      </Box>

      {error && (
        <Typography role="alert" sx={{ color: "#e11d48", mt: 0.75, fontSize: "0.8rem" }}>
          {error}
        </Typography>
      )}
    </>
  );
}
