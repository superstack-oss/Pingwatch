import { DEMO_URL } from "../data/site";
import { StatusPill } from "./StatusPill";

const preview = [
  { ci: "CI-0142", name: "Studio NAS", host: "192.168.1.10", status: "Up", rtt: "4.2 ms", kind: "NAS", monitor: "Ping" },
  { ci: "CI-0208", name: "SAN Array", host: "10.12.4.20", status: "Warning", rtt: "218 ms", kind: "Storage", monitor: "TCP Port" },
  { ci: "CI-0440", name: "App Server", host: "10.8.2.15", status: "Down", rtt: "timeout", kind: "Server", monitor: "gRPC" },
];

export function Hero() {
  return (
    <section className="relative overflow-hidden px-4 pt-16 pb-8 sm:pt-24">
      <div className="net-grid pointer-events-none absolute inset-0 opacity-70" aria-hidden="true" />
      <div className="relative mx-auto grid max-w-6xl gap-14 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
        <div className="hero-enter">
          <p className="text-sm tracking-wide text-muted uppercase">Uptime monitoring</p>
          <h1 className="font-display mt-4 max-w-xl text-5xl leading-[1.05] text-balance sm:text-6xl">
            Know when your infrastructure is reachable.
          </h1>
          <p className="mt-6 max-w-lg text-lg leading-relaxed text-muted">
            Pingwatch watches NAS, storage, servers, APIs, DNS names, and game servers. Six monitor types share one
            dashboard for status, response time, and history.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href="#documentation" className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-paper dark:bg-[#e6edf3] dark:text-[#0d1117]">
              Get Pingwatch
            </a>
            <a
              href={DEMO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-full border border-line bg-surface px-5 py-3 text-sm font-medium dark:border-[#30363d] dark:bg-[#161b22]"
            >
              View Demo
            </a>
          </div>
          <p className="mt-6 text-sm text-muted">Self-hosted · Docker or host · Developed by Superstack Inc.</p>
        </div>
        <div className="hero-enter">
          <div className="rounded-[28px] border border-line bg-surface p-4 shadow-sm dark:border-[#30363d] dark:bg-[#161b22]">
            <div className="mb-4 flex items-center justify-between px-1">
              <div className="flex items-center gap-2">
                <img src="/penguin.svg" alt="" className="h-6 w-6" />
                <strong className="text-sm font-medium">Uptime</strong>
              </div>
              <span className="text-xs text-muted">Last sweep just now</span>
            </div>
            <div className="mb-4 grid grid-cols-4 gap-2">
              {[
                ["Up", "18", "text-up"],
                ["Down", "1", "text-down"],
                ["Warning", "1", "text-warn"],
                ["Unknown", "0", "text-unknown"],
              ].map(([label, value, color]) => (
                <article key={label} className="rounded-2xl border border-line bg-paper px-3 py-2 dark:border-[#30363d] dark:bg-[#0d1117]">
                  <span className="text-[0.7rem] text-muted">{label}</span>
                  <strong className={`block text-xl font-medium ${color}`}>{value}</strong>
                </article>
              ))}
            </div>
            <div className="overflow-hidden rounded-2xl border border-line dark:border-[#30363d]">
              <table className="w-full text-left text-sm">
                <thead className="bg-paper text-[0.7rem] tracking-wide text-muted uppercase dark:bg-[#0d1117]">
                  <tr>
                    <th className="px-3 py-2 font-medium">CI</th>
                    <th className="px-3 py-2 font-medium">Name</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="hidden px-3 py-2 font-medium sm:table-cell">Monitor</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.map((row) => (
                    <tr key={row.ci} className="border-t border-line dark:border-[#30363d]">
                      <td className="px-3 py-2.5 font-mono text-xs">{row.ci}</td>
                      <td className="px-3 py-2.5">
                        {row.name}
                        <small className="block font-mono text-[0.7rem] text-muted">{row.host}</small>
                      </td>
                      <td className="px-3 py-2.5">
                        <StatusPill status={row.status} live={row.status !== "Paused"} />
                      </td>
                      <td className="hidden px-3 py-2.5 text-xs sm:table-cell">{row.monitor}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
