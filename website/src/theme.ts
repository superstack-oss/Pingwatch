import { createTheme } from "@mui/material/styles";

export function makeMuiTheme(dark: boolean) {
  return createTheme({
    palette: {
      mode: dark ? "dark" : "light",
      primary: { main: "#1a6758" },
      background: {
        default: dark ? "#0d1117" : "#f4f1ea",
        paper: dark ? "#161b22" : "#fffdf8",
      },
      text: {
        primary: dark ? "#e6edf3" : "#18222b",
        secondary: dark ? "#8b949e" : "#5c675f",
      },
      divider: dark ? "#30363d" : "#ddd6c8",
    },
    typography: {
      fontFamily: "Outfit, ui-sans-serif, system-ui, sans-serif",
    },
    shape: { borderRadius: 14 },
    components: {
      MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
      MuiAccordion: {
        styleOverrides: {
          root: {
            boxShadow: "none",
            border: "1px solid",
            borderColor: dark ? "#30363d" : "#ddd6c8",
            borderRadius: "16px !important",
            marginBottom: 10,
            "&:before": { display: "none" },
            "&.Mui-expanded": { margin: "0 0 10px" },
          },
        },
      },
      MuiAccordionSummary: {
        styleOverrides: {
          root: { minHeight: 64, paddingInline: 20 },
          content: { margin: "16px 0", fontWeight: 500 },
        },
      },
      MuiAccordionDetails: {
        styleOverrides: { root: { padding: "0 20px 20px", color: dark ? "#8b949e" : "#5c675f" } },
      },
    },
  });
}
