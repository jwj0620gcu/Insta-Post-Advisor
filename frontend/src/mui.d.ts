/**
 * MUI v6 타입 확장: Typography, Stack 등에서 system props를 직접 사용할 수 있게 한다.
 * 런타임에서는 동작하지만 기본 TS 타입에는 포함되어 있지 않다.
 */
import "@mui/material/Typography";
import "@mui/material/Stack";

declare module "@mui/material/Typography" {
  interface TypographyOwnProps {
    fontWeight?: number | string;
    fontSize?: number | string;
    textAlign?: string;
    lineHeight?: number | string;
    display?: string;
  }
}

declare module "@mui/material/Stack" {
  interface StackOwnProps {
    justifyContent?: string;
    alignItems?: string;
    flexWrap?: string;
  }
}
