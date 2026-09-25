import { FaDiscord, FaGithub } from "react-icons/fa6";
import { COMPANY, COMPANY_URL, DISCORD_URL, footerGroups, GITHUB_URL } from "../data/site";

const TICKS: { h: number; o: number }[] = [
  { h: 60, o: 0.1 },
  { h: 140, o: 0.045 },
  { h: 200, o: 0.045 },
  { h: 225, o: 0.045 },
  { h: 210, o: 0.045 },
  { h: 164, o: 0.045 },
  { h: 101, o: 0.045 },
  { h: 76, o: 0.045 },
  { h: 110, o: 0.045 },
  { h: 107, o: 0.045 },
  { h: 68, o: 0.045 },
  { h: 117, o: 0.045 },
  { h: 189, o: 0.045 },
  { h: 248, o: 0.045 },
  { h: 276, o: 0.045 },
  { h: 264, o: 0.045 },
  { h: 214, o: 0.045 },
  { h: 140, o: 0.1 },
  { h: 63, o: 0.045 },
  { h: 118, o: 0.045 },
  { h: 147, o: 0.045 },
  { h: 137, o: 0.045 },
  { h: 95, o: 0.045 },
  { h: 84, o: 0.045 },
  { h: 140, o: 0.045 },
  { h: 173, o: 0.045 },
  { h: 169, o: 0.045 },
  { h: 128, o: 0.045 },
  { h: 62, o: 0.045 },
  { h: 143, o: 0.045 },
  { h: 214, o: 0.045 },
  { h: 257, o: 0.045 },
  { h: 260, o: 0.045 },
  { h: 225, o: 0.045 },
  { h: 164, o: 0.1 },
  { h: 95, o: 0.045 },
  { h: 79, o: 0.045 },
  { h: 104, o: 0.045 },
  { h: 91, o: 0.045 },
  { h: 74, o: 0.045 },
  { h: 139, o: 0.045 },
  { h: 202, o: 0.045 },
  { h: 243, o: 0.045 },
  { h: 248, o: 0.045 },
  { h: 213, o: 0.045 },
  { h: 146, o: 0.045 },
  { h: 64, o: 0.045 },
  { h: 132, o: 0.045 },
  { h: 182, o: 0.045 },
  { h: 196, o: 0.045 },
  { h: 171, o: 0.045 },
  { h: 119, o: 0.1 },
  { h: 62, o: 0.045 },
  { h: 111, o: 0.045 },
  { h: 131, o: 0.045 },
  { h: 114, o: 0.045 },
  { h: 62, o: 0.045 },
  { h: 131, o: 0.045 },
  { h: 205, o: 0.045 },
  { h: 260, o: 0.045 },
  { h: 280, o: 0.045 },
  { h: 259, o: 0.045 },
  { h: 204, o: 0.045 },
  { h: 131, o: 0.045 },
  { h: 60, o: 0.045 },
  { h: 110, o: 0.045 },
  { h: 124, o: 0.045 },
  { h: 101, o: 0.045 },
  { h: 70, o: 0.1 },
  { h: 131, o: 0.045 },
  { h: 183, o: 0.045 },
  { h: 206, o: 0.045 },
  { h: 191, o: 0.045 },
  { h: 138, o: 0.045 },
  { h: 61, o: 0.045 },
  { h: 141, o: 0.045 },
  { h: 207, o: 0.045 },
  { h: 240, o: 0.045 },
  { h: 234, o: 0.045 },
  { h: 193, o: 0.045 },
  { h: 131, o: 0.045 },
  { h: 68, o: 0.045 },
  { h: 96, o: 0.045 },
  { h: 105, o: 0.045 },
  { h: 78, o: 0.045 },
  { h: 100, o: 0.1 },
  { h: 170, o: 0.045 },
  { h: 231, o: 0.045 },
  { h: 266, o: 0.045 },
  { h: 262, o: 0.045 },
  { h: 219, o: 0.045 },
  { h: 147, o: 0.045 },
  { h: 67, o: 0.045 },
  { h: 122, o: 0.045 },
  { h: 161, o: 0.045 },
  { h: 162, o: 0.045 },
];

function Skyline() {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end gap-px px-2 sm:gap-[3px] lg:gap-[5px]" aria-hidden="true">
      {TICKS.map((tick, i) => (
        <span
          key={i}
          className={`footer-tick flex-1 rounded-t-[2px] ${
            tick.o === 0.1 ? "bg-paper/20 dark:bg-[#e6edf3]/12" : "bg-paper/10 dark:bg-[#e6edf3]/[0.045]"
          }`}
          style={{
            height: tick.h,
            animationDelay: `${i * 90}ms`,
          }}
        />
      ))}
    </div>
  );
}

