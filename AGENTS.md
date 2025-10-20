<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# Repository Guidelines

## Project Structure & Module Organization
- `backend/templates/`: YAML templates covering statutory disclosure formats; keep filenames snake_case (e.g., `securities_report.yaml`) and update the Japanese README in UTF-8 when adding sections.
- `openspec/project.md`: Canonical development conventions—reread before kicking off new scopes.
- `openspec/changes/`: Active proposals such as `add-disclosure-comparison-tool`; keep `proposal.md`, `design.md`, and `tasks.md` synchronized with implementation.
- `openspec/specs/`: Authoritative requirements; add deltas via `openspec` instead of editing approved specs in place.
- `openspec/AGENTS.md`: Assistant workflow primer; consult whenever scope, change control, or spec etiquette is uncertain.

## Build, Test, and Development Commands
- `openspec list` / `openspec validate <change-id> --strict`: Inspect ongoing proposals and confirm spec hygiene before coding.
- Backend (Python 3.11+): create a virtual env (`python -m venv .venv` then `source .venv/bin/activate` or `.\.venv\Scripts\activate` on Windows), install dependencies (`pip install -r backend/requirements.txt` once defined), run the API with `uvicorn backend.app:app --reload`, and execute tests via `pytest backend/tests`.
- Frontend (Next.js 14+): install packages (`npm install`), start the dev server (`npm run dev`), lint (`npm run lint`), and run unit tests (`npm test`).
- Full stack: prefer containers for parity; once the compose file lands, run `docker compose up --build` to start API, workers, and Redis locally.

## Coding Style & Naming Conventions
- **Python**: Enforce PEP 8 with automatic formatters (`black`, `isort`); modules snake_case, classes PascalCase, functions snake_case, constants UPPER_SNAKE_CASE.
- **TypeScript**: Apply ESLint + Prettier (Airbnb baseline); files kebab-case (e.g., `document-upload.tsx`), components PascalCase, hooks camelCase prefixed with `use`.
- **YAML templates**: Keys stay snake_case and `document_type` identifiers match the filename to simplify lookups.

## Testing Guidelines
- Target >= 80% coverage across backend (`pytest`, `httpx` integration) and frontend (`Jest`, `Playwright` E2E).
- Mirror package layout: store backend tests under `backend/tests/<module>_test.py` and frontend suites under `frontend/__tests__/`.
- Provide fixture PDFs with anonymized data and clean up temporary artifacts created during parsing pipelines.
- Run `openspec validate <change-id>` before checking off items in `tasks.md`.

## Commit & Pull Request Guidelines
- Branching follows Git Flow (`feature/<topic>` for new work, `fix/<issue>` for patches) branching from `develop` and merging via reviewed PRs.
- Commits use Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`); include scopes where helpful (e.g., `feat(templates): add custom securities layout`).
- Pull requests summarize scope, link the relevant OpenSpec change or issue, list validation commands, and attach UI screenshots or sample output when the change affects user-facing flows.
- Update `tasks.md` checkboxes and flag residual risks before requesting review; reviewers rely on that status to confirm readiness.

## Security & Configuration Tips
- Never commit secrets—capture required variables in `.env.example` (OpenAI keys, Redis, database URLs) and load them through environment management.
- Delete uploaded PDFs and intermediate extracts after processing; observe the retention constraints noted in `openspec/project.md`.
- Monitor OpenAI usage during large batches; batch requests conservatively to control cost and avoid rate-limit failures.
