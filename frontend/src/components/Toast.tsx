import { useState, useEffect } from "react";
import { Snackbar, Alert } from "@mui/material";

let showToastFn: ((msg: string) => void) | null = null;

/**
 * 전역 toast 트리거 함수
 */
export function showToast(message: string) {
  showToastFn?.(message);
}

/**
 * Toast 컨테이너(MUI Snackbar). App 루트에 1회 배치
 */
export default function ToastContainer() {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    showToastFn = (msg: string) => {
      setMessage(msg);
      setOpen(true);
    };
    return () => {
      showToastFn = null;
    };
  }, []);

  return (
    <Snackbar
      open={open}
      autoHideDuration={2000}
      onClose={() => setOpen(false)}
      anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
    >
      <Alert
        onClose={() => setOpen(false)}
        severity="success"
        variant="filled"
        sx={{ borderRadius: 3 }}
      >
        {message}
      </Alert>
    </Snackbar>
  );
}
