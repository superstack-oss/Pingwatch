import { useMemo, useState } from "react";
import { StatusPill } from "./StatusPill";
import { Reveal } from "./Reveal";

type Device = {
  ci: string;
  name: string;
  host: string;
  status: "Up" | "Down" | "Warning" | "Unknown" | "Paused";
  rtt: string;
  avg: string;
  uptime: string;
  lastDown: string;
  kind: string;
  monitor: string;
  monitoring: string;
  history: Array<number | null>;
};

const fleet: Device[] = [
  {
    ci: "CI-0142",
    name: "Studio NAS",
    host: "192.168.1.10",
    status: "Up",
    rtt: "4.2 ms",
    avg: "5.1 ms",
    uptime: "99.98%",
    lastDown: "12d ago",
    kind: "NAS",
    monitor: "Ping",
    monitoring: "Active",
    history: [4, 5, 4, 6, 5, 4, 5, 7, 4, 5, 4, 4],
  },
  {
    ci: "CI-0208",
    name: "SAN Array",
    host: "10.12.4.20",
    status: "Warning",
    rtt: "218 ms",
    avg: "94 ms",
    uptime: "99.12%",
    lastDown: "3h ago",
    kind: "Storage",
    monitor: "TCP Port",
    monitoring: "Active",
    history: [42, 48, 51, 88, 120, 160, 210, 218, 190, 140, 96, 88],
  },
  {
    ci: "CI-0311",
    name: "Core Switch",
    host: "10.0.0.1",
    status: "Up",
    rtt: "1.1 ms",
    avg: "1.4 ms",
    uptime: "100%",
    lastDown: "Never",
    kind: "Network",
    monitor: "Ping",
    monitoring: "Active",
    history: [1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 1, 1],
  },
  {
    ci: "CI-0440",
    name: "App Server",
    host: "10.8.2.15",
    status: "Down",
    rtt: "timeout",
    avg: "12 ms",
    uptime: "97.40%",
    lastDown: "8 min ago",
    kind: "Server",
    monitor: "gRPC",
    monitoring: "Active",
    history: [11, 12, 10, 13, 12, null, null, null, null, null, null, null],
  },
  {
    ci: "CI-0517",
    name: "Backup NAS",
    host: "192.168.1.20",
    status: "Paused",
    rtt: "—",
    avg: "6.8 ms",
    uptime: "99.91%",
    lastDown: "21d ago",
    kind: "NAS",
    monitor: "DNS",
    monitoring: "Service mode",
    history: [6, 7, 6, 8, 7, 6, 7, 6, 6, 7, 6, 6],
  },
  {
    ci: "CI-0622",
    name: "Valheim",
    host: "10.8.2.40",
    status: "Up",
    rtt: "8.6 ms",
    avg: "9.2 ms",
    uptime: "99.91%",
    lastDown: "6d ago",
    kind: "Server",
    monitor: "Game server",
    monitoring: "Active",
    history: [8, 9, 8, 10, 9, 8, 9, 11, 8, 9, 8, 8],
  },
];

function Spark({ history }: { history: Array<number | null> }) {
  const max = Math.max(...history.filter((item): item is number => item != null), 1);
  return (
    <span className="spark inline-flex h-5 items-end gap-0.5" aria-hidden="true">
      {history.map((item, index) => {
        const height = item == null ? 3 : Math.max(4, Math.round((item / max) * 18));
        return <i key={index} className={item == null ? "miss" : ""} style={{ height }} />;
      })}
    </span>
  );
}

