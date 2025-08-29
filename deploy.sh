#!/bin/bash

# Document Portal Deployment Script
# This script helps automate the AWS ECS deployment process

set -e

echo "🚀 Document Portal Deployment Script"
echo "======================================"

# Configuration
AWS_REGION="us-east-1"
ECR_REPOSITORY="documentportal"
ECS_CLUSTER="document-portal-cluster"
ECS_SERVICE="document-portal-service"
STACK_NAME="document-portal-stack"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install it first."
    exit 1
fi

# Get AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
print_status "AWS Account ID: $AWS_ACCOUNT_ID"

# Step 1: Build and test Docker image locally
echo ""
echo "📦 Step 1: Building Docker image locally..."
docker build -t $ECR_REPOSITORY:latest .
print_status "Docker image built successfully"

# Step 2: Create ECR repository if it doesn't exist
echo ""
echo "🏗️  Step 2: Setting up ECR repository..."
aws ecr describe-repositories --repository-names $ECR_REPOSITORY --region $AWS_REGION 2>/dev/null || {
    print_warning "ECR repository doesn't exist. Creating..."
    aws ecr create-repository --repository-name $ECR_REPOSITORY --region $AWS_REGION
    print_status "ECR repository created"
}

# Step 3: Login to ECR
echo ""
echo "🔐 Step 3: Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
print_status "Logged into ECR"

# Step 4: Tag and push image
echo ""
echo "🚢 Step 4: Pushing image to ECR..."
docker tag $ECR_REPOSITORY:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest
print_status "Image pushed to ECR"

# Step 5: Update task definition with new image
echo ""
echo "📝 Step 5: Updating task definition..."
sed -i.bak "s/YOUR_ACCOUNT_ID/$AWS_ACCOUNT_ID/g" infrastructure/task-definition.json
print_status "Task definition updated"

# Step 6: Deploy CloudFormation stack (if needed)
echo ""
echo "☁️  Step 6: Checking CloudFormation stack..."
if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION 2>/dev/null; then
    print_warning "Stack exists. Updating..."
    aws cloudformation update-stack \
        --stack-name $STACK_NAME \
        --template-body file://infrastructure/document-portal-cf.yaml \
        --parameters ParameterKey=ImageUrl,ParameterValue=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest \
        --capabilities CAPABILITY_NAMED_IAM \
        --region $AWS_REGION
else
    print_warning "Stack doesn't exist. Creating..."
    aws cloudformation create-stack \
        --stack-name $STACK_NAME \
        --template-body file://infrastructure/document-portal-cf.yaml \
        --parameters ParameterKey=ImageUrl,ParameterValue=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest \
        --capabilities CAPABILITY_NAMED_IAM \
        --region $AWS_REGION
fi

echo ""
echo "⏳ Waiting for stack to be ready..."
aws cloudformation wait stack-create-complete --stack-name $STACK_NAME --region $AWS_REGION 2>/dev/null || \
aws cloudformation wait stack-update-complete --stack-name $STACK_NAME --region $AWS_REGION 2>/dev/null

print_status "CloudFormation stack ready"

# Step 7: Update ECS service
echo ""
echo "🔄 Step 7: Updating ECS service..."
aws ecs update-service \
    --cluster $ECS_CLUSTER \
    --service $ECS_SERVICE \
    --force-new-deployment \
    --region $AWS_REGION

print_status "ECS service updated"

# Step 8: Get service URL
echo ""
echo "🌐 Step 8: Getting service URL..."
TASK_ARN=$(aws ecs list-tasks --cluster $ECS_CLUSTER --service-name $ECS_SERVICE --query 'taskArns[0]' --output text --region $AWS_REGION)
if [ "$TASK_ARN" != "None" ]; then
    PUBLIC_IP=$(aws ecs describe-tasks --cluster $ECS_CLUSTER --tasks $TASK_ARN --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text --region $AWS_REGION)
    if [ "$PUBLIC_IP" != "" ]; then
        ENI_ID=$PUBLIC_IP
        PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID --query 'NetworkInterfaces[0].Association.PublicIp' --output text --region $AWS_REGION)
        echo ""
        print_status "🎉 Deployment complete!"
        echo ""
        echo "📱 Access your application at: http://$PUBLIC_IP:8080"
        echo "📚 API Documentation: http://$PUBLIC_IP:8080/docs"
        echo "🔍 Health Check: http://$PUBLIC_IP:8080/health"
    fi
fi

echo ""
echo "📊 To monitor logs:"
echo "aws logs tail /ecs/documentportal --follow --region $AWS_REGION"

echo ""
print_status "Deployment script completed!"
