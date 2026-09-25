import { LuBuilding2, LuHardDrive, LuHouse, LuNetwork, LuServer, LuWarehouse } from "react-icons/lu";
import { useCases } from "../data/site";
import { Reveal } from "./Reveal";

const icons = [LuHardDrive, LuWarehouse, LuServer, LuHouse, LuBuilding2, LuNetwork];

export function UseCases() {
  return (
    <section id="use-cases" className="px-4 py-12">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <p className="text-sm tracking-wide text-muted uppercase">Use cases</p>
          <h2 className="font-display mt-3 text-4xl">Built for the estate you already run.</h2>
        </Reveal>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {useCases.map((item, index) => {
            const Icon = icons[index] ?? LuHardDrive;
            return (
              <Reveal key={item.title}>
                <article className="rounded-3xl border border-line bg-surface p-6 dark:border-[#30363d] dark:bg-[#161b22]">
                  <Icon className="h-6 w-6 text-teal" aria-hidden="true" />
                  <h3 className="mt-4 font-medium">{item.title}</h3>
                  <p className="mt-2 text-sm text-muted">{item.body}</p>
                </article>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
