# AGENTS.md

## What this is

Single-file Flask app (`app.py`): a live Jinja2 template parser. The frontend is `templates/index.html` + `static/{css,js}`. All backend logic is two routes: `GET /` and `POST /convert`. Tests live in `test_app.py` (pytest, Flask test client).

## Commands

```bash
make install   # pip install -r requirements.txt — runtime deps ONLY
make run       # gunicorn on 127.0.0.1:5000 (Docker image uses 8125 instead)
make test      # pytest -v
make lint      # pylint on all *.py via --rcfile=.pylintrc
```

- `pytest`/`pylint` are not in `requirements.txt`. A gitignored `.venv/` in the repo root has them; use `.venv/bin/pytest` or install them yourself before `make test` / `make lint`.
- Single test: `pytest test_app.py::test_convert_with_json -v`
- `.flake8` exists (ignores E501) but nothing runs it — "lint" here means pylint.

## Security constraints — do not weaken

The app renders untrusted templates. `test_app.py` has a dedicated SSTI section asserting these; keep them intact:

- `JINJA2_ENVIRONMENT` is an `ImmutableSandboxedEnvironment` with `StrictUndefined` — undefined variables are an error, not empty strings.
- YAML input uses `yaml.safe_load` only, never `yaml.load`.
- Rendered output is HTML-escaped and newlines become `<br />` before being returned.

## API contract

`POST /convert` accepts form fields: `template`, `type` (`json`|`yaml`), `values`, `whitespaces`. Returns `{"rendered_output": ...}` (200) or `{"error": ...}` (400/500). The frontend still sends a `dummy` field, but the backend ignores it.

## CI / release

- No CI runs tests or lint — those are local-only. Nothing blocks a PR on them, so run `make test` and `make lint` yourself.
- CodeQL and GitGuardian trigger only on changes to `app.py` (pushes/PRs to `main`).
- Docker images build only when a GitHub Release is published: multi-arch (`linux/amd64,linux/arm64`), tagged `hatamiarash7/jinja-parser:<release-tag>` + `latest`, then Trivy-scanned. The image version comes from the release tag via `APP_VERSION` build arg.
