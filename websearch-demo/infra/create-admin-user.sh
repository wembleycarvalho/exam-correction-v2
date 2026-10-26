#!/usr/bin/env bash
#
# create-admin-user.sh - creates (or resets) the default admin user in the
# Cognito User Pool provisioned by this stack.
#
# Self sign-up is disabled, so users must be created by an admin. This script
# reads the User Pool ID from the deployed CloudFormation stack outputs, then:
#   1. Creates the user (idempotent - ignores "already exists").
#   2. Sets a PERMANENT password, so there's no forced password change on the
#      first Hosted UI login.
#
# Usage:
#   ./create-admin-user.sh                       # uses the defaults below
#   ADMIN_EMAIL=me@example.com ADMIN_PASSWORD='S3cret!' ./create-admin-user.sh
#
# Prerequisites: AWS CLI configured for the same account/region as the deploy
# (this repo uses us-east-1), and the stack already deployed (cdk deploy).

set -euo pipefail

STACK_NAME="${STACK_NAME:-WebSearchDemoStack}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Admin123!}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "Looking up User Pool ID from stack '${STACK_NAME}' in ${AWS_REGION}..."
USER_POOL_ID="$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" \
  --output text)"

if [[ -z "${USER_POOL_ID}" || "${USER_POOL_ID}" == "None" ]]; then
  echo "ERROR: could not find UserPoolId output on stack '${STACK_NAME}'." >&2
  echo "Is the stack deployed? Try: cd infra && npx cdk deploy" >&2
  exit 1
fi

echo "User Pool: ${USER_POOL_ID}"
echo "Creating admin user: ${ADMIN_EMAIL}"

# Create the user. MESSAGE_ACTION=SUPPRESS avoids sending a welcome email
# (there's no real inbox for a demo). "|| true" keeps the script idempotent if
# the user already exists.
aws cognito-idp admin-create-user \
  --region "${AWS_REGION}" \
  --user-pool-id "${USER_POOL_ID}" \
  --username "${ADMIN_EMAIL}" \
  --user-attributes Name=email,Value="${ADMIN_EMAIL}" Name=email_verified,Value=true \
  --message-action SUPPRESS \
  >/dev/null 2>&1 || echo "(user may already exist - continuing to set password)"

# Set a permanent password so the first login through the Hosted UI works
# without a "change your password" challenge.
aws cognito-idp admin-set-user-password \
  --region "${AWS_REGION}" \
  --user-pool-id "${USER_POOL_ID}" \
  --username "${ADMIN_EMAIL}" \
  --password "${ADMIN_PASSWORD}" \
  --permanent

echo
echo "Done. Sign in at the SiteUrl (from the stack outputs) with:"
echo "  email:    ${ADMIN_EMAIL}"
echo "  password: ${ADMIN_PASSWORD}"
echo
echo "Change ADMIN_EMAIL / ADMIN_PASSWORD env vars before running for a real login."
