#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# deploy.sh — Deploy NetLicensing MCP Server to AWS
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   ./deploy.sh fargate [--certificate-arn <arn>] [--region us-east-1]
#   ./deploy.sh apprunner --ecr-image <uri>       [--region us-east-1]
#   ./deploy.sh teardown  [--stack-name <name>]   [--region us-east-1]
#
# Prerequisites:
#   - AWS CLI v2 configured with appropriate credentials
#   - For App Runner: image pushed to ECR (GHCR not directly supported)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_NAME="${STACK_NAME:-netlicensing-mcp}"
REGION="${AWS_REGION:-us-east-1}"
IMAGE_URI="${IMAGE_URI:-ghcr.io/labs64/netlicensing-mcp:latest}"

# ── Helpers ──────────────────────────────────────────────────────────────────

red()   { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
blue()  { printf "\033[34m%s\033[0m\n" "$*"; }

die() { red "ERROR: $*" >&2; exit 1; }

check_prereqs() {
    command -v aws >/dev/null 2>&1 || die "AWS CLI not found. Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    aws sts get-caller-identity >/dev/null 2>&1 || die "AWS credentials not configured. Run: aws configure"
}

# ── Deploy to ECS Fargate ────────────────────────────────────────────────────

deploy_fargate() {
    local certificate_arn=""
    local desired_count=1
    local use_spot="true"
    local verbose="false"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --certificate-arn)    certificate_arn="$2"; shift 2 ;;
            --desired-count)      desired_count="$2"; shift 2 ;;
            --no-spot)            use_spot="false"; shift ;;
            --verbose)            verbose="true"; shift ;;
            --region)             REGION="$2"; shift 2 ;;
            --stack-name)         STACK_NAME="$2"; shift 2 ;;
            --image)              IMAGE_URI="$2"; shift 2 ;;
            *) die "Unknown option: $1" ;;
        esac
    done

    blue "Deploying NetLicensing MCP to ECS Fargate..."
    blue "  Stack:       $STACK_NAME"
    blue "  Region:      $REGION"
    blue "  Image:       $IMAGE_URI"
    blue "  Spot:        $use_spot"

    local params=(
        "ImageUri=${IMAGE_URI}"
        "DesiredCount=${desired_count}"
        "UseSpot=${use_spot}"
        "McpVerbose=${verbose}"
    )
    [[ -n "$certificate_arn" ]] && params+=("CertificateArn=${certificate_arn}")

    aws cloudformation deploy \
        --template-file "${SCRIPT_DIR}/ecs-fargate.yaml" \
        --stack-name "${STACK_NAME}" \
        --region "${REGION}" \
        --capabilities CAPABILITY_IAM \
        --parameter-overrides "${params[@]}" \
        --no-fail-on-empty-changeset

    green "✅ Deployment complete!"
    echo ""
    blue "Stack outputs:"
    aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${REGION}" \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
        --output table
}

# ── Deploy to App Runner ────────────────────────────────────────────────────

deploy_apprunner() {
    local ecr_image=""
    local verbose="false"
    local min_size=0
    local max_size=2

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --ecr-image)   ecr_image="$2"; shift 2 ;;
            --verbose)     verbose="true"; shift ;;
            --min-size)    min_size="$2"; shift 2 ;;
            --max-size)    max_size="$2"; shift 2 ;;
            --region)      REGION="$2"; shift 2 ;;
            --stack-name)  STACK_NAME="$2"; shift 2 ;;
            *) die "Unknown option: $1" ;;
        esac
    done

    [[ -n "$ecr_image" ]] || die "--ecr-image is required (App Runner requires ECR). Mirror the image first — see README."

    blue "Deploying NetLicensing MCP to App Runner..."
    blue "  Stack:  $STACK_NAME"
    blue "  Region: $REGION"
    blue "  Image:  $ecr_image"

    aws cloudformation deploy \
        --template-file "${SCRIPT_DIR}/apprunner.yaml" \
        --stack-name "${STACK_NAME}" \
        --region "${REGION}" \
        --capabilities CAPABILITY_IAM \
        --parameter-overrides \
            "ImageUri=${ecr_image}" \
            "McpVerbose=${verbose}" \
            "MinSize=${min_size}" \
            "MaxSize=${max_size}" \
        --no-fail-on-empty-changeset

    green "✅ Deployment complete!"
    echo ""
    blue "Stack outputs:"
    aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --region "${REGION}" \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
        --output table
}

# ── Teardown ─────────────────────────────────────────────────────────────────

