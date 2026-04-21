import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { ThemeProvider, CssBaseline } from "@mui/material";
import { AnimatePresence, motion } from "framer-motion";
import theme from "./theme";
import { pageTransition } from "./utils/motion";
import ToastContainer from "./components/Toast";
import ErrorBoundary from "./components/ErrorBoundary";
import AnnouncementDialog from "./components/AnnouncementDialog";
import "./index.css";

/* ── 지연 로딩 페이지 ── */
const Home = lazy(() => import("./pages/Home"));
const Diagnosing = lazy(() => import("./pages/Diagnosing"));
const Report = lazy(() => import("./pages/Report"));
const History = lazy(() => import("./pages/History"));
const ScreenshotAnalysis = lazy(() => import("./pages/ScreenshotAnalysis"));

/* ── 최소 로딩 폴백 ── */
function PageLoader() {
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "60vh" }}>
      <div style={{ width: 28, height: 28, border: "3px solid #f2dce9", borderTopColor: "#d62976", borderRadius: "50%", animation: "spin 0.6s linear infinite" }} />
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

/** 페이지 전환 애니메이션 래퍼 (Framer Motion AnimatePresence) */
function AnimatedRoutes() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route
          path="/"
          element={
            <motion.div
              variants={pageTransition}
              initial="initial"
              animate="animate"
              exit="exit"
              style={{ minHeight: "100vh" }}
            >
              <Suspense fallback={<PageLoader />}>
                <Home />
              </Suspense>
            </motion.div>
          }
        />
        <Route
          path="/diagnosing"
          element={
            <motion.div
              variants={pageTransition}
              initial="initial"
              animate="animate"
              exit="exit"
              style={{ minHeight: "100vh" }}
            >
              <Suspense fallback={<PageLoader />}>
                <Diagnosing />
              </Suspense>
            </motion.div>
          }
        />
        <Route
          path="/report"
          element={
            <motion.div
              variants={pageTransition}
              initial="initial"
              animate="animate"
              exit="exit"
              style={{ minHeight: "100vh" }}
            >
              <Suspense fallback={<PageLoader />}>
                <Report />
              </Suspense>
            </motion.div>
          }
        />
        <Route
          path="/history"
          element={
            <motion.div
              variants={pageTransition}
              initial="initial"
              animate="animate"
              exit="exit"
              style={{ minHeight: "100vh" }}
            >
              <Suspense fallback={<PageLoader />}>
                <History />
              </Suspense>
            </motion.div>
          }
        />
        <Route
          path="/screenshot"
          element={
            <motion.div
              variants={pageTransition}
              initial="initial"
              animate="animate"
              exit="exit"
              style={{ minHeight: "100vh" }}
            >
              <Suspense fallback={<PageLoader />}>
                <ScreenshotAnalysis />
              </Suspense>
            </motion.div>
          }
        />
      </Routes>
    </AnimatePresence>
  );
}

/**
 * 루트 컴포넌트
 */
function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ErrorBoundary>
        <BrowserRouter basename="/app">
          <AnimatedRoutes />
          <ToastContainer />
          <AnnouncementDialog />
        </BrowserRouter>
      </ErrorBoundary>
    </ThemeProvider>
  );
}

export default App;
