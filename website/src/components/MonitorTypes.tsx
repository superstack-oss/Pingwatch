import { LuGamepad2, LuGlobe, LuNetwork, LuPlug, LuRadio, LuWifi } from "react-icons/lu";
import { monitorTypes } from "../data/site";
import { Reveal } from "./Reveal";

const icons = [LuWifi, LuPlug, LuGlobe, LuRadio, LuNetwork, LuGamepad2];

export function MonitorTypes() {
  return (
    <section id="monitors" className="px-4 py-12">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <p className="text-sm tracking-wide text-muted uppercase">Monitor types</p>
          <h2 className="font-display mt-3 max-w-2xl text-4xl text-balance">Six ways to ask if something is up.</h2>
          <p className="mt-4 max-w-2xl text-muted">
            Asset type stays NAS, storage, SAN, network, server, or other. The check itself is one of these monitors,
            chosen when you add the device.
          </p>
        </Reveal>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {monitorTypes.map((item, index) => {
            const Icon = icons[index] ?? LuWifi;
            return (
              <Reveal key={item.title}>
                <article className="h-full rounded-3xl border border-line bg-surface p-6 dark:border-[#30363d] dark:bg-[#161b22]">
                  <Icon className="h-6 w-6 text-teal" aria-hidden="true" />
                  <h3 className="mt-4 font-medium">{item.title}</h3>
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
