#!/usr/bin/env bash
#
# list-vpcs.sh - finds VPCs suitable for this stack and prints ONLY the subnets
# that meet the requirements, so you can reuse an existing VPC when the
# "max VPCs per region" (or Elastic IP) limit gets in the way.
#
# Requirement: the stack needs PRIVATE subnets WITH egress (a route to a NAT
# Gateway) across at least 2 Availability Zones, so the Fargate tasks can reach
# ECR/Secrets Manager/Cognito/Gateway and the internal ALB gets one subnet per
# AZ. This script lists only those qualifying subnets, grouped by VPC, and skips
# VPCs that don't qualify.
#
# Usage:
#   ./list-vpcs.sh
#   AWS_REGION=eu-west-1 ./list-vpcs.sh
#
# Then reuse a listed VPC:
#   npx cdk deploy -c vpcId=<VpcId>

set -uo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
echo "Region: ${AWS_REGION}"
echo

# --- Quota (used vs limit) -------------------------------------------------
USED="$(aws ec2 describe-vpcs --region "${AWS_REGION}" \
  --query 'length(Vpcs)' --output text 2>/dev/null || echo '?')"
LIMIT="$(aws service-quotas get-service-quota \
  --region "${AWS_REGION}" --service-code vpc --quota-code L-F678F1CE \
  --query 'Quota.Value' --output text 2>/dev/null || echo '5 (default; quota lookup denied)')"
echo "VPCs in use: ${USED}    |    Limit (VPCs per Region): ${LIMIT}"
echo
echo "Suitable VPCs (>= 2 AZs with a private + egress subnet) and their qualifying subnets:"
echo

suitable_count=0

for vpc_id in $(aws ec2 describe-vpcs --region "${AWS_REGION}" \
  --query 'Vpcs[].VpcId' --output text); do

  # Find the subnets that route to a NAT Gateway. We list every route table
  # with (id, first-nat-route-or-None), then for the ones that have a NAT route
  # collect their explicitly-associated subnets. (A nested filter like
  # RouteTables[?Routes[?NatGatewayId!=`null`]] is unreliable across CLI/JMESPath
  # versions, so we filter in the shell instead.)
  egress_subnets=""
  while read -r rtb natid; do
    [ -z "${rtb:-}" ] && continue
    if [ "${natid:-None}" != "None" ]; then
      subs="$(aws ec2 describe-route-tables --region "${AWS_REGION}" \
        --route-table-ids "${rtb}" \
        --query 'RouteTables[0].Associations[?SubnetId!=`null`].SubnetId' \
        --output text)"
      egress_subnets="${egress_subnets} ${subs}"
    fi
  done <<EOF
$(aws ec2 describe-route-tables --region "${AWS_REGION}" \
   --filters "Name=vpc-id,Values=${vpc_id}" \
   --query 'RouteTables[].[RouteTableId, Routes[?NatGatewayId!=`null`].NatGatewayId | [0]]' \
   --output text)
EOF

  egress_subnets="$(echo ${egress_subnets} | tr ' \t' '\n\n' | sed '/^$/d' | sort -u)"
  [ -z "${egress_subnets}" ] && continue

  az_count="$(aws ec2 describe-subnets --region "${AWS_REGION}" \
    --subnet-ids ${egress_subnets} \
    --query 'Subnets[].AvailabilityZone' --output text \
    | tr '\t' '\n' | sort -u | grep -c .)"
  [ "${az_count:-0}" -lt 2 ] && continue

  suitable_count=$((suitable_count + 1))

  cidr="$(aws ec2 describe-vpcs --region "${AWS_REGION}" --vpc-ids "${vpc_id}" \
    --query 'Vpcs[0].CidrBlock' --output text)"
  is_default="$(aws ec2 describe-vpcs --region "${AWS_REGION}" --vpc-ids "${vpc_id}" \
    --query 'Vpcs[0].IsDefault' --output text)"
  name="$(aws ec2 describe-vpcs --region "${AWS_REGION}" --vpc-ids "${vpc_id}" \
    --query "Vpcs[0].Tags[?Key=='Name'].Value | [0]" --output text)"
  [ "${name}" = "None" ] && name="(no Name tag)"

  echo "VPC ${vpc_id}  (cidr=${cidr}, name=${name}, default=${is_default})  -> ${az_count} AZs"
  aws ec2 describe-subnets --region "${AWS_REGION}" --subnet-ids ${egress_subnets} \
    --query "Subnets[].[SubnetId, AvailabilityZone, CidrBlock, (Tags[?Key=='Name'].Value | [0])]" \
    --output text | sort -k2 | while read -r sid az scidr sname; do
      { [ -z "${sname}" ] || [ "${sname}" = "None" ]; } && sname="(no Name tag)"
      printf "    %-24s  %-16s  %-18s  %s\n" "${sid}" "${az}" "${scidr}" "${sname}"
    done
  echo
done

if [ "${suitable_count}" -eq 0 ]; then
  echo "No suitable VPC found in ${AWS_REGION}."
  echo "You need a VPC with private subnets that have egress (NAT Gateway) in >= 2 AZs,"
  echo "or free up quota and deploy without -c vpcId to create a new VPC."
else
  echo "Reuse one with:   npx cdk deploy -c vpcId=<VpcId>"
fi
