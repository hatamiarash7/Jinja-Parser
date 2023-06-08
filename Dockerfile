FROM --platform=$BUILDPLATFORM python:3.11.4-slim-buster

LABEL org.opencontainers.image.title="jinja-parser"
LABEL org.opencontainers.image.description="Live parser for Jinja2"
LABEL org.opencontainers.image.url="https://github.com/hatamiarash7/Jinja-Parser"
LABEL org.opencontainers.image.source="https://github.com/hatamiarash7/Jinja-Parser"
LABEL org.opencontainers.image.vendor="hatamiarash7"
LABEL org.opencontainers.image.author="hatamiarash7"
LABEL org.opencontainers.version="$APP_VERSION"
LABEL org.opencontainers.image.created="$DATE_CREATED"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

COPY ./requirements.txt /app

RUN pip3 install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "--log-level", "debug", "app:app"]