export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="relative overflow-hidden bg-ink text-[#9aa39c] dark:bg-[#161b22] dark:text-[#8b949e]">
      <Skyline />

      <div className="relative z-10 mx-auto max-w-6xl px-6 pt-16 pb-14 sm:px-10 lg:px-4">
        <div className="flex flex-col gap-12 lg:grid lg:grid-cols-6 lg:gap-x-12">
          <div className="lg:col-span-2">
            <a href="#top" className="inline-flex items-center gap-2.5">
              <img src="/penguin.svg" alt="" className="h-8 w-8" />
              <strong className="text-[1.05rem] font-medium text-paper dark:text-[#e6edf3]">Pingwatch</strong>
            </a>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-[#9aa39c] dark:text-[#8b949e]">
              Uptime monitoring for NAS, storage, servers, APIs, DNS, and game infrastructure. Open-source infrastructure
              monitoring for teams who value control and transparency. Self-hosted, AGPL-3.0, no monitor limits.
            </p>
            <div className="mt-5 flex items-center gap-3">
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="GitHub"
                className="grid h-9 w-9 place-items-center text-[#9aa39c] transition-colors duration-200 hover:text-paper dark:text-[#8b949e] dark:hover:text-[#e6edf3]"
              >
                <FaGithub className="h-5 w-5" />
              </a>
              <a
                href={DISCORD_URL}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Discord"
                className="grid h-9 w-9 place-items-center text-[#9aa39c] transition-colors duration-200 hover:text-paper dark:text-[#8b949e] dark:hover:text-[#e6edf3]"
              >
                <FaDiscord className="h-5 w-5" />
              </a>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-x-8 gap-y-10 sm:gap-x-12 lg:col-span-4 lg:grid-cols-4 lg:gap-8">
            {footerGroups.map((group) => (
              <nav key={group.title} aria-label={group.title}>
                <p className="text-[11px] font-medium tracking-[0.18em] text-[#d4cbb8] uppercase dark:text-[#a8b3bc]">
                  {group.title}
                </p>
                <ul className="mt-4 grid gap-2.5">
                  {group.links.map((link) => (
                    <li key={`${group.title}-${link.label}`}>
                      <a
                        href={link.href}
                        className="inline-flex min-h-11 items-center text-sm text-[#9aa39c] transition-colors duration-200 hover:text-paper focus-visible:text-paper focus-visible:outline-offset-4 lg:min-h-0 dark:text-[#8b949e] dark:hover:text-[#e6edf3] dark:focus-visible:text-[#e6edf3]"
                        {...(link.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                      >
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </nav>
            ))}
          </div>
        </div>
      </div>

      <div className="relative z-10 border-t border-white/10 dark:border-[#30363d]">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-6 sm:px-8 lg:flex-row lg:items-center lg:justify-between lg:px-4">
          <p className="text-sm text-[#9aa39c] dark:text-[#8b949e]">© {year} Pingwatch. All rights reserved.</p>
          <div className="flex flex-col gap-1 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-6 sm:gap-y-2">
            <a
              href="#privacy"
              className="inline-flex min-h-11 items-center text-sm text-[#9aa39c] transition-colors duration-200 hover:text-paper lg:min-h-0 dark:text-[#8b949e] dark:hover:text-[#e6edf3]"
            >
              Privacy Policy
            </a>
            <a
              href="#terms"
              className="inline-flex min-h-11 items-center text-sm text-[#9aa39c] transition-colors duration-200 hover:text-paper lg:min-h-0 dark:text-[#8b949e] dark:hover:text-[#e6edf3]"
            >
              Terms of Service
            </a>
            <a
              href="#documentation"
              className="inline-flex min-h-11 items-center text-sm text-[#9aa39c] transition-colors duration-200 hover:text-paper lg:min-h-0 dark:text-[#8b949e] dark:hover:text-[#e6edf3]"
            >
              Documentation
            </a>
            <p className="text-sm text-[#c5cfc8] dark:text-[#c9d1d9]">
              Built by{" "}
              <a
                href={COMPANY_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-paper underline decoration-paper/30 underline-offset-4 transition-colors duration-200 hover:text-white hover:decoration-paper dark:text-[#e6edf3] dark:decoration-[#e6edf3]/40"
              >
                {COMPANY}
              </a>
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
