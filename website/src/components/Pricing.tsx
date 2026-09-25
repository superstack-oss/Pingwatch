import { COMPANY_URL, DEMO_URL } from "../data/site";
import { Reveal } from "./Reveal";

export function Pricing() {
  return (
    <section id="pricing" className="px-4 py-24">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <p className="text-sm tracking-wide text-muted uppercase">04 · Pricing</p>
          <h2 className="font-display mt-3 text-4xl">Self-hosted first. Commercial terms when you need them.</h2>
          <p className="mt-4 max-w-2xl text-muted">
            Published list prices are not set on this page yet. The plans below are the commercial structure—amounts will be
            added when Superstack announces them.
          </p>
        </Reveal>
        <div className="mt-10 grid gap-4 lg:grid-cols-3">
          <Reveal>
            <article className="flex h-full flex-col rounded-3xl border border-line bg-surface p-7 dark:border-[#30363d] dark:bg-[#161b22]">
              <h3 className="text-xl font-medium">Self-hosted</h3>
              <p className="mt-2 text-3xl font-medium">Price TBA</p>
              <p className="mt-3 text-sm text-muted">Deploy Pingwatch and MySQL in your environment with Docker or uvicorn on the host.</p>
              <ul className="mt-6 grid gap-2 text-sm text-muted">
                <li>Ping, TCP, DNS, WebSocket, gRPC, Game</li>
                <li>Dashboard, Analytics, Incidents</li>
                <li>Your data stays on your servers</li>
              </ul>
              <a href="#documentation" className="mt-8 rounded-full bg-ink px-4 py-3 text-center text-sm text-paper dark:bg-[#e6edf3] dark:text-[#0d1117]">
                Get Pingwatch
              </a>
            </article>
          </Reveal>
          <Reveal>
            <article className="flex h-full flex-col rounded-3xl border border-teal bg-surface p-7 dark:border-teal dark:bg-[#161b22]">
              <h3 className="text-xl font-medium">Commercial</h3>
              <p className="mt-2 text-3xl font-medium">Contact us</p>
              <p className="mt-3 text-sm text-muted">For organizations that want support, onboarding, or a commercial agreement from Superstack.</p>
              <ul className="mt-6 grid gap-2 text-sm text-muted">
                <li>Talk to Superstack Inc.</li>
                <li>Pricing provided on request</li>
                <li>Same Pingwatch product, commercially backed</li>
              </ul>
              <a
                href={COMPANY_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-8 rounded-full border border-line px-4 py-3 text-center text-sm dark:border-[#30363d]"
              >
                Contact Superstack
              </a>
            </article>
          </Reveal>
          <Reveal>
            <article className="flex h-full flex-col rounded-3xl border border-line bg-surface p-7 dark:border-[#30363d] dark:bg-[#161b22]">
              <h3 className="text-xl font-medium">Hosted demo</h3>
              <p className="mt-2 text-3xl font-medium">Try it</p>
              <p className="mt-3 text-sm text-muted">A public demonstration instance is available while you evaluate the product.</p>
              <ul className="mt-6 grid gap-2 text-sm text-muted">
                <li>demo-pingwatch.superstack.in</li>
                <li>No install required to look around</li>
                <li>Not a substitute for self-hosting production</li>
              </ul>
              <a
                href={DEMO_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-8 rounded-full border border-line px-4 py-3 text-center text-sm dark:border-[#30363d]"
              >
                View Demo
              </a>
            </article>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
