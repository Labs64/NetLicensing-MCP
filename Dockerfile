FROM python:3.12-slim

# Consolidated labels (single layer)
LABEL org.opencontainers.image.title="netlicensing-mcp" \
      org.opencontainers.image.description="MCP server for the Labs64 NetLicensing API" \
      org.opencontainers.image.source="https://github.com/Labs64/NetLicensing-MCP" \
      org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app

# 1. Install dependencies first (layer-cached)
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir "mcp[cli]>=1.7.0" httpx python-dotenv

# 2. Copy source and install package (non-editable for production)
COPY src/ ./src/
COPY dist/*.whl ./
RUN pip install --no-cache-dir --no-deps \
    $(ls netlicensing_mcp-*.whl | sort -V | tail -1)

# 3. Runtime config — inject via -e at docker run, no defaults baked in
#    NETLICENSING_API_KEY   — required, no default
#    NETLICENSING_BASE_URL  — optional override
ENV NETLICENSING_BASE_URL="https://go.netlicensing.io/core/v2/rest"

# stdio mode by default; pass args via docker run for http / verbose:
#   docker run ... image              → stdio (default)
#   docker run ... image http         → HTTP mode
#   docker run ... image -v           → verbose stdio
#   docker run ... image http -v      → verbose HTTP
# Or use env vars: MCP_TRANSPORT=http  MCP_VERBOSE=true
EXPOSE 8000
ENTRYPOINT ["netlicensing-mcp"]
CMD []