teardown() {
    local stack="${STACK_NAME}"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --stack-name) stack="$2"; shift 2 ;;
            --region)     REGION="$2"; shift 2 ;;
            *) die "Unknown option: $1" ;;
        esac
    done

    red "⚠️  This will delete the stack '${stack}' and ALL its resources."
    read -rp "Type the stack name to confirm: " confirm
    [[ "$confirm" == "$stack" ]] || die "Confirmation failed — aborting."

    blue "Deleting stack ${stack}..."
    aws cloudformation delete-stack --stack-name "${stack}" --region "${REGION}"
    aws cloudformation wait stack-delete-complete --stack-name "${stack}" --region "${REGION}"
    green "✅ Stack deleted."
}

# ── Mirror GHCR image to ECR (helper for App Runner) ────────────────────────

mirror_to_ecr() {
    local source_image="${IMAGE_URI}"
    local ecr_repo=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --source)   source_image="$2"; shift 2 ;;
            --ecr-repo) ecr_repo="$2"; shift 2 ;;
            --region)   REGION="$2"; shift 2 ;;
            *) die "Unknown option: $1" ;;
        esac
    done

    [[ -n "$ecr_repo" ]] || die "--ecr-repo is required (e.g. 123456789.dkr.ecr.us-east-1.amazonaws.com/netlicensing-mcp)"

    blue "Mirroring ${source_image} → ${ecr_repo}:latest"

    # Login to ECR
    local account_id region
    account_id=$(echo "$ecr_repo" | cut -d. -f1)
    region=$(echo "$ecr_repo" | cut -d. -f4)
    aws ecr get-login-password --region "${region}" | docker login --username AWS --password-stdin "${account_id}.dkr.ecr.${region}.amazonaws.com"

    # Create repo if it doesn't exist
    aws ecr describe-repositories --repository-names netlicensing-mcp --region "${region}" 2>/dev/null || \
        aws ecr create-repository --repository-name netlicensing-mcp --region "${region}"

    docker pull "${source_image}"
    docker tag "${source_image}" "${ecr_repo}:latest"
    docker push "${ecr_repo}:latest"

    green "✅ Image mirrored to ${ecr_repo}:latest"
}

# ── Main ─────────────────────────────────────────────────────────────────────

main() {
    check_prereqs

    local command="${1:-help}"
    shift || true

    case "$command" in
        fargate)    deploy_fargate "$@" ;;
        apprunner)  deploy_apprunner "$@" ;;
        teardown)   teardown "$@" ;;
        mirror)     mirror_to_ecr "$@" ;;
        help|--help|-h)
            cat <<EOF
NetLicensing MCP Server — AWS Deployment

Usage:
  $(basename "$0") fargate    [--certificate-arn <arn>] [options]
  $(basename "$0") apprunner  --ecr-image <uri> [options]
  $(basename "$0") teardown   [--stack-name <name>]
  $(basename "$0") mirror     --ecr-repo <uri> [--source <image>]

Fargate options:
  --certificate-arn     ACM certificate ARN for HTTPS
  --desired-count       Number of tasks (default: 1)
  --no-spot             Use on-demand instead of Spot capacity
  --verbose             Enable debug logging
  --image               Container image URI
  --region              AWS region (default: us-east-1)
  --stack-name          CloudFormation stack name (default: netlicensing-mcp)

App Runner options:
  --ecr-image           ECR image URI (required, use 'mirror' to copy from GHCR)
  --verbose             Enable debug logging
  --min-size            Min instances, 0 for scale-to-zero (default: 0)
  --max-size            Max instances (default: 2)
  --region              AWS region (default: us-east-1)
  --stack-name          CloudFormation stack name (default: netlicensing-mcp)

Mirror (helper for App Runner):
  --ecr-repo            Target ECR repo URI (required)
  --source              Source image (default: ghcr.io/labs64/netlicensing-mcp:latest)

Examples:
  # Deploy with Fargate (HTTP-only)
  $(basename "$0") fargate

  # Deploy with Fargate (HTTPS)
  $(basename "$0") fargate \\
      --certificate-arn arn:aws:acm:us-east-1:123456789:certificate/abc-123

  # Deploy with App Runner (mirror image first)
  $(basename "$0") mirror --ecr-repo 123456789.dkr.ecr.us-east-1.amazonaws.com/netlicensing-mcp
  $(basename "$0") apprunner \\
      --ecr-image 123456789.dkr.ecr.us-east-1.amazonaws.com/netlicensing-mcp:latest

  # Tear down
  $(basename "$0") teardown --stack-name netlicensing-mcp
EOF
            ;;
        *) die "Unknown command: $command. Run with --help for usage." ;;
    esac
}

main "$@"

