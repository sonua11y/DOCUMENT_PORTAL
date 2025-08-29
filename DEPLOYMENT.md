# 🚀 Document Portal Deployment Guide

This guide will help you deploy the Document Portal application to AWS ECS using automated CI/CD with GitHub Actions.

## 📋 Prerequisites

### 1. AWS Account Setup
- AWS Account with appropriate permissions
- AWS CLI installed and configured
- Docker installed locally

### 2. Required AWS Services
- **ECS (Elastic Container Service)** - For running containers
- **ECR (Elastic Container Registry)** - For storing Docker images
- **VPC** - Network infrastructure
- **IAM** - Roles and permissions
- **Secrets Manager** - For API keys
- **CloudWatch** - For logging

### 3. API Keys Required
- **Google API Key** (for Gemini AI)
- **Groq API Key** (for alternative LLM)
- **LangChain API Key** (optional, for tracing)

## 🔧 Step-by-Step Deployment

### Step 1: AWS Account Configuration

1. **Create IAM User for GitHub Actions**
   ```bash
   # Create IAM user
   aws iam create-user --user-name github-actions-user
   
   # Attach necessary policies
   aws iam attach-user-policy --user-name github-actions-user --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess
   aws iam attach-user-policy --user-name github-actions-user --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess
   
   # Create access keys
   aws iam create-access-key --user-name github-actions-user
   ```

2. **Create Custom IAM Policies**
   
   Create policy: `AllowECSLogs`
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Effect": "Allow",
               "Action": [
                   "logs:CreateLogGroup",
                   "logs:CreateLogStream",
                   "logs:PutLogEvents"
               ],
               "Resource": "*"
           }
       ]
   }
   ```
   
   Create policy: `AllowSecretsAccess`
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Effect": "Allow",
               "Action": "secretsmanager:GetSecretValue",
               "Resource": "arn:aws:secretsmanager:*:*:secret:*"
           }
       ]
   }
   ```

### Step 2: Set Up AWS Secrets Manager

1. **Create API Key Secrets**
   ```bash
   # Create Google API Key secret
   aws secretsmanager create-secret \
       --name "GOOGLE_API_KEY" \
       --description "Google Generative AI API Key" \
       --secret-string "your-google-api-key-here"
   
   # Create Groq API Key secret
   aws secretsmanager create-secret \
       --name "GROQ_API_KEY" \
       --description "Groq API Key" \
       --secret-string "your-groq-api-key-here"
   
   # Create LangChain API Key secret (optional)
   aws secretsmanager create-secret \
       --name "LANGCHAIN_API_KEY" \
       --description "LangChain API Key" \
       --secret-string "your-langchain-api-key-here"
   ```

### Step 3: GitHub Repository Setup

1. **Add Repository Secrets**
   Go to GitHub Repository → Settings → Secrets and variables → Actions
   
   Add these secrets:
   - `AWS_ACCESS_KEY_ID`: From Step 1
   - `AWS_SECRET_ACCESS_KEY`: From Step 1

### Step 4: Update Configuration Files

1. **Update task-definition.json**
   Replace `YOUR_ACCOUNT_ID` with your AWS Account ID:
   ```bash
   # Get your AWS Account ID
   aws sts get-caller-identity --query Account --output text
   
   # Update the task definition
   sed -i 's/YOUR_ACCOUNT_ID/123456789012/g' infrastructure/task-definition.json
   ```

2. **Update CloudFormation template**
   Update the secret ARNs in `infrastructure/document-portal-cf.yaml` with your account ID and region.

### Step 5: Deploy Infrastructure

#### Option A: Automated Deployment (Recommended)
```bash
# Make the deployment script executable
chmod +x deploy.sh

# Run the deployment script
./deploy.sh
```

