import { why } from "../data/site";
import { Reveal } from "./Reveal";

export function WhyPingwatch() {
  return (
    <section id="about" className="scroll-mt-24 px-4 py-12">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <p className="text-sm tracking-wide text-muted uppercase">Why Pingwatch</p>
          <h2 className="font-display mt-3 max-w-2xl text-4xl text-balance">Simple monitoring for the infrastructure that matters.</h2>
        </Reveal>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {why.map((item) => (
            <Reveal key={item.title}>
              <article className="rounded-3xl border border-line bg-surface p-6 dark:border-[#30363d] dark:bg-[#161b22]">
                <h3 className="font-medium">{item.title}</h3>
                <p className="mt-2 text-sm text-muted">{item.body}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
