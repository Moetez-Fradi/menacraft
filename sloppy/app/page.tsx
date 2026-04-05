import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-4xl flex-col gap-6 px-4 py-10 md:px-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold">MENACRAFT Classifier Debug Console</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-300">
          Navigate to endpoint-specific forms with explainability-focused output.
        </p>
      </header>

      <section className="grid gap-4 md:grid-cols-2">
        <Link
          className="rounded-lg border border-zinc-300 p-5 transition hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          href="/analyze"
        >
          <h2 className="text-lg font-semibold">/v1/analyze</h2>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-300">
            Submit case input and inspect authenticity explainability (scores, evidence, suspicious spans, debug trace).
          </p>
        </Link>

        <Link
          className="rounded-lg border border-zinc-300 p-5 transition hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          href="/context"
        >
          <h2 className="text-lg font-semibold">/v1/context/analyze</h2>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-300">
            Validate claim consistency for an existing case and inspect context signals, references, and traces.
          </p>
        </Link>

        <Link
          className="rounded-lg border border-zinc-300 p-5 transition hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          href="/source-credibility"
        >
          <h2 className="text-lg font-semibold">Source Credibility /analyze</h2>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-300">
            Submit author/account metadata and links to evaluate source trust signals and risk level.
          </p>
        </Link>

        <Link
          className="rounded-lg border border-zinc-300 p-5 transition hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          href="/truth-retrieval"
        >
          <h2 className="text-lg font-semibold">Truth Retrieval /truth</h2>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-300">
            Verify claims against retrieved sources and inspect verdict, confidence, and correction context.
          </p>
        </Link>
      </section>
    </main>
  );
}