#### Option B: Manual Deployment
```bash
# 1. Build Docker image
docker build -t documentportal:latest .

# 2. Create ECR repository
aws ecr create-repository --repository-name documentportal

# 3. Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# 4. Tag and push image
docker tag documentportal:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/documentportal:latest
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/documentportal:latest

# 5. Deploy CloudFormation stack
aws cloudformation create-stack \
    --stack-name document-portal-stack \
    --template-body file://infrastructure/document-portal-cf.yaml \
    --parameters ParameterKey=ImageUrl,ParameterValue=YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/documentportal:latest \
    --capabilities CAPABILITY_NAMED_IAM
```

### Step 6: Configure Security Groups

1. **Update Security Group**
   ```bash
   # Find your security group ID
   aws ec2 describe-security-groups --filters "Name=group-name,Values=*ECS*"
   
   # Add inbound rule for port 8080
   aws ec2 authorize-security-group-ingress \
       --group-id sg-xxxxxxxxx \
       --protocol tcp \
       --port 8080 \
       --cidr 0.0.0.0/0
   ```

### Step 7: Access Your Application

1. **Get Public IP**
   ```bash
   # Get running task
   TASK_ARN=$(aws ecs list-tasks --cluster document-portal-cluster --service-name document-portal-service --query 'taskArns[0]' --output text)
   
   # Get network interface
   ENI_ID=$(aws ecs describe-tasks --cluster document-portal-cluster --tasks $TASK_ARN --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)
   
   # Get public IP
   PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID --query 'NetworkInterfaces[0].Association.PublicIp' --output text)
   
   echo "Application URL: http://$PUBLIC_IP:8080"
   ```

2. **Access Points**
   - **Main Application**: `http://YOUR_PUBLIC_IP:8080`
   - **API Documentation**: `http://YOUR_PUBLIC_IP:8080/docs`
   - **Health Check**: `http://YOUR_PUBLIC_IP:8080/health`

## 📊 Monitoring and Logs

### View Application Logs
```bash
# View real-time logs
aws logs tail /ecs/documentportal --follow

# View specific log stream
aws logs describe-log-streams --log-group-name /ecs/documentportal
```

### Monitor ECS Service
```bash
# Check service status
aws ecs describe-services --cluster document-portal-cluster --services document-portal-service

# Check task status
aws ecs list-tasks --cluster document-portal-cluster --service-name document-portal-service
```

## 🔄 CI/CD with GitHub Actions

Once set up, every push to the `main` branch will automatically:

1. Build the Docker image
2. Push to ECR
3. Update the ECS task definition
4. Deploy the new version
5. Wait for deployment completion

## 🛠️ Troubleshooting

### Common Issues

1. **Task Fails to Start**
   - Check CloudWatch logs: `/ecs/documentportal`
   - Verify API keys in Secrets Manager
   - Check task definition CPU/memory limits

2. **Application Not Accessible**
   - Verify security group allows port 8080
   - Check if task has public IP assigned
   - Verify VPC and subnet configuration

3. **API Key Issues**
   - Ensure secrets exist in Secrets Manager
   - Verify IAM role has `secretsmanager:GetSecretValue` permission
   - Check secret ARNs in task definition

4. **Docker Build Issues**
   - Ensure all dependencies are in requirements.txt
   - Check Dockerfile syntax
   - Verify base image compatibility

### Useful Commands

```bash
# Check ECS service events
aws ecs describe-services --cluster document-portal-cluster --services document-portal-service --query 'services[0].events'

# Force new deployment
aws ecs update-service --cluster document-portal-cluster --service document-portal-service --force-new-deployment

# Scale service
aws ecs update-service --cluster document-portal-cluster --service document-portal-service --desired-count 2

# Stop all tasks (for maintenance)
aws ecs update-service --cluster document-portal-cluster --service document-portal-service --desired-count 0
```

## 📞 Support

For issues or questions:
1. Check CloudWatch logs first
2. Review AWS ECS service events
3. Verify all prerequisites are met
4. Check GitHub Actions workflow logs

## 🎉 Success!

Your Document Portal is now deployed and accessible! The application provides:
- Document analysis using AI
- Document comparison capabilities
- Chat functionality with RAG
- RESTful API with automatic documentation
