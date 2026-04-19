/**
 * API 요청 유틸
 */
import axios from "axios";

/**
 * 전체 진단(멀티 에이전트 + 선택적 영상)은 수분이 걸릴 수 있으므로
 * Diagnosing 페이지의 대기 제한과 같은 값을 사용한다.
 * frontend/.env 에서 `VITE_DIAGNOSE_MAX_WAIT_MS`(밀리초)로 조정 가능하다.
 */
export const DIAGNOSE_CLIENT_MAX_MS = (() => {
  const n = Number(import.meta.env.VITE_DIAGNOSE_MAX_WAIT_MS);
  return Number.isFinite(n) && n > 0 ? n : 600_000;
})();

const api = axios.create({
  baseURL: "/api",
  timeout: 120_000,
});

/**
 * Vite 프록시를 통해 로컬 백엔드 프로세스가 도달 가능한지만 확인한다.
 */
export async function getApiHealth(): Promise<boolean> {
  try {
    const { data } = await api.get<{ ok?: boolean }>("/health", { timeout: 5000 });
    return data?.ok === true;
  } catch {
    return false;
  }
}

export interface DiagnoseParams {
  title: string;
  content: string;
  category: string;
  tags: string;
  coverImage?: File;
  coverImages?: File[];
  videoFile?: File;
}

export interface AgentOpinion {
  agent_name: string;
  dimension: string;
  score: number;
  issues: string[];
  suggestions: string[];
  reasoning: string;
  debate_comments: string[];
}

export interface SimulatedComment {
  username: string;
  avatar_emoji?: string;
  comment: string;
  sentiment: "positive" | "negative" | "neutral";
  likes?: number;
  time_ago?: string;
  ip_location?: string;
  is_author?: boolean;
}

export interface DebateEntry {
  round: number;
  agent_name: string;
  kind: "agree" | "rebuttal" | "add";
  text: string;
}

export interface CoverDirection {
  layout: string;
  color_scheme: string;
  text_style: string;
  tips: string[];
}

export interface DiagnoseResult {
  overall_score: number;
  grade: string;
  radar_data: Record<string, number>;
  agent_opinions: AgentOpinion[];
  issues: Array<{ severity: string; description: string; from_agent: string }>;
  suggestions: Array<{
    priority: number;
    description: string;
    expected_impact: string;
  }>;
  debate_summary: string;
  debate_timeline: DebateEntry[];
  simulated_comments: SimulatedComment[];
  optimized_title?: string;
  optimized_content?: string;
  cover_direction?: CoverDirection;
}

/**
 * 노트를 진단한다.
 */
export async function diagnoseNote(
  params: DiagnoseParams
): Promise<DiagnoseResult> {
  const formData = new FormData();
  formData.append("title", params.title);
  formData.append("content", params.content);
  formData.append("category", params.category);
  formData.append("tags", params.tags);
  if (params.coverImage) {
    formData.append("cover_image", params.coverImage);
  }
  if (params.coverImages && params.coverImages.length > 0) {
    params.coverImages.forEach((file) => formData.append("cover_images", file));
  }
  if (params.videoFile) {
    formData.append("video_file", params.videoFile);
  }

  const { data } = await api.post<DiagnoseResult>("/diagnose", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: DIAGNOSE_CLIENT_MAX_MS,
  });
  return data;
}

/**
 * Model A 즉시 사전 점수(<50ms, LLM 호출 없음)
 */
export interface PreScoreResult {
  total_score: number;
  dimensions: Record<string, number>;
  weights: Record<string, number>;
  level: string;
  baseline: { avg_engagement: number; median: number; viral_threshold: number; sample_size: number };
  category: string;
  category_cn: string;
}

export async function preScore(params: {
  title: string; content: string; category: string; tags: string; image_count: number;
}): Promise<PreScoreResult> {
  const fd = new FormData();
  fd.append("title", params.title);
  fd.append("content", params.content);
  fd.append("category", params.category);
  fd.append("tags", params.tags);
  fd.append("image_count", String(params.image_count));
  const { data } = await api.post<PreScoreResult>("/pre-score", fd);
  return data;
}

