#!/usr/bin/env bash
# PatientSynapse — AWS Infrastructure Setup via CLI
# Run this from your local machine (requires aws cli configured)
set -euo pipefail

DOMAIN="patientsynapse.com"
REGION="us-east-1"
KEY_NAME="patientsynapse-key"
INSTANCE_TYPE="t3.small"
AMI_ID="ami-0f9de6e2d2f067fca"  # Ubuntu 24.04 LTS us-east-1 (update if different region)

echo "=== PatientSynapse AWS Setup ==="

# ---- 1. Create Key Pair ----
echo "[1/6] Creating SSH key pair..."
if aws ec2 describe-key-pairs --key-names "$KEY_NAME" --region "$REGION" 2>/dev/null; then
  echo "  Key pair '$KEY_NAME' already exists, skipping."
else
  aws ec2 create-key-pair \
    --key-name "$KEY_NAME" \
    --key-type rsa \
    --region "$REGION" \
    --query 'KeyMaterial' \
    --output text > ~/.ssh/${KEY_NAME}.pem
  chmod 400 ~/.ssh/${KEY_NAME}.pem
  echo "  Saved to ~/.ssh/${KEY_NAME}.pem"
fi

# ---- 2. Create Security Group ----
echo "[2/6] Creating security group..."
VPC_ID=$(aws ec2 describe-vpcs --region "$REGION" --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text)

SG_ID=$(aws ec2 describe-security-groups \
  --region "$REGION" \
  --filters "Name=group-name,Values=patientsynapse-sg" "Name=vpc-id,Values=$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  SG_ID=$(aws ec2 create-security-group \
    --group-name patientsynapse-sg \
    --description "PatientSynapse - SSH, HTTP, HTTPS" \
    --vpc-id "$VPC_ID" \
    --region "$REGION" \
    --query 'GroupId' --output text)

  # SSH
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --region "$REGION" \
    --protocol tcp --port 22 --cidr 0.0.0.0/0
  # HTTP
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --region "$REGION" \
    --protocol tcp --port 80 --cidr 0.0.0.0/0
  # HTTPS
  aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --region "$REGION" \
    --protocol tcp --port 443 --cidr 0.0.0.0/0

  echo "  Created security group: $SG_ID"
else
  echo "  Security group already exists: $SG_ID"
fi

# ---- 3. Launch EC2 Instance ----
echo "[3/6] Launching EC2 instance..."
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --key-name "$KEY_NAME" \
  --security-group-ids "$SG_ID" \
  --region "$REGION" \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=patientsynapse}]" \
  --query 'Instances[0].InstanceId' --output text)

echo "  Instance launched: $INSTANCE_ID"
echo "  Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"

# ---- 4. Allocate and Associate Elastic IP ----
echo "[4/6] Allocating Elastic IP..."
ALLOC_ID=$(aws ec2 allocate-address --domain vpc --region "$REGION" --query 'AllocationId' --output text)
EIP=$(aws ec2 describe-addresses --allocation-ids "$ALLOC_ID" --region "$REGION" --query 'Addresses[0].PublicIp' --output text)

aws ec2 associate-address --instance-id "$INSTANCE_ID" --allocation-id "$ALLOC_ID" --region "$REGION"
echo "  Elastic IP: $EIP"

# ---- 5. Route53 DNS ----
echo "[5/6] Configuring Route53 DNS..."
HOSTED_ZONE_ID=$(aws route53 list-hosted-zones-by-name \
  --dns-name "$DOMAIN" \
  --query 'HostedZones[0].Id' --output text | sed 's|/hostedzone/||')

if [ -n "$HOSTED_ZONE_ID" ] && [ "$HOSTED_ZONE_ID" != "None" ]; then
  aws route53 change-resource-record-sets \
    --hosted-zone-id "$HOSTED_ZONE_ID" \
    --change-batch "{
      \"Changes\": [
        {
          \"Action\": \"UPSERT\",
          \"ResourceRecordSet\": {
            \"Name\": \"$DOMAIN\",
            \"Type\": \"A\",
            \"TTL\": 300,
            \"ResourceRecords\": [{\"Value\": \"$EIP\"}]
          }
        },
        {
          \"Action\": \"UPSERT\",
          \"ResourceRecordSet\": {
            \"Name\": \"www.$DOMAIN\",
            \"Type\": \"A\",
            \"TTL\": 300,
            \"ResourceRecords\": [{\"Value\": \"$EIP\"}]
          }
        }
      ]
    }"
  echo "  DNS records created: $DOMAIN -> $EIP"
else
  echo "  WARNING: Hosted zone for $DOMAIN not found. Create DNS records manually."
fi

# ---- 6. Output summary ----
echo ""
echo "=== Setup Complete ==="
echo "Instance ID:  $INSTANCE_ID"
echo "Elastic IP:   $EIP"
echo "SSH Key:      ~/.ssh/${KEY_NAME}.pem"
echo "Security Grp: $SG_ID"
echo ""
echo "Next steps:"
echo "  1. Wait ~2 min for instance to fully boot"
echo "  2. SSH in:  ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@$EIP"
echo "  3. Run:     bash scripts/server-setup.sh"
echo "  4. Deploy:  bash scripts/deploy.sh"
