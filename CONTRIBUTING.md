# Contributing to CodeCoach

Thank you for helping improve CodeCoach. Small, focused pull requests with tests and clear provenance are easiest to review.

## Before You Start

- Search existing issues and pull requests.
- Open an issue before large architectural changes or new dependencies.
- Never post credentials, private student data, internal URLs, or production logs containing user content.
- Follow the [Code of Conduct](./CODE_OF_CONDUCT.md).

## Development Setup

Backend:

```bash
cd apps/backend
python -m venv .venv
pip install -r requirements-dev.txt
python -m pytest tests
```

Frontend:

```bash
cd apps/frontend
npm ci
npm run build
```

See the root [README](./README.md) for platform-specific environment activation and run commands.

## Change Guidelines

- Keep changes minimal and scoped to one problem.
- Preserve the API contract unless the change is explicitly coordinated.
- Add or update tests for behavior changes.
- Keep LLM access optional and preserve deterministic fallback behavior.
- Do not put secrets in `VITE_*` variables; frontend environment values are public.
- Use clear commit messages such as `fix: handle expired sessions` or `docs: clarify local setup`.

## Knowledge Contributions

Knowledge cards are distributable project content, not disposable test fixtures. A pull request that adds or modifies cards must:

- Identify the author or exact upstream source.
- Record an SPDX license identifier compatible with redistribution.
- Include the source URL and immutable revision for third-party material.
- Explain whether text or code was copied, translated, summarized, or independently written.
- Confirm technical accuracy and review AI-assisted text for accidental reproduction.

Do not submit content from books, paid courses, school handouts, coding platforms, blogs, or solution repositories unless explicit compatible permission can be verified. Algorithm ideas may be explained independently, but copyrighted wording and source code must not be copied without permission.

## Developer Certificate of Origin

All commits must include a `Signed-off-by` line created with:

```bash
git commit -s -m "type: concise summary"
```

By signing off, you certify the [Developer Certificate of Origin 1.1](https://developercertificate.org/): you have the right to submit the contribution under this repository's license.

## Pull Request Checklist

- The change has a clear problem statement.
- Backend tests pass with `python -m pytest tests`.
- Frontend builds with `npm run build` when frontend code changes.
- Documentation and `.env.example` are updated when configuration changes.
- No generated runtime data, secrets, or unexplained third-party content is included.
- Commits are signed off under the DCO.

Maintainers may ask for a smaller change, additional tests, provenance evidence, or security adjustments before merging.
