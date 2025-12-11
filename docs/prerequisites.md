# Prerequisites for AWS DevOps Agent and Prometheus MCP Demo

## AWS Account Requirements

### Account Limits and Quotas

Ensure your AWS account has sufficient quotas for:

- **Amazon EKS:**
  - Clusters: At least 1
  - Node groups: At least 2
  - Fargate profiles (optional): At least 1

- **Amazon EC2:**
  - Running On-Demand instances (t3.large or larger): At least 3
  - Elastic IP addresses: At least 2

- **AWS Managed Prometheus (AMP):**
  - Workspaces: At least 1
  - Active series: 10,000+

- **CloudWatch:**
  - Log groups: 20+
  - Metrics: Unlimited (pay per use)
  - Alarms: At least 10

### IAM Permissions

The IAM user or role deploying the stack must have permissions for:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "eks:*",
        "ec2:*",
        "iam:*",
        "cloudformation:*",
        "cloudwatch:*",
        "logs:*",
        "aps:*",
        "xray:*",
        "ecr:*",
        "secretsmanager:*",
        "events:*",
        "sqs:*",
        "sns:*",
        "s3:*",
        "elasticloadbalancing:*"
      ],
      "Resource": "*"
    }
  ]
}
```

## Required AWS Services

### 1. Amazon EKS Cluster

- **Version:** 1.28 or later
- **Compute:** Managed node group with at least 3 nodes (t3.large or larger)
- **Networking:** VPC with public and private subnets
- **Add-ons:**
  - VPC CNI
  - kube-proxy
  - CoreDNS
  - AWS Load Balancer Controller

**Estimated Cost:** $150-200/month

### 2. CloudWatch Container Insights

- Enabled on the EKS cluster
- FluentBit daemonset deployed
- CloudWatch agent configured

**Estimated Cost:** $20-30/month

### 3. AWS Managed Prometheus (AMP)

- Workspace created
- Prometheus server configured to remote write
- SigV4 authentication enabled

**Estimated Cost:** $30-40/month

### 4. AWS X-Ray

- X-Ray daemon deployed in cluster
- Application instrumented with X-Ray SDK
- Service map available

**Estimated Cost:** $5-10/month

### 5. Amazon Managed Grafana (Optional but Recommended)

- Workspace created
- Data sources configured (AMP, CloudWatch)
- Dashboards imported

**Estimated Cost:** $9/user/month

## Required Tools

### Local Development Tools

Install the following tools on your workstation:

#### 1. AWS CLI

```bash
# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure credentials
aws configure

# Verify
aws --version
```

#### 2. kubectl

```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Verify
kubectl version --client
```

#### 3. eksctl

```bash
# Install eksctl
curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
sudo mv /tmp/eksctl /usr/local/bin

# Verify
eksctl version
```

#### 4. Helm

```bash
# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify
helm version
```

#### 5. Docker

```bash
# Install Docker (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y docker.io

# Start Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group
sudo usermod -aG docker $USER

# Verify
docker --version
```

#### 6. Node.js and npm (for CDK)

```bash
# Install Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify
node --version
npm --version
```

#### 7. AWS CDK

```bash
# Install AWS CDK
npm install -g aws-cdk

# Verify
cdk --version
```

## Slack Workspace Setup

### 1. Create Slack App

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name: "DevOps Agent"
4. Select your workspace

### 2. Configure Bot Token Scopes

Add the following OAuth scopes under "OAuth & Permissions":

```
chat:write
chat:write.public
files:write
channels:read
groups:read
im:read
mpim:read
users:read
```

### 3. Install App to Workspace

1. Click "Install to Workspace"
2. Copy the "Bot User OAuth Token" (starts with `xoxb-`)
3. Store it securely (you'll add it to AWS Secrets Manager)

### 4. Create Slack Channel

```bash
# Create a channel for incidents
Channel name: #eks-incidents
Purpose: EKS incident notifications from DevOps Agent
```

### 5. Invite Bot to Channel

In Slack:
```
/invite @DevOps Agent
```

## Network Requirements

### VPC Configuration

- **CIDR:** At least /16 (e.g., 10.0.0.0/16)
- **Subnets:**
  - Public subnets: At least 2 (in different AZs)
  - Private subnets: At least 2 (in different AZs)
- **NAT Gateways:** 1-2 (for private subnet internet access)
- **Internet Gateway:** 1

### Security Groups

- EKS cluster security group
- Node security group
- Allow intra-cluster communication
- Allow ALB ingress (ports 80, 443)

### DNS

- Route53 hosted zone (optional, for custom domain)
- DNS resolution enabled in VPC

## Application Prerequisites

### Pet Adoptions Application

The demo requires the Pet Adoptions application to be deployed:

1. **Services:**
   - petsite (frontend)
   - petsearch-java
   - payforadoption-go
   - petlistadoptions-go
   - petadoptionshistory-py

2. **Databases:**
   - Amazon RDS (PostgreSQL or MySQL)
   - Amazon DynamoDB tables

3. **Storage:**
   - S3 bucket for pet images

4. **Load Balancing:**
   - Application Load Balancer

## Verification Checklist

Before proceeding with the DevOps Agent deployment:

- [ ] EKS cluster is running and accessible
- [ ] kubectl can connect to the cluster
- [ ] Container Insights is enabled
- [ ] Prometheus workspace is created
- [ ] X-Ray daemon is deployed
- [ ] Pet Adoptions services are running
- [ ] Grafana workspace is configured (optional)
- [ ] Slack app is created and token obtained
- [ ] IAM permissions are sufficient
- [ ] AWS CLI is configured
- [ ] All required tools are installed

## Quick Verification Script

```bash
#!/bin/bash

