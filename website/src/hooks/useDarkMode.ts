import { useEffect, useState } from "react";

const KEY = "pingwatch-site-theme";

function readInitial() {
  if (typeof window === "undefined") return false;
  const stored = localStorage.getItem(KEY);
  if (stored === "dark") return true;
  if (stored === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function useDarkMode() {
  const [dark, setDark] = useState(readInitial);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem(KEY, dark ? "dark" : "light");
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#0d1117" : "#f4f1ea");
  }, [dark]);

  return { dark, toggle: () => setDark((value) => !value) };
}
