import { dockerSnippet, hostSnippet } from "../data/site";
import { Reveal } from "./Reveal";

export function Deployment() {
  return (
    <section id="documentation" className="px-4 py-24">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <p className="text-sm tracking-wide text-muted uppercase">03 · Documentation</p>
          <h2 className="font-display mt-3 max-w-2xl text-4xl text-balance">Run it with Docker, or directly on the host.</h2>
          <p className="mt-4 max-w-2xl text-muted">
            Pingwatch is self-hosted. Compose is the production path. Direct uvicorn on the host is the reliable way to
            ICMP-ping LAN devices from macOS Docker Desktop. TCP, DNS, WebSocket, gRPC, and game checks run the same way.
          </p>
        </Reveal>
        <div className="mt-10 grid gap-4 lg:grid-cols-2">
          <Reveal>
            <article id="docker" className="h-full scroll-mt-24 rounded-3xl border border-line bg-ink p-6 text-[#e6edf3] dark:border-[#30363d]">
              <p className="text-sm text-[#8b949e]">Docker</p>
              <h3 className="mt-2 text-xl font-medium text-white">Compose starts MySQL and the app</h3>
              <pre className="mt-5 overflow-x-auto rounded-2xl bg-black/40 p-4 font-mono text-sm leading-relaxed">
                <code>{dockerSnippet}</code>
              </pre>
              <p className="mt-4 text-sm text-[#8b949e]">Then open http://127.0.0.1:8000 and sign in. Copy .env.example first.</p>
            </article>
          </Reveal>
          <Reveal>
            <article id="direct" className="h-full scroll-mt-24 rounded-3xl border border-line bg-surface p-6 dark:border-[#30363d] dark:bg-[#161b22]">
              <p className="text-sm text-muted">Direct / non-Docker</p>
              <h3 className="mt-2 text-xl font-medium">venv, pip, uvicorn</h3>
              <pre className="mt-5 overflow-x-auto rounded-2xl bg-paper p-4 font-mono text-sm leading-relaxed dark:bg-[#0d1117]">
                <code>{hostSnippet}</code>
              </pre>
              <p className="mt-4 text-sm text-muted">Point .env at MySQL. Python 3.9+ (3.12 recommended). ICMP ping must be available on the host for Ping checks.</p>
            </article>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
