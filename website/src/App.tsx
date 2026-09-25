import CssBaseline from "@mui/material/CssBaseline";
import { StyledEngineProvider, ThemeProvider } from "@mui/material/styles";
import { useEffect, useMemo, useState } from "react";
import { DashboardShowcase } from "./components/DashboardShowcase";
import { Deployment } from "./components/Deployment";
import { FAQ } from "./components/FAQ";
import { Features } from "./components/Features";
import { FinalCta } from "./components/FinalCta";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { HowItWorks } from "./components/HowItWorks";
import { Legal } from "./components/Legal";
import { MonitorTypes } from "./components/MonitorTypes";
import { Pricing } from "./components/Pricing";
import { Problem } from "./components/Problem";
import { UseCases } from "./components/UseCases";
import { WhyPingwatch } from "./components/WhyPingwatch";
import { useDarkMode } from "./hooks/useDarkMode";
import { makeMuiTheme } from "./theme";

function readHash() {
  return window.location.hash.replace("#", "");
}

export default function App() {
  const { dark, toggle } = useDarkMode();
  const theme = useMemo(() => makeMuiTheme(dark), [dark]);
  const [hash, setHash] = useState(readHash);

  useEffect(() => {
    const onHash = () => setHash(readHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const legal = hash === "privacy" || hash === "terms" ? hash : null;

  return (
    <StyledEngineProvider injectFirst>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:m-3 focus:rounded-full focus:bg-ink focus:px-4 focus:py-2 focus:text-paper">
          Skip to content
        </a>
        <div id="top">
          <Header dark={dark} onToggleTheme={toggle} />
          {legal ? (
            <Legal kind={legal} />
          ) : (
            <main id="main">
              <Hero />
              <Problem />
              <Features />
              <MonitorTypes />
              <DashboardShowcase />
              <HowItWorks />
              <UseCases />
              <Deployment />
              <WhyPingwatch />
              <Pricing />
              <FAQ />
              <FinalCta />
            </main>
          )}
          <Footer />
        </div>
      </ThemeProvider>
    </StyledEngineProvider>
  );
}
