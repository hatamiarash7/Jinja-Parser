# AGENTS.md

## What this is

Single-file Flask app (`app.py`): a live Jinja2 template parser. The frontend is `templates/index.html` + `static/{css,js}`. Backend logic is three routes: `GET /`, `POST /convert` and `GET /healthz`. Tests live in `test_app.py` (pytest, Flask test client).

## Commands

```bash
make install       # pip install -r requirements.txt — runtime deps ONLY
make install-dev   # pip install -r requirements-dev.txt — runtime + dev deps
make run           # gunicorn on 127.0.0.1:5000 (Docker image uses 8125 instead)
make test          # pytest -v with coverage (--cov=app)
make lint          # pylint on app.py + test_app.py via --rcfile=.pylintrc
```

- Runtime deps are pinned in `requirements.txt`; dev tools (pytest, pytest-cov, pylint) are pinned in `requirements-dev.txt` and must NOT go into `requirements.txt` (the Docker image installs only runtime deps).
- `pytest`/`pylint` are not in `requirements.txt`. A gitignored `.venv/` in the repo root has them; use `make test PYTHON=.venv/bin/python` or install them yourself before `make test` / `make lint`.
- Single test: `pytest test_app.py::test_convert_with_json -v`
- pytest + coverage behavior is configured in `pyproject.toml`; pylint config is `.pylintrc`.
- `.flake8` exists (ignores E501) but nothing runs it — "lint" here means pylint.

## Security constraints — do not weaken

The app renders untrusted templates. `test_app.py` has a dedicated SSTI section asserting these; keep them intact:

- `JINJA2_ENVIRONMENT` is an `ImmutableSandboxedEnvironment` with `StrictUndefined` — undefined variables are an error, not empty strings.
- YAML input uses `yaml.safe_load` only, never `yaml.load`.
- Rendered output is HTML-escaped and newlines become `<br />` before being returned. Variable output is intentionally double-escaped (render-time autoescape + final escape); the final escape is required because literal HTML in the template body is not autoescaped.
- Request bodies are capped by `MAX_CONTENT_LENGTH` (1 MiB) with a JSON 413 error handler.
- Templates are compiled via `get_template()`: small ones go through a bounded `lru_cache`, oversized ones (> `CACHEABLE_TEMPLATE_SIZE`) bypass it so the cache stays memory-bounded.
- The 500 branches in `convert()` are defensive guards covered by monkeypatched tests — keep the tests that exercise them.

## API contract

`POST /convert` accepts form fields: `template`, `type` (`json`|`yaml`, case-insensitive), `values` (must parse to a dict), `whitespaces`. Returns `{"rendered_output": ...}` (200) or `{"error": ...}` (400/413/500). `GET /healthz` returns `{"status": "ok"}` (used by the Docker HEALTHCHECK).

## Docker

- `Dockerfile`: python:3.15-slim, non-root user, HEALTHCHECK against `/healthz`, gunicorn honors `WEB_CONCURRENCY` (do not pass `--workers` on the CLI or the env var stops working), `--timeout 30` so a hung worker is replaced.
- `docker-compose.yml` builds and runs the image locally.
- Never install dev deps or copy `.venv/` into the image; `.dockerignore` enforces the context.

## CI / release

- No CI runs tests or lint — those are local-only. Nothing blocks a PR on them, so run `make test` and `make lint` yourself.
- CodeQL and GitGuardian trigger only on changes to `app.py` (pushes/PRs to `main`).
- Docker images build only when a GitHub Release is published: multi-arch (`linux/amd64,linux/arm64`), tagged `hatamiarash7/jinja-parser:<release-tag>` + `latest`, then Trivy-scanned. The image version comes from the release tag via `APP_VERSION` build arg.
