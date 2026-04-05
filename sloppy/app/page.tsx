import Link from "next/link";

const cards = [
  {
    href: "/analyze",
    title: "Analyze content",
    badge: "Classifier",
    endpoint: "/v1/analyze",
    description:
      "Check a claim, post, image, or short video and get a clear authenticity summary.",
  },
  {
    href: "/context",
    title: "Check context",
    badge: "Context",
    endpoint: "/v1/context/analyze",
    description:
      "Validate a claim against an existing case to see whether surrounding context supports it.",
  },
  {
    href: "/source-credibility",
    title: "Evaluate source credibility",
    badge: "Credibility",
    endpoint: "/analyze",
    description:
      "Score account trust signals and link quality to estimate source reliability.",
  },
  {
    href: "/truth-retrieval",
    title: "Retrieve supporting truth",
    badge: "Verification",
    endpoint: "/truth",
    description:
      "Cross-check a statement with external sources and view confidence with corrections.",
  },
];

export default function Home() {
  return (
    <main className="app-page max-w-5xl">
      <header className="app-header panel p-6 md:p-8">
        <span className="endpoint-kicker">sloppy service console</span>
        <h1 className="app-title text-3xl md:text-4xl">sloppy analysis hub</h1>
        <p className="app-subtitle text-base">
          Choose a task below, fill a simple form, and review results in plain language.
        </p>
      </header>

      <section className="grid gap-4 md:grid-cols-2">
        {cards.map((card) => (
          <Link
            key={card.href}
            className="panel group p-5 transition duration-200 hover:-translate-y-0.5 hover:shadow-lg"
            href={card.href}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="inline-flex rounded-full border border-violet-400/25 bg-violet-500/12 px-2.5 py-1 text-xs font-semibold text-violet-100">
                {card.badge}
              </span>
              <span className="text-xs font-medium text-zinc-400">{card.endpoint}</span>
            </div>
            <h2 className="mt-3 text-lg font-semibold tracking-tight">{card.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-zinc-300">
              {card.description}
            </p>
            <p className="mt-4 text-sm font-medium text-violet-300 transition group-hover:translate-x-0.5">
              Open →
            </p>
          </Link>
        ))}
      </section>
    </main>
  );
}
