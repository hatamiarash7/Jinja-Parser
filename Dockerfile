FROM --platform=$BUILDPLATFORM python:3.15-slim-bookworm

ARG DATE_CREATED
ARG APP_VERSION="undefined@docker"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
# Number of gunicorn workers; override with: docker run -e WEB_CONCURRENCY=4
ENV WEB_CONCURRENCY=2

LABEL org.opencontainers.image.title="jinja-parser"
LABEL org.opencontainers.image.description="Live parser for Jinja2"
LABEL org.opencontainers.image.url="https://github.com/hatamiarash7/Jinja-Parser"
LABEL org.opencontainers.image.source="https://github.com/hatamiarash7/Jinja-Parser"
LABEL org.opencontainers.image.vendor="hatamiarash7"
LABEL org.opencontainers.image.author="hatamiarash7"
LABEL org.opencontainers.image.version="$APP_VERSION"
LABEL org.opencontainers.image.created="$DATE_CREATED"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY ./requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir --requirement /app/requirements.txt

COPY . .

# Run as an unprivileged user.
RUN groupadd --system app && useradd --system --gid app --no-create-home app
USER app

EXPOSE 8125

# /dev/shm avoids gunicorn's heartbeat file hitting container disk slowdowns.
# --timeout lets a stuck worker (e.g. a pathological template loop) be
# replaced by the master instead of hanging a slot forever.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8125/healthz', timeout=3).status == 200 else 1)"]

# Note: gunicorn reads WEB_CONCURRENCY (above) for the worker count,
# as long as --workers is not passed on the command line.
CMD ["gunicorn", "--bind", "0.0.0.0:8125", "--timeout", "30", "--worker-tmp-dir", "/dev/shm", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "app:app"]
