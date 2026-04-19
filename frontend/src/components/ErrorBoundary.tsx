import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { Box, Typography, Button } from "@mui/material";
import SentimentVeryDissatisfiedIcon from "@mui/icons-material/SentimentVeryDissatisfied";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * 전역 에러 바운더리
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <Box
          sx={{
            minHeight: "100vh",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            bgcolor: "background.default",
            px: 3,
          }}
        >
          <Box sx={{ textAlign: "center", maxWidth: 400 }}>
            <SentimentVeryDissatisfiedIcon
              sx={{ fontSize: 64, color: "text.secondary", mb: 2 }}
            />
            <Typography variant="h5" fontWeight={700} gutterBottom>
              페이지 오류가 발생했습니다
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
              {this.state.error?.message || "알 수 없는 오류"}
            </Typography>
            <Button
              variant="contained"
              onClick={() => window.location.assign("/app")}
            >
              홈으로 돌아가기
            </Button>
          </Box>
        </Box>
      );
    }
    return this.props.children;
  }
}
