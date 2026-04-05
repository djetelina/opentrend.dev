FROM python:3.14-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
COPY src/opentrend/__init__.py ./src/opentrend/__init__.py
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY tailwind.config.js ./
COPY src/ ./src/

# Build Tailwind CSS
ADD https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64 /usr/local/bin/tailwindcss
RUN chmod +x /usr/local/bin/tailwindcss \
    && tailwindcss -i src/opentrend/static/css/tailwind-input.css -o src/opentrend/static/css/tailwind.css --minify \
    && useradd --create-home --no-log-init appuser \
    && chown -R appuser:appuser /app/.venv
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

CMD ["uv", "run", "litestar", "--app", "opentrend.app:create_app", "run", "--host", "0.0.0.0", "--port", "8000"]
