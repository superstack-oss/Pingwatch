import { problems } from "../data/site";
import { Reveal } from "./Reveal";

export function Problem() {
  return (
    <section id="product" className="px-4 py-20">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <p className="text-sm tracking-wide text-muted uppercase">The problem</p>
          <h2 className="font-display mt-3 max-w-2xl text-4xl text-balance">Infrastructure fails quietly until someone needs it.</h2>
        </Reveal>
        <div className="mt-12 grid gap-4 md:grid-cols-2">
          {problems.map((item) => (
            <Reveal key={item.title}>
              <article className="rounded-3xl border border-line bg-surface p-6 dark:border-[#30363d] dark:bg-[#161b22]">
                <h3 className="text-lg font-medium">{item.title}</h3>
                <p className="mt-2 text-muted">{item.body}</p>
              </article>
            </Reveal>
          ))}
        </div>
        <Reveal className="mt-8 rounded-3xl border border-teal/20 bg-teal/5 p-6 md:p-8">
          <h3 className="text-xl font-medium">What Pingwatch does instead</h3>
          <p className="mt-3 max-w-3xl leading-relaxed text-muted">
            Pingwatch checks the CIs you care about on a schedule you control, keeps the check history, and puts Up / Down /
            Warning / Unknown on one dashboard. Device detail adds availability, last response, last down, and outages.
            Repeated failures can open an incident with work notes so the timeline is not lost in chat.
          </p>
        </Reveal>
      </div>
    </section>
  );
}