export function DashboardShowcase() {
  const [selected, setSelected] = useState(fleet[0].ci);
  const device = useMemo(() => fleet.find((item) => item.ci === selected) ?? fleet[0], [selected]);

  return (
    <section id="dashboard" className="px-4 py-12">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <p className="text-sm tracking-wide text-muted uppercase">01 · Dashboard</p>
          <h2 className="font-display mt-3 max-w-2xl text-4xl text-balance">The operational view, without the noise.</h2>
          <p className="mt-4 max-w-2xl text-muted">
            Select a CI to open the same kind of detail Pingwatch shows in the product: status, response, availability, and
            last down.
          </p>
        </Reveal>
        <Reveal className="mt-10 overflow-hidden rounded-[28px] border border-line bg-surface shadow-sm dark:border-[#30363d] dark:bg-[#161b22]">
          <div className="grid lg:grid-cols-[1.2fr_0.8fr]">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="bg-paper text-[0.7rem] tracking-wide text-muted uppercase dark:bg-[#0d1117]">
                  <tr>
                    <th className="px-4 py-3 font-medium">CI</th>
                    <th className="px-4 py-3 font-medium">Name</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Monitor</th>
                    <th className="px-4 py-3 font-medium">Response</th>
                    <th className="px-4 py-3 font-medium">Avg</th>
                    <th className="px-4 py-3 font-medium">Uptime</th>
                    <th className="px-4 py-3 font-medium">Last down</th>
                  </tr>
                </thead>
                <tbody>
                  {fleet.map((row) => (
                    <tr
                      key={row.ci}
                      tabIndex={0}
                      aria-selected={selected === row.ci}
                      className={`cursor-pointer border-t border-line transition dark:border-[#30363d] ${
                        selected === row.ci ? "bg-cream/70 dark:bg-[#1c2330]" : "hover:bg-paper dark:hover:bg-[#0d1117]"
                      }`}
                      onClick={() => setSelected(row.ci)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelected(row.ci);
                        }
                      }}
                    >
                      <td className="px-4 py-3 font-mono text-xs">{row.ci}</td>
                      <td className="px-4 py-3">
                        {row.name}
                        <small className="block font-mono text-[0.7rem] text-muted">{row.host}</small>
                      </td>
                      <td className="px-4 py-3">
                        <StatusPill status={row.status} live={row.status === "Up" || row.status === "Warning"} />
                      </td>
                      <td className="px-4 py-3 text-muted">{row.monitor}</td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-2">
                          <Spark history={row.history} />
                          <span className="font-mono text-xs">{row.rtt}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{row.avg}</td>
                      <td className="px-4 py-3 font-mono text-xs">{row.uptime}</td>
                      <td className="px-4 py-3 text-muted">{row.lastDown}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <aside className="border-t border-line p-6 lg:border-t-0 lg:border-l dark:border-[#30363d]" aria-live="polite">
              <p className="text-xs tracking-wide text-muted uppercase">Device detail</p>
              <h3 className="mt-2 text-2xl font-medium">{device.name}</h3>
              <p className="mt-1 font-mono text-sm text-muted">
                {device.host} · {device.kind} · {device.monitor}
              </p>
              <div className="mt-4">
                <StatusPill status={device.status} live={device.status === "Up"} />
              </div>
              <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-muted">Current response</dt>
                  <dd className="mt-1 font-medium">{device.rtt}</dd>
                </div>
                <div>
                  <dt className="text-muted">Average response</dt>
                  <dd className="mt-1 font-medium">{device.avg}</dd>
                </div>
                <div>
                  <dt className="text-muted">Availability</dt>
                  <dd className="mt-1 font-medium">{device.uptime}</dd>
                </div>
                <div>
                  <dt className="text-muted">Last down</dt>
                  <dd className="mt-1 font-medium">{device.lastDown}</dd>
                </div>
                <div>
                  <dt className="text-muted">Monitoring</dt>
                  <dd className="mt-1 font-medium">{device.monitoring}</dd>
                </div>
                <div>
                  <dt className="text-muted">Monitor</dt>
                  <dd className="mt-1 font-medium">{device.monitor}</dd>
                </div>
                <div>
                  <dt className="text-muted">Type</dt>
                  <dd className="mt-1 font-medium">{device.kind}</dd>
                </div>
              </dl>
              <p className="mt-6 text-xs text-muted">
                In the app this opens the full device page: Recent / Day / Week / Month history, outages, and Investigate.
              </p>
            </aside>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