echo "=== Checking Prerequisites ==="

# Check AWS CLI
if command -v aws &> /dev/null; then
    echo "✓ AWS CLI installed: $(aws --version)"
else
    echo "✗ AWS CLI not found"
fi

# Check kubectl
if command -v kubectl &> /dev/null; then
    echo "✓ kubectl installed: $(kubectl version --client --short 2>/dev/null)"
else
    echo "✗ kubectl not found"
fi

# Check eksctl
if command -v eksctl &> /dev/null; then
    echo "✓ eksctl installed: $(eksctl version)"
else
    echo "✗ eksctl not found"
fi

# Check Helm
if command -v helm &> /dev/null; then
    echo "✓ Helm installed: $(helm version --short)"
else
    echo "✗ Helm not found"
fi

# Check Docker
if command -v docker &> /dev/null; then
    echo "✓ Docker installed: $(docker --version)"
else
    echo "✗ Docker not found"
fi

# Check CDK
if command -v cdk &> /dev/null; then
    echo "✓ AWS CDK installed: $(cdk --version)"
else
    echo "✗ AWS CDK not found"
fi

# Check EKS cluster access
if kubectl get nodes &> /dev/null; then
    echo "✓ EKS cluster accessible"
    echo "  Nodes: $(kubectl get nodes --no-headers | wc -l)"
else
    echo "✗ Cannot access EKS cluster"
fi

# Check Container Insights
if kubectl get daemonset aws-for-fluent-bit -n amazon-cloudwatch &> /dev/null; then
    echo "✓ Container Insights FluentBit deployed"
else
    echo "⚠ Container Insights may not be configured"
fi

# Check X-Ray daemon
if kubectl get daemonset xray-daemon -n default &> /dev/null; then
    echo "✓ X-Ray daemon deployed"
else
    echo "⚠ X-Ray daemon not found"
fi

echo ""
echo "=== Estimated Monthly Costs ==="
echo "EKS Cluster:         $150-200"
echo "CloudWatch:          $20-30"
echo "AMP:                 $30-40"
echo "X-Ray:               $5-10"
echo "Grafana (optional):  $9"
echo "--------------------------------"
echo "Total:               $205-290/month"
```

Save this as `check-prerequisites.sh` and run it:

```bash
chmod +x check-prerequisites.sh
./check-prerequisites.sh
```

## Next Steps

Once all prerequisites are met, proceed to:

1. [Deployment Guide](./deployment-guide.md)
2. [Configuration Guide](./configuration-guide.md)
3. [Demo Walkthrough](./devops-agent-demo.md)

## Troubleshooting

### Common Issues

**Issue:** kubectl cannot connect to cluster
```bash
# Update kubeconfig
aws eks update-kubeconfig --region <region> --name <cluster-name>
```

**Issue:** Insufficient IAM permissions
```bash
# Check current identity
aws sts get-caller-identity

# Review required permissions in IAM
```

**Issue:** Container Insights not showing data
```bash
# Check FluentBit logs
kubectl logs -n amazon-cloudwatch -l app.kubernetes.io/name=aws-for-fluent-bit

# Verify IAM role for service account
kubectl describe sa fluent-bit -n amazon-cloudwatch
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/aws-samples/one-observability-demo/issues
- AWS Support: https://aws.amazon.com/support/
- Documentation: https://docs.aws.amazon.com/
