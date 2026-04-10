#!/bin/bash

# InsureMail AI Deployment Script
# This script deploys all AWS resources for the InsureMail AI system

set -e

echo "=========================================="
echo "InsureMail AI - Deployment Script"
echo "=========================================="

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${STACK_NAME:-insuremail-ai}"
S3_BUCKET="${S3_BUCKET:-insuremail-deployment-$(date +%s)}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Please run 'aws configure'"
        exit 1
    fi
    
    log_info "Prerequisites check passed!"
}

# Create S3 bucket for deployment artifacts
create_deployment_bucket() {
    log_info "Creating deployment S3 bucket: $S3_BUCKET"
    
    if aws s3 ls "s3://$S3_BUCKET" 2>&1 | grep -q 'NoSuchBucket'; then
        aws s3 mb "s3://$S3_BUCKET" --region "$AWS_REGION"
        aws s3api put-bucket-versioning \
            --bucket "$S3_BUCKET" \
            --versioning-configuration Status=Enabled
        log_info "Deployment bucket created successfully"
    else
        log_warn "Bucket $S3_BUCKET already exists"
    fi
}

# Deploy Lambda functions
deploy_lambda_functions() {
    log_info "Deploying Lambda functions..."
    
    LAMBDA_FUNCTIONS=(
        "email_parser:insuremail-email-parser"
        "classify_intent:insuremail-classify-intent"
        "retrieve_knowledge:insuremail-retrieve-knowledge"
        "crm_validation:insuremail-crm-validation"
        "generate_response:insuremail-generate-response"
        "email_sender:insuremail-email-sender"
        "save_result:insuremail-save-result"
        "gmail_imap_poller:insuremail-gmail-imap-poller"
    )
    
    for func in "${LAMBDA_FUNCTIONS[@]}"; do
        IFS=':' read -r file_name func_name <<< "$func"
        
        log_info "Deploying $func_name..."
        
        # Create deployment package
        cd "../backend/lambda-functions"
        
        # Check if function exists
        if aws lambda get-function --function-name "$func_name" --region "$AWS_REGION" &> /dev/null; then
            # Update function code
            aws lambda update-function-code \
                --function-name "$func_name" \
                --zip-file "fileb://${file_name}.zip" \
                --region "$AWS_REGION" > /dev/null
            log_info "Updated $func_name"
        else
            log_warn "Function $func_name does not exist. Please create it first."
        fi
        
        cd - > /dev/null
    done
}

# Deploy API Gateway
deploy_api_gateway() {
    log_info "Deploying API Gateway..."
    
    API_NAME="insuremail-api"
    
    # Check if API exists
    API_ID=$(aws apigateway get-rest-apis --region "$AWS_REGION" --query "items[?name=='$API_NAME'].id" --output text)
    
    if [ -z "$API_ID" ] || [ "$API_ID" == "None" ]; then
        log_info "Creating new API Gateway: $API_NAME"
        
        # Create REST API
        API_ID=$(aws apigateway create-rest-api \
            --name "$API_NAME" \
            --region "$AWS_REGION" \
            --query 'id' --output text)
        
        log_info "Created API with ID: $API_ID"
    else
        log_info "Using existing API: $API_ID"
    fi
    
    # Get root resource ID
    ROOT_RESOURCE_ID=$(aws apigateway get-resources \
        --rest-api-id "$API_ID" \
        --region "$AWS_REGION" \
        --query 'items[?path==`/`].id' --output text)
    
    log_info "API Gateway deployment complete"
    log_info "API Endpoint: https://$API_ID.execute-api.$AWS_REGION.amazonaws.com/prod"
}

