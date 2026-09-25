import { steps } from "../data/site";
import { Reveal } from "./Reveal";

export function HowItWorks() {
  return (
    <section id="how-it-works" className="px-4 py-24">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <p className="text-sm tracking-wide text-muted uppercase">02 · How it works</p>
          <h2 className="font-display mt-3 max-w-2xl text-4xl text-balance">Choose a monitor. Pingwatch does the rest.</h2>
        </Reveal>
        <ol className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {steps.map((step) => (
            <Reveal key={step.n}>
              <li className="h-full rounded-3xl border border-line bg-surface p-6 dark:border-[#30363d] dark:bg-[#161b22]">
                <span className="font-mono text-sm text-teal">{step.n}</span>
                <h3 className="mt-4 text-lg font-medium">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{step.body}</p>
              </li>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}
