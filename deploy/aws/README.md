# AWS Deployment — NetLicensing MCP Server

Deploy the NetLicensing MCP server to AWS with a **public HTTPS URL** so remote
AI agents (Claude, Copilot, custom apps) can connect via the
`streamable-http` transport.

Two deployment options are provided:

| Option | Best for | Cost (idle) | Scale-to-zero | HTTPS |
|---|---|---|---|---|
| **ECS Fargate** | Production, full control | ~$5–15/mo (Spot) | No (min 1 task) | Via ALB + ACM cert |
| **App Runner** | Simplest, low-traffic | ~$0 (scale-to-zero) | ✅ Yes | Auto-provisioned |

---

## Prerequisites

- **AWS CLI v2** — [Install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- **AWS credentials** configured (`aws configure` or environment variables)
- **Docker** (only needed if mirroring images to ECR for App Runner)

---

## Option A — ECS Fargate (recommended for production)

### 1. Deploy the stack

```bash
# HTTP only (quick test)
./deploy.sh fargate

# HTTPS (production) — requires an ACM certificate
./deploy.sh fargate \
    --certificate-arn arn:aws:acm:us-east-1:123456789:certificate/your-cert-id
```

Or use CloudFormation directly:

```bash
aws cloudformation deploy \
    --template-file deploy/aws/ecs-fargate.yaml \
    --stack-name netlicensing-mcp \
    --region us-east-1 \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        CertificateArn=arn:aws:acm:us-east-1:123456789:certificate/your-cert-id
```

### 2. Get the public URL

```bash
aws cloudformation describe-stacks \
    --stack-name netlicensing-mcp \
    --query 'Stacks[0].Outputs' \
    --output table
```

The `McpEndpointHttps` output is the URL to use in your MCP client config.

### 3. Verify

```bash
curl https://your-alb-dns.us-east-1.elb.amazonaws.com/health
# → {"status":"ok","server":"netlicensing-mcp"}
```

### Architecture

```
┌─────────────┐     HTTPS     ┌────────────┐     HTTP      ┌───────────────────┐
│  MCP Client │ ─────────── → │    ALB     │ ─────────── → │  Fargate Task     │
│  (Claude,   │               │  (ACM TLS) │               │  netlicensing-mcp │
│   Copilot)  │               └────────────┘               │  :8000/mcp        │
└─────────────┘                                            └───────────────────┘
```

---

## Option B — App Runner (simplest, scale-to-zero)

> **Note:** App Runner only supports ECR and ECR Public images — not GHCR
> directly. Use the `mirror` command to copy the image first.

### 1. Mirror the image to ECR

```bash
# Create an ECR repo (if it doesn't exist)
aws ecr create-repository --repository-name netlicensing-mcp --region us-east-1

# Mirror using the helper script
./deploy.sh mirror \
    --ecr-repo 123456789.dkr.ecr.us-east-1.amazonaws.com/netlicensing-mcp
```

### 2. Deploy

```bash
./deploy.sh apprunner \
    --ecr-image 123456789.dkr.ecr.us-east-1.amazonaws.com/netlicensing-mcp:latest
```

### 3. Get the public URL

The stack output `McpEndpoint` contains the auto-provisioned HTTPS URL
(e.g. `https://abc123.us-east-1.awsapprunner.com/mcp`).

---

## Connecting MCP Clients to the AWS Endpoint

Once deployed, configure your MCP client to use the public URL with the
`streamable-http` transport:

### Claude Desktop / VS Code

To securely invoke the remote MCP server for a specific vendor account, pass your NetLicensing API Key using the `apikey` query parameter:

```json
{
  "mcpServers": {
    "netlicensing": {
      "url": "https://your-alb-dns.us-east-1.elb.amazonaws.com/mcp?apikey=YOUR_API_KEY"
    }
  }
}
```

### Generic streamable-http client

Pass the API key dynamically per client via HTTP headers or in the URL string:

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# You can pass the key in the URL: "https://your-endpoint/mcp?apikey=foo"
# Or natively with headers:
headers = {"X-NetLicensing-API-Key": "YOUR_API_KEY"}

async with streamablehttp_client("https://your-endpoint/mcp", headers=headers) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
```

---

## Cleanup

```bash
# Delete the stack and all resources
./deploy.sh teardown --stack-name netlicensing-mcp

# Or directly:
aws cloudformation delete-stack --stack-name netlicensing-mcp --region us-east-1
```
