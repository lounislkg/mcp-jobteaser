FROM python:3.12-slim

# System Chromium instead of Playwright's bundled browser: more reliable on
# ARM (Raspberry Pi), and apt resolves all of Chromium's shared-lib
# dependencies automatically.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY README.md ./
RUN uv sync --frozen --no-dev

ENV CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium \
    CHROMIUM_EXTRA_ARGS=--no-sandbox,--disable-dev-shm-usage \
    MCP_HTTP_HOST=0.0.0.0 \
    MCP_HTTP_PORT=8000 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["python", "-m", "mcp_jobteaser.server"]
