This is the MENACRAFT manual web console built with [Next.js](https://nextjs.org).

## Getting Started

First, run MENACRAFT services (from repo root):

```bash
docker compose up --build
```

Then run the web app:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

The UI supports two modes:

- `orchestrator`: calls `POST /analyze` (same extension-compatible path)
- `direct`: adapter mode (`anonymize + classify + context + source + truth`)

Optional environment variables for the Next app server:

- `ORCHESTRATOR_URL` (default `http://localhost:8080`)
- `ANONYMIZER_URL` (default `http://localhost:8081`)
- `ML_SERVICE_URL` (default `http://localhost:8082`)
- `TRUTH_SERVICE_URL` (default `http://localhost:8083`)
- `CONTEXT_SERVICE_URL` (default `http://localhost:8084`)

Use this console to submit manual text, links, images, and video files and inspect per-axis outputs while iterating on services.
