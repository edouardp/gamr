#!/bin/bash
set -e

STACK_NAME="gamr-website"
REGION="us-east-1"

BUCKET=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue' --output text)
DISTRIBUTION_ID=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`DistributionId`].OutputValue' --output text)

echo "Syncing website/ to s3://$BUCKET/"
aws s3 sync website/ "s3://$BUCKET/" --delete --size-only

echo "Invalidating CloudFront distribution: $DISTRIBUTION_ID"
aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION_ID" --paths "/*" --output text

echo "Upload complete! Site will be live at https://gamr.edouard.nz shortly."
