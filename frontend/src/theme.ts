import { createTheme, type ThemeOptions } from "@mui/material/styles";

const IG_COLORS = {
  yellow: "#feda75",
  orange: "#fa7e1e",
  coral: "#f56040",
  pink: "#d62976",
  purple: "#962fbf",
  indigo: "#4f5bd5",
  text: "#241628",
  muted: "#6f5b72",
  surface: "#fff8f8",
  paper: "#ffffff",
  divider: "rgba(214, 41, 118, 0.16)",
};

const IG_GRADIENT =
  "linear-gradient(135deg, #feda75 0%, #fa7e1e 22%, #f56040 40%, #d62976 62%, #962fbf 82%, #4f5bd5 100%)";

const themeOptions: ThemeOptions = {
  palette: {
    primary: {
      main: IG_COLORS.pink,
      light: IG_COLORS.coral,
      dark: "#ba1d66",
      contrastText: "#ffffff",
    },
    secondary: {
      main: IG_COLORS.purple,
      light: "#b26fd0",
      dark: "#74269a",
      contrastText: "#ffffff",
    },
    error: {
      main: "#e11d48",
      light: "#fb7185",
      dark: "#be123c",
    },
    warning: {
      main: IG_COLORS.orange,
      light: IG_COLORS.yellow,
      dark: "#d15e0b",
    },
    info: {
      main: IG_COLORS.indigo,
      light: "#7a83ea",
      dark: "#3645b8",
    },
    success: {
      main: "#22a06b",
      light: "#63cf98",
      dark: "#14734a",
    },
    background: {
      default: IG_COLORS.surface,
      paper: IG_COLORS.paper,
    },
    text: {
      primary: IG_COLORS.text,
      secondary: IG_COLORS.muted,
    },
    divider: IG_COLORS.divider,
  },

  typography: {
    fontFamily: [
      "Pretendard",
      "Noto Sans KR",
      "Inter",
      "-apple-system",
      "BlinkMacSystemFont",
      "sans-serif",
    ].join(","),
    fontWeightRegular: 400,
    fontWeightMedium: 500,
    fontWeightBold: 700,
    h1: { fontWeight: 700, fontSize: "2rem", lineHeight: 1.3, letterSpacing: "-0.02em" },
    h2: { fontWeight: 700, fontSize: "1.75rem", lineHeight: 1.35, letterSpacing: "-0.02em" },
    h3: { fontWeight: 600, fontSize: "1.5rem", lineHeight: 1.4 },
    h4: { fontWeight: 600, fontSize: "1.25rem", lineHeight: 1.4 },
    h5: { fontWeight: 600, fontSize: "1.1rem", lineHeight: 1.5 },
    h6: { fontWeight: 600, fontSize: "1rem", lineHeight: 1.5 },
    subtitle1: { fontWeight: 500, fontSize: "1rem", lineHeight: 1.6 },
    subtitle2: { fontWeight: 500, fontSize: "0.875rem", lineHeight: 1.6 },
    body1: { fontWeight: 400, fontSize: "1rem", lineHeight: 1.7 },
    body2: { fontWeight: 400, fontSize: "0.875rem", lineHeight: 1.7 },
    button: { fontWeight: 600, fontSize: "0.875rem", letterSpacing: "0.02em" },
    caption: { fontWeight: 400, fontSize: "0.75rem", lineHeight: 1.5, color: "#8f7d93" },
  },

  shape: {
    borderRadius: 14,
  },

  shadows: [
    "none",
    "0 1px 2px rgba(79, 91, 213, 0.05)",
    "0 2px 8px rgba(214, 41, 118, 0.08)",
    "0 6px 20px rgba(214, 41, 118, 0.1)",
    "0 10px 30px rgba(150, 47, 191, 0.12)",
    "0 14px 36px rgba(150, 47, 191, 0.13)",
    "0 16px 40px rgba(79, 91, 213, 0.13)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
    "0 6px 20px rgba(0,0,0,0.08)",
  ],

  components: {
    MuiCssBaseline: {
      styleOverrides: {
        ":root": {
          "--ig-yellow": IG_COLORS.yellow,
          "--ig-orange": IG_COLORS.orange,
          "--ig-coral": IG_COLORS.coral,
          "--ig-pink": IG_COLORS.pink,
          "--ig-purple": IG_COLORS.purple,
          "--ig-indigo": IG_COLORS.indigo,
          "--ig-gradient": IG_GRADIENT,
        },
        body: {
          backgroundColor: "#fff8f8",
          backgroundImage:
            "radial-gradient(circle at 12% -8%, rgba(250,126,30,0.28), transparent 34%), radial-gradient(circle at 88% 0%, rgba(79,91,213,0.25), transparent 32%), radial-gradient(circle at 56% 108%, rgba(214,41,118,0.22), transparent 42%), linear-gradient(180deg, #fff8f8 0%, #fff5f8 58%, #fff2f7 100%)",
          backgroundAttachment: "fixed",
          color: IG_COLORS.text,
        },
      },
    },

    MuiButton: {
      defaultProps: {
        disableElevation: true,
      },
      styleOverrides: {
        root: {
          textTransform: "none" as const,
          fontWeight: 600,
          borderRadius: 14,
          padding: "10px 28px",
          transition: "background-color 0.22s ease, box-shadow 0.22s ease, transform 0.18s ease",
        },
        sizeLarge: {
          padding: "14px 32px",
          fontSize: "1rem",
          borderRadius: 14,
        },
        sizeSmall: {
          padding: "6px 18px",
          fontSize: "0.8rem",
          borderRadius: 12,
        },
      },
      variants: [
        {
          props: { variant: "contained" as const, color: "primary" as const },
          style: {
            background: IG_GRADIENT,
            boxShadow: "0 8px 24px rgba(214, 41, 118, 0.28)",
            "&:hover": {
              filter: "brightness(1.04)",
              boxShadow: "0 10px 28px rgba(150, 47, 191, 0.3)",
              transform: "translateY(-1px)",
            },
            "&:active": {
              transform: "translateY(0)",
            },
            "&.Mui-disabled": {
              background: "#ece6ee",
              boxShadow: "none",
              color: "#a894ac",
            },
          },
        },
        {
          props: { variant: "outlined" as const, color: "primary" as const },
          style: {
            borderWidth: 1.5,
            borderColor: "rgba(214, 41, 118, 0.45)",
            color: IG_COLORS.pink,
            "&:hover": {
              borderWidth: 1.5,
              backgroundColor: "rgba(214, 41, 118, 0.06)",
              borderColor: IG_COLORS.pink,
            },
          },
        },
      ],
    },

    MuiCard: {
      defaultProps: {
        elevation: 0,
      },
      styleOverrides: {
        root: {
          borderRadius: 18,
          border: "1px solid rgba(214, 41, 118, 0.12)",
          backgroundColor: "rgba(255, 255, 255, 0.92)",
          boxShadow: "0 12px 32px rgba(214, 41, 118, 0.08)",
          backdropFilter: "blur(8px)",
        },
      },
    },

    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
        },
        rounded: {
          borderRadius: 18,
        },
      },
    },

    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 999,
          fontWeight: 500,
          height: 30,
        },
        colorPrimary: {
          background: "rgba(214, 41, 118, 0.1)",
          color: "#b71f63",
          border: "1px solid rgba(214, 41, 118, 0.14)",
        },
      },
    },

    MuiTextField: {
      styleOverrides: {
        root: {
          "& .MuiOutlinedInput-root": {
            borderRadius: 14,
            transition: "box-shadow 0.2s ease, border-color 0.2s ease",
            "& .MuiOutlinedInput-notchedOutline": {
              borderColor: "rgba(214, 41, 118, 0.18)",
            },
            "&:hover .MuiOutlinedInput-notchedOutline": {
              borderColor: "rgba(214, 41, 118, 0.26)",
            },
            "&.Mui-focused": {
              boxShadow: "0 0 0 3px rgba(214, 41, 118, 0.12)",
            },
            "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
              borderColor: IG_COLORS.pink,
              borderWidth: 2,
            },
          },
        },
      },
    },

    MuiStepper: {
      styleOverrides: {
        root: {
          paddingLeft: 0,
          paddingRight: 0,
        },
      },
    },

    MuiStepConnector: {
      styleOverrides: {
        line: {
          borderColor: "rgba(214, 41, 118, 0.2)",
        },
      },
    },

    MuiStepIcon: {
      styleOverrides: {
        root: {
          color: "rgba(214, 41, 118, 0.2)",
          "&.Mui-active": {
            color: IG_COLORS.pink,
            filter: "drop-shadow(0 2px 6px rgba(214, 41, 118, 0.35))",
          },
          "&.Mui-completed": {
            color: IG_COLORS.purple,
          },
        },
      },
    },

    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          alignItems: "center",
        },
      },
    },

    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 18,
          boxShadow: "0 24px 64px rgba(214, 41, 118, 0.2)",
          border: "1px solid rgba(214, 41, 118, 0.12)",
        },
      },
    },

    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          borderRadius: 10,
          fontSize: "0.8rem",
          fontWeight: 500,
          backgroundColor: "rgba(36, 22, 40, 0.94)",
          padding: "8px 14px",
          backdropFilter: "blur(8px)",
        },
      },
    },

    MuiLinearProgress: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          height: 6,
          backgroundColor: "rgba(214, 41, 118, 0.1)",
        },
        bar: {
          borderRadius: 8,
          backgroundImage: IG_GRADIENT,
        },
      },
    },

    MuiIconButton: {
      styleOverrides: {
        root: {
          transition: "background-color 0.18s ease, transform 0.15s ease",
          "&:hover": {
            backgroundColor: "rgba(214, 41, 118, 0.08)",
          },
        },
      },
    },
  },
};

const theme = createTheme(themeOptions);

export default theme;