/**
 * SSE 스트리밍 진단
 */
export type StreamEvent =
  | { type: "pre_score"; data: PreScoreResult & { title: string } }
  | { type: "progress"; data: { step: string; message: string } }
  | { type: "result"; data: DiagnoseResult }
  | { type: "error"; data: { message: string } };

export async function diagnoseStream(
  params: DiagnoseParams,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const fd = new FormData();
  fd.append("title", params.title);
  fd.append("content", params.content);
  fd.append("category", params.category);
  fd.append("tags", params.tags);
  if (params.coverImage) fd.append("cover_image", params.coverImage);
  if (params.coverImages) params.coverImages.forEach((f) => fd.append("cover_images", f));
  if (params.videoFile) fd.append("video_file", params.videoFile);

  const response = await fetch("/api/diagnose-stream", { method: "POST", body: fd, signal });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  /** read() 호출 사이에 유지해야 한다. TCP 특성상 `event:`/`data:`가 다른 chunk로 나뉠 수 있다. */
  let pendingEvent = "";

  const processSseLines = (lines: string[]) => {
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        pendingEvent = line.slice(7).trim();
      } else if (line.startsWith("data:") && pendingEvent) {
        const payload = line.slice(5).trimStart();
        try {
          const data = JSON.parse(payload);
          onEvent({ type: pendingEvent, data } as StreamEvent);
        } catch (e) {
          if (pendingEvent === "result") {
            console.error(
              "[diagnoseStream] result data JSON 파싱 실패(너무 크거나 잘렸을 수 있음)",
              e,
            );
          }
        }
        pendingEvent = "";
      }
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (value) {
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      processSseLines(lines);
    }
    if (done) break;
  }
  if (buffer.trim()) {
    processSseLines(buffer.split("\n"));
  }
}

/**
 * 카테고리 baseline 요약 조회
 */
export async function getBaseline(category: string) {
  const { data } = await api.get(`/baseline/${category}`);
  return data;
}

/**
 * 시뮬레이션 댓글 추가 생성
 */
export interface CommentWithReplies extends SimulatedComment {
  replies?: SimulatedComment[];
}

export async function generateComments(params: {
  title: string;
  content: string;
  category: string;
  existing_count: number;
}): Promise<CommentWithReplies[]> {
  const { data } = await api.post<{ comments: CommentWithReplies[] }>(
    "/generate-comments",
    params
  );
  return data.comments;
}

// --------------- 반복 최적화 ---------------

export interface OptimizePlan {
  strategy: string;
  optimized_title: string;
  optimized_content: string;
  key_changes: string;
  score: number;
  score_delta: number;
  recommended?: boolean;
}

export interface OptimizeResult {
  original_score: number;
  plans: OptimizePlan[];
}

export async function optimizeDiagnosis(params: {
  title: string;
  content: string;
  category: string;
  issues: string;
  suggestions: string;
  overall_score: number;
}): Promise<OptimizeResult> {
  const { data } = await api.post<OptimizeResult>("/optimize", params);
  return data;
}

// --------------- 기록 ---------------

export interface HistoryListItem {
  id: string;
  title: string;
  category: string;
  overall_score: number;
  grade: string;
  created_at: string;
}

export interface HistoryDetail extends HistoryListItem {
  report: DiagnoseResult;
}

/**
 * @param params - title, category, report(전체 DiagnoseResult)
 * @returns {id: string}
 */
export async function saveHistory(params: {
  title: string;
  category: string;
  report: DiagnoseResult;
}): Promise<{ id: string }> {
  const { data } = await api.post<{ id: string }>("/history", params);
  return data;
}

/**
 * @param limit - 페이지당 개수
 * @param offset - 오프셋
 */
export async function getHistoryList(
  limit = 20,
  offset = 0
): Promise<HistoryListItem[]> {
  const { data } = await api.get<HistoryListItem[]>("/history", {
    params: { limit, offset },
  });
  return data;
}

/**
 * @param id - 기록 UUID
 */
