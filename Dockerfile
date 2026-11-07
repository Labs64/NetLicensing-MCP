# Stage 1: export the locked runtime dependencies (with hashes) from uv.lock,
# so the image runs exactly the versions CI and pip-audit saw.
FROM python:3.12-slim AS requirements
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-emit-project -o requirements.txt

# Stage 2: runtime image
FROM python:3.12-slim

# Consolidated labels (single layer)
LABEL org.opencontainers.image.title="netlicensing-mcp" \
      org.opencontainers.image.description="MCP server for the Labs64 NetLicensing API" \
      org.opencontainers.image.source="https://github.com/Labs64/NetLicensing-MCP" \
      org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app

# 1. Install dependencies first (layer-cached)
COPY --from=requirements /build/requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

# 2. Install the pre-built wheel (run `hatch build --target wheel` first)
COPY dist/*.whl ./
RUN pip install --no-cache-dir --no-deps \
    $(ls netlicensing_mcp-*.whl | sort -V | tail -1)

# 3. Runtime config — inject via -e at docker run, no defaults baked in
#    NETLICENSING_API_KEY   — required, no default
#    NETLICENSING_BASE_URL  — optional override
ENV NETLICENSING_BASE_URL="https://go.netlicensing.io/core/v2/rest"

# 4. Drop root privileges — run as a non-root user for security
RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

# stdio mode by default; pass args via docker run for http / verbose:
#   docker run ... image              → stdio (default)
#   docker run ... image http         → HTTP mode
#   docker run ... image -v           → verbose stdio
#   docker run ... image http -v      → verbose HTTP
# Or use env vars: MCP_TRANSPORT=http  MCP_VERBOSE=true
COPY healthcheck.py /usr/local/bin/healthcheck.py
# Probes /health in HTTP mode; reports healthy in stdio mode, which has no port.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "/usr/local/bin/healthcheck.py"]

EXPOSE 8000
ENTRYPOINT ["netlicensing-mcp"]
CMD []
