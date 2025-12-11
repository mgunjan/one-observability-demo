#!/bin/bash
#
# Build and Push Docker Images for DevOps Agent and Prometheus MCP Server
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Building and Pushing Container Images${NC}"
echo -e "${GREEN}========================================${NC}"
echo "AWS Region: $AWS_REGION"
echo "ECR Registry: $ECR_REGISTRY"
echo ""

# Login to ECR
echo -e "${YELLOW}Logging in to Amazon ECR...${NC}"
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

# Create ECR repositories if they don't exist
echo -e "${YELLOW}Creating ECR repositories...${NC}"
aws ecr create-repository --repository-name devops-agent --region $AWS_REGION 2>/dev/null || true
aws ecr create-repository --repository-name prometheus-mcp-server --region $AWS_REGION 2>/dev/null || true

# Build DevOps Agent
echo -e "${YELLOW}Building DevOps Agent...${NC}"
cd devops-agent
docker build -t devops-agent:latest .
docker tag devops-agent:latest $ECR_REGISTRY/devops-agent:latest
docker tag devops-agent:latest $ECR_REGISTRY/devops-agent:$(date +%Y%m%d%H%M%S)

echo -e "${YELLOW}Pushing DevOps Agent...${NC}"
docker push $ECR_REGISTRY/devops-agent:latest
docker push $ECR_REGISTRY/devops-agent:$(date +%Y%m%d%H%M%S)
cd ..

# Build Prometheus MCP Server
echo -e "${YELLOW}Building Prometheus MCP Server...${NC}"
cd prometheus-mcp-server
docker build -t prometheus-mcp-server:latest .
docker tag prometheus-mcp-server:latest $ECR_REGISTRY/prometheus-mcp-server:latest
docker tag prometheus-mcp-server:latest $ECR_REGISTRY/prometheus-mcp-server:$(date +%Y%m%d%H%M%S)

echo -e "${YELLOW}Pushing Prometheus MCP Server...${NC}"
docker push $ECR_REGISTRY/prometheus-mcp-server:latest
docker push $ECR_REGISTRY/prometheus-mcp-server:$(date +%Y%m%d%H%M%S)
cd ..

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Build and Push Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Images pushed to:"
echo "  - $ECR_REGISTRY/devops-agent:latest"
echo "  - $ECR_REGISTRY/prometheus-mcp-server:latest"
echo ""
echo "Next steps:"
echo "  1. Update manifests with ECR registry: $ECR_REGISTRY"
echo "  2. Deploy to Kubernetes:"
echo "     kubectl apply -f devops-agent/manifests/"
echo "     kubectl apply -f prometheus-mcp-server/manifests/"
echo "  3. Verify deployment:"
echo "     kubectl get pods -n devops-agent"
echo ""
