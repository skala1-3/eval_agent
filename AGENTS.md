# Repository Guidelines

## Project Structure & Module Organization
- `agents/` holds task-specific agent classes such as `scoring_agent.py` and `report_writer_agent.py`; extend these rather than altering shared state logic.
- `graph/` contains the LangGraph workflow (`graph.py`, `state.py`) and entrypoints (`run.py`, `visualize.py`); new nodes should expose clear input/output fields on `PipelineState`.
- `data/` and `outputs/` are workspace directories for scraped evidence, reports, and logs; keep large artifacts out of git.
- `scripts/` bundles one-off utilities (e.g., `make_report.py`), while `tests/` mirrors core modules with scenario-driven coverage.

## Build, Test, and Development Commands
- `uv sync` installs runtime dependencies; add `-E dev` to include linting and test extras.
- `python graph/run.py --query "AI financial advisory startup"` exercises the end-to-end agent graph locally.
- `python graph/visualize.py` regenerates `outputs/agent_graph.png` for documentation.
- `uv run pytest` executes the full test suite; append `--cov=agents --cov=graph` when validating coverage expectations.

## Coding Style & Naming Conventions
- Python 3.11 with four-space indentation and type hints on public functions; prefer dataclasses or Pydantic models already used in `graph/state.py`.
- Follow Black and Ruff defaults (`line-length = 100`); run `uv run black .` and `uv run ruff check .` before opening a PR.
- Module names stay snake_case; agent classes use PascalCase (`ScoringAgent`), and async helpers use verb-based snake_case.
- Keep docstrings action-oriented and include rationale when adjusting scoring heuristics or graph transitions.

## Testing Guidelines
- Place new tests under `tests/` mirroring the module layout (`test_scoring_agent.py` as the pattern); name files `test_<feature>.py`.
- Use pytest fixtures to build `PipelineState` instances, and assert both decision labels and supporting structures (scores, reports).
- Prefer deterministic inputs; mock external APIs or network calls instead of hitting live services.
- Run `uv run pytest -k <subset>` for focused debugging, and refresh `uv run pytest --maxfail=1 --ff` before submitting changes.

## Commit & Pull Request Guidelines
- Follow Conventional Commit prefixes (`feat:`, `fix:`, `docs:`) with optional emoji as seen in `:sparkles: feat: add RAGRetrieverAgent`; keep subjects under 72 characters.
- Commits should be scoped to one change set (e.g., agent tweak plus matching test); include migration notes in the body when touching data schemas.
- Pull requests need a concise summary, testing evidence (`uv run pytest` output), and links to Jira/GitHub issues; attach screenshots or generated PDFs when UI/report formatting changes.
- Request review from the owning agent lead (see README contributor table) and wait for at least one approval plus passing CI before merge.

## Agent & Environment Notes
- Load secrets from `.env`; commit only `.env.example` updates. Document new keys in both files when adding integrations.
- When experimenting with retrieval corpora, store interim artifacts under `outputs/` and clean up before pushing to keep the repository lightweight.
- Align evidence categories with the seven-axis scorecard (`docs/scorecard.md`) so downstream scoring remains consistent.
