#!/bin/bash
set -e

STACK_NAME="gamr-website"
REGION="us-east-1"
TEMPLATE="cloudformation/gamr-website.yaml"
DOMAIN="edouard.nz"

echo "Looking up hosted zone ID for $DOMAIN..."
HOSTED_ZONE_ID=$(aws route53 list-hosted-zones \
  --query "HostedZones[?Name=='${DOMAIN}.'].Id" \
  --output text | sed 's|/hostedzone/||')

if [ -z "$HOSTED_ZONE_ID" ]; then
  echo "ERROR: Could not find hosted zone for $DOMAIN"
  exit 1
fi
echo "Found hosted zone: $HOSTED_ZONE_ID"

echo "Deploying CloudFormation stack: $STACK_NAME"
aws cloudformation deploy \
  --stack-name "$STACK_NAME" \
  --template-file "$TEMPLATE" \
  --region "$REGION" \
  --parameter-overrides \
    HostedZoneId="$HOSTED_ZONE_ID" \
  --no-fail-on-empty-changeset

echo "Stack outputs:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs' \
  --output table

echo "Done."
