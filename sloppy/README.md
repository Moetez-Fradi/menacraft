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

The UI now includes dedicated endpoint pages:

- `/analyze`: form for classifier `POST /v1/analyze` with explainability output, links input, and image/video uploads
- `/context`: form for classifier `POST /v1/context/analyze` with explainability output
- `/source-credibility`: form for source credibility `POST /analyze`
- `/truth-retrieval`: form for truth retrieval `POST /truth`

Optional environment variables for the Next app server:

- `ML_SERVICE_URL` (default `http://localhost:8082`)
- `SOURCE_CREDIBILITY_URL` (default `http://localhost:8084`)
- `TRUTH_SERVICE_URL` (default `http://localhost:8083`)

Use this console to submit manual text and claims directly to classifier endpoints and inspect explainability outputs while iterating on the classifier service.
