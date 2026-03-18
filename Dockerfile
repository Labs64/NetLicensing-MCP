FROM python:3.12-slim

LABEL org.opencontainers.image.title="netlicensing-mcp"
LABEL org.opencontainers.image.description="MCP server for the Labs64 NetLicensing API"
LABEL org.opencontainers.image.source="https://github.com/Labs64/NetLicensing-MCP"
LABEL org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app

# Install dependencies first (layer-cached)
COPY pyproject.toml .
RUN pip install --no-cache-dir "mcp[cli]>=1.7.0" httpx python-dotenv

# Copy source and install package (non-editable for production)
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps .

ENV NETLICENSING_API_KEY=""
ENV NETLICENSING_BASE_URL="https://go.netlicensing.io/core/v2/rest"

# HTTP mode by default for container use; override CMD for stdio
EXPOSE 8000
CMD ["netlicensing-mcp", "http"]