export async function getHistoryDetail(id: string): Promise<HistoryDetail> {
  const { data } = await api.get<HistoryDetail>(`/history/${id}`);
  return data;
}

/**
 * @param id - 기록 UUID
 */
export async function deleteHistory(id: string): Promise<void> {
  await api.delete(`/history/${id}`);
}

// --------------- 스크린샷 분석 ---------------

export type SlotType = "cover" | "content" | "profile" | "comments";

export interface QuickRecognizeResult {
  success: boolean;
  /** image=스크린샷 빠른 인식, video=영상 빠른 인식(제목은 커버/제목 캡처를 별도 권장) */
  media_source?: "image" | "video";
  slot_type: string;
  extra_slots?: string[];
  category: string;
  title?: string;
  content_text?: string;
  summary: string;
  confidence?: number;
  error?: string;
  publisher?: { name: string; follower_count: string };
  engagement_signal?: {
    likes_visible: number;
    collects_visible: number;
    comments_visible: number;
    is_high_engagement: boolean;
  };
}

export interface DeepAnalysisResult {
  scenario: string;
  slot_count: number;
  extra_text: string;
  video_info: { filename: string; size_mb: number; content_type: string } | null;
  analyses: Record<string, Record<string, unknown>>;
  overall: {
    completeness: number;
    scenario: string;
    tips: string[];
    slots_analyzed: string[];
  };
}

/**
 * 단일 스크린샷을 업로드해 AI 빠른 인식을 수행한다.
 * @param file - 이미지 파일
 * @param slotHint - 슬롯 힌트
 */
export async function quickRecognize(
  file: File,
  slotHint?: SlotType
): Promise<QuickRecognizeResult> {
  const fd = new FormData();
  fd.append("file", file);
  if (slotHint) fd.append("slot_hint", slotHint);
  const { data } = await api.post<QuickRecognizeResult>(
    "/screenshot/quick-recognize",
    fd,
    {
      headers: { "Content-Type": "multipart/form-data" },
      /** 비전 60s + OCR, 백엔드 여유 시간 포함 */
      timeout: 180_000,
    },
  );
  return data;
}

/**
 * 영상을 업로드해 AI 빠른 인식을 수행한다(전체 또는 프레임 샘플).
 * @param file - 영상 파일(mp4 / webm / quicktime)
 */
export async function quickRecognizeVideo(file: File): Promise<QuickRecognizeResult> {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await api.post<QuickRecognizeResult>(
    "/screenshot/quick-recognize-video",
    fd,
    {
      headers: { "Content-Type": "multipart/form-data" },
      /** 영상 빠른 인식은 전체 STT를 포함하므로 긴 영상은 수분이 걸릴 수 있다 */
      timeout: 600_000,
    }
  );
  return data;
}

/**
 * 전체 이미지 번들을 제출해 심층 분석을 수행한다.
 * @param params - scenario 및 슬롯별 스크린샷 포함
 */
export async function deepAnalyze(params: {
  scenario: "pre_publish" | "post_publish";
  cover?: File;
  contentImg?: File;
  profile?: File;
  comments?: File;
  video?: File;
  extraText?: string;
}): Promise<DeepAnalysisResult> {
  const fd = new FormData();
  fd.append("scenario", params.scenario);
  if (params.cover) fd.append("cover", params.cover);
  if (params.contentImg) fd.append("content_img", params.contentImg);
  if (params.profile) fd.append("profile", params.profile);
  if (params.comments) fd.append("comments", params.comments);
  if (params.video) fd.append("video", params.video);
  if (params.extraText) fd.append("extra_text", params.extraText);
  const { data } = await api.post<DeepAnalysisResult>(
    "/screenshot/deep-analyze",
    fd,
    { headers: { "Content-Type": "multipart/form-data" }, timeout: 180000 }
  );
  return data;
}

/**
 * 텍스트 내 링크 제거
 */
export async function stripLinks(text: string): Promise<string> {
  const fd = new FormData();
  fd.append("text", text);
  const { data } = await api.post<{ cleaned: string }>("/text/strip-links", fd);
  return data.cleaned;
}

export default api;
