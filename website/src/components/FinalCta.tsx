import { DEMO_URL } from "../data/site";
import { Reveal } from "./Reveal";

export function FinalCta() {
  return (
    <section className="px-4 py-24">
      <Reveal className="mx-auto max-w-6xl rounded-[32px] border border-line bg-ink px-8 py-16 text-center text-[#e6edf3] dark:border-[#30363d]">
        <p className="text-sm tracking-wide text-[#8b949e] uppercase">Get started</p>
        <h2 className="font-display mt-4 text-4xl text-white text-balance sm:text-5xl">Know when your infrastructure is down.</h2>
        <p className="mx-auto mt-4 max-w-xl text-[#8b949e]">
          Deploy Pingwatch on your network, or open the Superstack demo and walk the same dashboard your operators will use.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <a href="#documentation" className="rounded-full bg-white px-5 py-3 text-sm font-medium text-ink">
            Get Pingwatch
          </a>
          <a
            href={DEMO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-full border border-white/20 px-5 py-3 text-sm font-medium text-white"
          >
            View Demo
          </a>
        </div>
      </Reveal>
    </section>
  );
}
