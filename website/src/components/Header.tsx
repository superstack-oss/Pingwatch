import Drawer from "@mui/material/Drawer";
import { useState } from "react";
import { HiOutlineMoon, HiOutlineSun } from "react-icons/hi2";
import { LuMenu, LuX } from "react-icons/lu";
import { DEMO_URL, nav } from "../data/site";

export function Header({ dark, onToggleTheme }: { dark: boolean; onToggleTheme: () => void }) {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 px-4 pt-4">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
        <nav
          className="flex items-center gap-1 rounded-full border border-line/80 bg-surface/90 px-2 py-1.5 shadow-sm backdrop-blur-md dark:border-[#30363d] dark:bg-[#161b22]/90"
          aria-label="Primary"
        >
          <a href="#top" className="flex items-center gap-2 rounded-full py-1 pr-3 pl-1.5">
            <img src="/penguin.svg" alt="" className="h-7 w-7" />
            <span className="font-medium">Pingwatch</span>
          </a>
          <div className="hidden items-center lg:flex">
            {nav.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="rounded-full px-2.5 py-1.5 text-sm text-muted transition hover:text-ink dark:text-[#8b949e] dark:hover:text-[#e6edf3]"
              >
                {item.label}
              </a>
            ))}
          </div>
        </nav>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onToggleTheme}
            className="grid h-10 w-10 place-items-center rounded-full border border-line bg-surface text-muted transition hover:text-ink dark:border-[#30363d] dark:bg-[#161b22] dark:text-[#8b949e]"
            aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
          >
            {dark ? <HiOutlineSun className="h-5 w-5" /> : <HiOutlineMoon className="h-5 w-5" />}
          </button>
          <a
            href={DEMO_URL}
            className="hidden rounded-full border border-line bg-surface px-4 py-2 text-sm font-medium dark:border-[#30363d] dark:bg-[#161b22] sm:inline-flex"
          >
            View demo
          </a>
          <a href="#documentation" className="hidden rounded-full bg-ink px-4 py-2 text-sm font-medium text-paper dark:bg-[#e6edf3] dark:text-[#0d1117] sm:inline-flex">
            Get Pingwatch
          </a>
          <button
            type="button"
            className="grid h-10 w-10 place-items-center rounded-full border border-line bg-surface lg:hidden dark:border-[#30363d] dark:bg-[#161b22]"
            aria-label="Open menu"
            onClick={() => setOpen(true)}
          >
            <LuMenu className="h-5 w-5" />
          </button>
        </div>
      </div>
      <Drawer anchor="right" open={open} onClose={() => setOpen(false)}>
        <div className="flex h-full w-72 flex-col bg-paper p-5 dark:bg-[#0d1117] dark:text-[#e6edf3]">
          <div className="mb-6 flex items-center justify-between">
            <span className="font-medium">Pingwatch</span>
            <button type="button" aria-label="Close menu" onClick={() => setOpen(false)}>
              <LuX className="h-5 w-5" />
            </button>
          </div>
          <div className="grid gap-1">
            {nav.map((item) => (
              <a key={item.href} href={item.href} className="rounded-xl px-3 py-3 text-muted" onClick={() => setOpen(false)}>
                {item.label}
              </a>
            ))}
          </div>
          <a href="#documentation" className="mt-6 rounded-full bg-ink px-4 py-3 text-center text-paper dark:bg-[#e6edf3] dark:text-[#0d1117]" onClick={() => setOpen(false)}>
            Get Pingwatch
          </a>
          <a href={DEMO_URL} className="mt-2 rounded-full border border-line px-4 py-3 text-center dark:border-[#30363d]" onClick={() => setOpen(false)}>
            View demo
          </a>
        </div>
      </Drawer>
    </header>
  );
}
