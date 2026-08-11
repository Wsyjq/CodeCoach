# CodeCoach Frontend

React and Vite frontend for the CodeCoach learning workspace.

## Run

Start the backend on port `8000`, then run:

```bash
npm ci
npm run dev
```

The Vite development server proxies `/api` and `/health` to `http://localhost:8000`.

## Build

```bash
npm run build
```

The production Docker image serves the generated frontend and FastAPI from the same origin.
