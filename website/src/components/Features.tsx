import type { IconType } from "react-icons";
import {
  LuActivity,
  LuAlarmClock,
  LuChartNoAxesCombined,
  LuContainer,
  LuFeather,
  LuHistory,
  LuLayoutDashboard,
  LuMonitor,
  LuServer,
  LuTriangleAlert,
  LuWifi,
} from "react-icons/lu";
import { MdDevices } from "react-icons/md";
import { features } from "../data/site";
import { Reveal } from "./Reveal";

const icons: Record<string, IconType> = {
  activity: LuWifi,
  pulse: LuActivity,
  timer: LuAlarmClock,
  devices: MdDevices,
  history: LuHistory,
  alert: LuTriangleAlert,
  chart: LuChartNoAxesCombined,
  stats: LuMonitor,
  layout: LuLayoutDashboard,
  feather: LuFeather,
  docker: LuContainer,
  server: LuServer,
};

export function Features() {
  return (
    <section id="features" className="px-4 py-24">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <p className="text-sm tracking-wide text-muted uppercase">00 · Features</p>
          <h2 className="font-display mt-3 max-w-2xl text-4xl text-balance">The signals that matter for availability.</h2>
          <p className="mt-4 max-w-2xl text-muted">
            Pingwatch covers Ping, TCP Port, DNS, WebSocket, gRPC health, and native game-server queries. It does not
            replace APM or a network-management suite.
          </p>
        </Reveal>
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((item) => {
            const Icon = icons[item.icon] ?? LuActivity;
            return (
              <Reveal key={item.title}>
                <article className="h-full rounded-3xl border border-line bg-surface p-6 transition hover:-translate-y-0.5 hover:shadow-sm dark:border-[#30363d] dark:bg-[#161b22]">
                  <Icon className="h-6 w-6 text-teal" aria-hidden="true" />
                  <h3 className="mt-4 text-lg font-medium">{item.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{item.body}</p>
                </article>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
