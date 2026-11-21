# Deploy the NetLicensing MCP server on AWS

This guide takes you from nothing to a running MCP server with its own web
address that remote AI clients (Claude Code, VS Code, your own apps) can connect
to. Follow the steps in order and copy the snippets.

**How it works:** the server runs as a container on AWS Fargate behind a load
balancer. The server does **not** store your NetLicensing API key. Every client
sends its own key in an HTTP header with each request, so one deployment can
serve many people, each with their own NetLicensing account.

```
MCP client ──HTTPS──▶ Load balancer ──HTTP──▶ Fargate task (netlicensing-mcp, port 8000)
```

> **App Runner:** AWS has closed App Runner to new customers and recommends
> Amazon ECS Express Mode instead
> ([AWS notice](https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html)).
> Use the Fargate path below. The App Runner template is kept at the
> [end of this page](#existing-app-runner-customers) for accounts that already use it.

---

## Before you start

You need:

- An AWS account and permission to create VPCs, load balancers, ECS services and IAM roles.
- [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html), signed in.
- A NetLicensing API key from your NetLicensing account.
- For HTTPS (step 4): a domain name you control, for example `mcp.example.com`.

Check that the CLI works and points at the account you expect:

```bash
aws --version
aws sts get-caller-identity
```

Pick the region once and reuse it everywhere below:

```bash
export AWS_REGION=us-east-1
```

Get the files (skip if you already cloned the repo):

```bash
git clone https://github.com/Labs64/NetLicensing-MCP.git
cd NetLicensing-MCP/deploy/aws
```

---

## Step 1: Deploy

For a first test, deploy without HTTPS. This is quick, and fine for trying it out
with a sandbox key. **Do not use a real API key over plain HTTP.**

```bash
./deploy.sh fargate
```

The script creates a CloudFormation stack named `netlicensing-mcp` (network,
load balancer, cluster, service) and waits until it finishes. This usually takes
a few minutes. It runs the public image `ghcr.io/labs64/netlicensing-mcp:latest`,
which needs no registry login.

Useful options:

| Option | What it does |
|---|---|
| `--image ghcr.io/labs64/netlicensing-mcp:1.0` | Pin a version instead of `latest` (recommended for production). |
| `--no-spot` | Use regular Fargate capacity. The default is Fargate Spot, which is cheaper but can be interrupted by AWS. |
| `--desired-count 2` | Run two copies of the server. |
| `--stack-name my-mcp` | Use a different stack name (keep it short; load balancer names are limited to 32 characters). |
| `--verbose` | Debug logging (secrets are still redacted). |

## Step 2: Find your address

```bash
aws cloudformation describe-stacks \
  --stack-name netlicensing-mcp \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table
```

Copy the `AlbDnsName` value (looks like `netlicensing-mcp-alb-123.us-east-1.elb.amazonaws.com`).

```bash
export ALB=<paste AlbDnsName here>
```

## Step 3: Check that it works

Health check, which should print `{"status":"ok","server":"netlicensing-mcp"}`:

```bash
curl http://$ALB/health
```

Readiness check, which also tests that the server reaches the NetLicensing API
and should print `"status":"ready"` (see [Health and readiness probes](#health-and-readiness-probes)):

```bash
curl http://$ALB/ready
```

A request without a key must be refused with `401`:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://$ALB/mcp
```

A request with a key must succeed. This asks the server to start an MCP session
(`demo:demo` is NetLicensing's public sandbox key):

```bash
curl -s -X POST http://$ALB/mcp \
  -H "X-NetLicensing-API-Key: demo:demo" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

You should see a JSON reply containing `"serverInfo":{"name":"netlicensing-mcp"...`.
If the health check hangs or returns 503, wait a minute (the load balancer is
still registering the container) and try again. If it still fails, see
[Troubleshooting](#troubleshooting).

## Step 4: Turn on HTTPS (needed for real keys)

A TLS certificate only works for a hostname it was issued for, and a client
rejects the connection if the certificate's domain does not match the host name
it requested
([AWS docs](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/https-listener-certificates.html)).
So HTTPS needs **your own domain name** that points at the load balancer. In
this guide it is `mcp.example.com`; replace it with yours.

**4a. Request a certificate** (in the same region as the stack):

```bash
aws acm request-certificate \
  --domain-name mcp.example.com \
  --validation-method DNS \
  --region $AWS_REGION
```

Copy the `CertificateArn` it prints and keep it:

```bash
export CERT_ARN=<paste CertificateArn here>
```

**4b. Prove you own the domain.** Ask AWS which DNS record to create:

```bash
aws acm describe-certificate \
  --certificate-arn $CERT_ARN --region $AWS_REGION \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord'
```

Create that CNAME record (`Name` and `Value`) at your DNS provider, then wait
until AWS confirms it (this can take several minutes):

```bash
aws acm wait certificate-validated --certificate-arn $CERT_ARN --region $AWS_REGION
```

**4c. Redeploy with the certificate:**

```bash
./deploy.sh fargate --certificate-arn $CERT_ARN
```

Port 80 now redirects to HTTPS.

**4d. Point your domain at the load balancer.** At your DNS provider, create a
CNAME record `mcp.example.com` → the `AlbDnsName` value from step 2.

**4e. Test:**

```bash
curl https://mcp.example.com/health
curl https://mcp.example.com/ready
```

Your MCP address is now **`https://mcp.example.com/mcp`**.

## Step 5: Connect your AI client

Send your NetLicensing API key in the `X-NetLicensing-API-Key` header
(`Authorization: Bearer <key>` works too).

**Claude Code:**

```bash
claude mcp add --transport http netlicensing https://mcp.example.com/mcp \
  --header "X-NetLicensing-API-Key: YOUR_API_KEY"
```

**VS Code** (`.vscode/mcp.json`):

```json
{
  "servers": {
    "netlicensing": {
      "type": "http",
      "url": "https://mcp.example.com/mcp",
      "headers": { "X-NetLicensing-API-Key": "YOUR_API_KEY" }
    }
  }
}
```

**Your own Python code:**

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

headers = {"X-NetLicensing-API-Key": "YOUR_API_KEY"}

async with streamablehttp_client("https://mcp.example.com/mcp", headers=headers) as (
    read,
    write,
    _,
):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
```

---

## Updating to a new version

Redeploy with the version you want (the image tags are listed at
[ghcr.io/labs64/netlicensing-mcp](https://github.com/Labs64/NetLicensing-MCP/pkgs/container/netlicensing-mcp)):

```bash
./deploy.sh fargate --certificate-arn $CERT_ARN --image ghcr.io/labs64/netlicensing-mcp:1.0
```

If you keep using the `latest` tag, CloudFormation sees no change, so tell ECS to
pull the image again:

```bash
aws ecs update-service \
  --cluster netlicensing-mcp-cluster \
  --service netlicensing-mcp-service \
  --force-new-deployment \
  --region $AWS_REGION
```

## Health and readiness probes

The server has two unauthenticated endpoints. Neither needs an API key.

| Endpoint | Kind | Answers | Use it for |
|---|---|---|---|
| `GET /health` | Liveness | Always `200` `{"status":"ok","server":"netlicensing-mcp"}` while the process serves HTTP. Never calls NetLicensing. | Load balancer target-group checks, App Runner health checks, the Docker `HEALTHCHECK`: anything that restarts or replaces the container when it fails. |
| `GET /ready` | Readiness | `200` `{"status":"ready", ...}` when the MCP endpoint is running and the NetLicensing API answers; otherwise `503` `{"status":"not_ready", "reason": ..., ...}`. | Monitoring and alerting, smoke tests after a deploy (`curl https://<host>/ready`), and orchestrators that only stop sending traffic while it fails. |

Both CloudFormation templates keep `/health` as the target-group / App Runner
health check. Do not switch them to `/ready`: when NetLicensing itself is down,
`/ready` returns `503` on every container, and every container would be marked
unhealthy and replaced, although a new container cannot fix an upstream outage.

`/ready` checks the API with one unauthenticated `GET` of `NETLICENSING_BASE_URL`
(3-second timeout). Any HTTP answer, including `401` or `404`, means "reachable";
only timeouts and connection errors mean "unreachable". A success is cached for
15 seconds and a failure for 5 seconds, so frequent probes do not reach
NetLicensing more often than that. The reply names only the API's host name, never
a key or the upstream response.

## Troubleshooting

**See the server's logs:**

```bash
aws logs tail /ecs/netlicensing-mcp --follow --region $AWS_REGION
```

**See why a container is not starting or staying healthy:**

```bash
aws ecs describe-services \
  --cluster netlicensing-mcp-cluster --services netlicensing-mcp-service \
  --region $AWS_REGION --query 'services[0].events[:5].message'
```

| Symptom | Likely cause |
|---|---|
| `401` from `/mcp` | The client is not sending the API key header. |
| `503` from the load balancer right after deploy | The container is still starting. Wait a minute and retry. |
| `503` from `/ready` with `"reason": "NetLicensing API at ... is unreachable (...)"` | The container cannot reach the NetLicensing API: check the task's outbound internet access (the Fargate template gives tasks a public IP) and `NETLICENSING_BASE_URL`. |
| Browser or client reports a certificate error | You are using the `...elb.amazonaws.com` name. Use your own domain (step 4d). |
| `deploy.sh` says the stack is in `ROLLBACK_COMPLETE` | Delete the failed stack (`./deploy.sh teardown`) and deploy again. |

## Cleanup

Deletes the stack and everything it created (you must type the stack name to confirm):

```bash
./deploy.sh teardown --stack-name netlicensing-mcp
```

If you created an ACM certificate or DNS records for step 4, remove those
yourself. They are not part of the stack.

---

## Existing App Runner customers

Only for AWS accounts that already use App Runner. App Runner can pull only from
ECR, so copy the image there first (needs Docker running):

```bash
./deploy.sh mirror --ecr-repo 123456789012.dkr.ecr.$AWS_REGION.amazonaws.com/netlicensing-mcp
./deploy.sh apprunner --ecr-image 123456789012.dkr.ecr.$AWS_REGION.amazonaws.com/netlicensing-mcp:latest
```

Replace `123456789012` with your AWS account ID. App Runner provides its own
HTTPS address; the `McpEndpoint` stack output is your MCP URL. App Runner always
keeps at least one instance running (`--min-size` must be 1 or more).
