import { COMPANY, COMPANY_URL } from "../data/site";

export function Legal({ kind }: { kind: "privacy" | "terms" }) {
  const title = kind === "privacy" ? "Privacy" : "Terms";
  return (
    <main className="mx-auto max-w-2xl px-4 py-20">
      <a href="#top" className="text-sm text-muted">
        ← Back to Pingwatch
      </a>
      <h1 className="font-display mt-6 text-4xl">{title}</h1>
      <p className="mt-6 leading-relaxed text-muted">
        This is a placeholder {title.toLowerCase()} notice for the Pingwatch commercial site. The full policy will be published
        by {COMPANY} before general availability. Until then, treat demo-pingwatch.superstack.in as an evaluation environment
        and contact Superstack for production use.
      </p>
      <p className="mt-4 text-sm text-muted">
        <a href={COMPANY_URL} target="_blank" rel="noopener noreferrer">
          superstack.in
        </a>
      </p>
    </main>
  );
}