# Deploy Step Functions
deploy_step_functions() {
    log_info "Deploying Step Functions..."
    
    STATE_MACHINE_NAME="insuremail-email-processor"
    
    # Read workflow definition
    WORKFLOW_DEFINITION=$(cat ../backend/step-functions/email_processing_workflow.json)
    
    # Check if state machine exists
    STATE_MACHINE_ARN=$(aws stepfunctions list-state-machines \
        --region "$AWS_REGION" \
        --query "stateMachines[?name=='$STATE_MACHINE_NAME'].stateMachineArn" --output text)
    
    if [ -z "$STATE_MACHINE_ARN" ] || [ "$STATE_MACHINE_ARN" == "None" ]; then
        log_info "Creating new state machine: $STATE_MACHINE_NAME"
        
        # Create state machine
        STATE_MACHINE_ARN=$(aws stepfunctions create-state-machine \
            --name "$STATE_MACHINE_NAME" \
            --definition "$WORKFLOW_DEFINITION" \
            --role-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/StepFunctions-InsureMail-Role" \
            --region "$AWS_REGION" \
            --query 'stateMachineArn' --output text)
        
        log_info "Created state machine: $STATE_MACHINE_ARN"
    else
        log_info "Updating existing state machine: $STATE_MACHINE_ARN"
        
        aws stepfunctions update-state-machine \
            --state-machine-arn "$STATE_MACHINE_ARN" \
            --definition "$WORKFLOW_DEFINITION" \
            --region "$AWS_REGION" > /dev/null
    fi
    
    log_info "Step Functions deployment complete"
}

# Create DynamoDB tables
create_dynamodb_tables() {
    log_info "Creating DynamoDB tables..."
    
    TABLES=(
        "InsureMail-Emails:email_id"
        "InsureMail-Customers:member_id"
        "InsureMail-Knowledge:doc_id"
    )
    
    for table in "${TABLES[@]}"; do
        IFS=':' read -r table_name key_name <<< "$table"
        
        if aws dynamodb describe-table --table-name "$table_name" --region "$AWS_REGION" &> /dev/null; then
            log_warn "Table $table_name already exists"
        else
            log_info "Creating table: $table_name"
            
            aws dynamodb create-table \
                --table-name "$table_name" \
                --attribute-definitions AttributeName="$key_name",AttributeType=S \
                --key-schema AttributeName="$key_name",KeyType=HASH \
                --billing-mode PAY_PER_REQUEST \
                --region "$AWS_REGION" > /dev/null
            
            log_info "Created table: $table_name"
        fi
    done
}

# Create S3 buckets
create_s3_buckets() {
    log_info "Creating S3 buckets..."
    
    BUCKETS=(
        "insuremail-incoming"
        "insuremail-attachments"
        "insuremail-models"
        "insuremail-audit"
    )
    
    for bucket in "${BUCKETS[@]}"; do
        BUCKET_NAME="${bucket}-$(aws sts get-caller-identity --query Account --output text)"
        
        if aws s3 ls "s3://$BUCKET_NAME" 2>&1 | grep -q 'NoSuchBucket'; then
            log_info "Creating bucket: $BUCKET_NAME"
            aws s3 mb "s3://$BUCKET_NAME" --region "$AWS_REGION"
            
            # Enable versioning
            aws s3api put-bucket-versioning \
                --bucket "$BUCKET_NAME" \
                --versioning-configuration Status=Enabled
            
            log_info "Created bucket: $BUCKET_NAME"
        else
            log_warn "Bucket $BUCKET_NAME already exists"
        fi
    done
}

# Deploy frontend
deploy_frontend() {
    log_info "Deploying frontend..."
    
    FRONTEND_BUCKET="insuremail-dashboard-$(aws sts get-caller-identity --query Account --output text)"
    
    # Create bucket if not exists
    if aws s3 ls "s3://$FRONTEND_BUCKET" 2>&1 | grep -q 'NoSuchBucket'; then
        aws s3 mb "s3://$FRONTEND_BUCKET" --region "$AWS_REGION"
        aws s3 website "s3://$FRONTEND_BUCKET" --index-document index.html --error-document index.html
    fi
    
    # Build frontend
    cd ../frontend/dashboard
    npm install
    npm run build
    
    # Upload to S3
    aws s3 sync dist/ "s3://$FRONTEND_BUCKET" --delete
    
    cd - > /dev/null
    
    log_info "Frontend deployed to: http://$FRONTEND_BUCKET.s3-website-$AWS_REGION.amazonaws.com"
}

# Print deployment summary
print_summary() {
    echo ""
    echo "=========================================="
    echo "Deployment Summary"
    echo "=========================================="
    echo "Region: $AWS_REGION"
    echo "Stack: $STACK_NAME"
    echo ""
    echo "Resources Created:"
    echo "  - Lambda Functions: 8"
    echo "  - DynamoDB Tables: 3"
    echo "  - S3 Buckets: 5"
    echo "  - Step Functions: 1"
    echo "  - API Gateway: 1"
    echo ""
    echo "Next Steps:"
    echo "  1. Configure Gmail IMAP credentials"
    echo "  2. Verify SES email address"
    echo "  3. Train and upload ML models"
    echo "  4. Upload knowledge base documents"
    echo "  5. Test the workflow"
    echo "=========================================="
}

# Main deployment flow
main() {
    check_prerequisites
    create_deployment_bucket
    create_s3_buckets
    create_dynamodb_tables
    deploy_lambda_functions
    deploy_step_functions
    deploy_api_gateway
    deploy_frontend
    print_summary
}

# Run main function
main "$@"
