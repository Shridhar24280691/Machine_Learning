# InsureMail AI Deployment Script (PowerShell Version)
# This script deploys all AWS resources for the InsureMail AI system

param(
    [string]$AWSRegion = "us-east-1",
    [string]$StackName = "insuremail-ai",
    [string]$S3Bucket = "insuremail-deployment-$(Get-Date -Format 'yyyyMMddHHmmss')"
)

# Colors for output
$Green = "Green"
$Yellow = "Yellow"
$Red = "Red"
$White = "White"

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor $Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor $Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor $Red
}

# Check prerequisites
function Check-Prerequisites {
    Write-Info "Checking prerequisites..."

    # Check AWS CLI
    try {
        $awsVersion = aws --version 2>$null
        Write-Info "AWS CLI found: $awsVersion"
    }
    catch {
        Write-Error "AWS CLI is not installed or not in PATH. Please install it first."
        exit 1
    }

    # Check AWS credentials
    try {
        aws sts get-caller-identity >$null 2>&1
        Write-Info "AWS credentials configured successfully"
    }
    catch {
        Write-Error "AWS credentials not configured. Please run 'aws configure'"
        exit 1
    }

    Write-Info "Prerequisites check passed!"
}

# Create S3 bucket for deployment artifacts
function New-DeploymentBucket {
    Write-Info "Creating deployment S3 bucket: $S3Bucket"

    $checkResult = aws s3api head-bucket --bucket "$S3Bucket" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Warn "Bucket $S3Bucket already exists"
        return
    }

    Write-Info "Deployment bucket does not exist or is inaccessible; attempting creation..."
    $createResult = aws s3 mb "s3://$S3Bucket" --region "$AWSRegion" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create deployment bucket ${S3Bucket}: ${createResult}"
        return
    }

    $versionResult = aws s3api put-bucket-versioning --bucket "$S3Bucket" --versioning-configuration Status=Enabled 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Bucket created, but versioning failed: $versionResult"
    }
    Write-Info "Deployment bucket created successfully"
}

function Build-LambdaPackages {
    Write-Info "Building Lambda zip packages..."

    $lambdaFiles = @(
        "email_parser",
        "classify_intent",
        "retrieve_knowledge",
        "crm_validation",
        "generate_response",
        "email_sender",
        "save_result",
        "gmail_imap_poller"
    )

    foreach ($fileName in $lambdaFiles) {
        $sourcePath = Join-Path $PSScriptRoot "..\backend\lambda-functions\$fileName.py"
        $zipPath = Join-Path $PSScriptRoot "..\backend\lambda-functions\$fileName.zip"

        if (-not (Test-Path $sourcePath)) {
            Write-Error "Lambda source file not found: $sourcePath"
            continue
        }

        try {
            if (Test-Path $zipPath) {
                Remove-Item $zipPath -Force -ErrorAction Stop
            }
            Compress-Archive -Path $sourcePath -DestinationPath $zipPath -Force -ErrorAction Stop
            Write-Info "Built package: $zipPath"
        }
        catch {
            Write-Error "Failed to build Lambda package for ${fileName}: $_"
        }
    }
}

# Deploy Lambda functions
function Update-LambdaFunctions {
    Write-Info "Deploying Lambda functions..."

    $lambdaFunctions = @(
        "email_parser:insuremail-email-parser",
        "classify_intent:insuremail-classify-intent",
        "retrieve_knowledge:insuremail-retrieve-knowledge",
        "crm_validation:insuremail-crm-validation",
        "generate_response:insuremail-generate-response",
        "email_sender:insuremail-email-sender",
        "save_result:insuremail-save-result",
        "gmail_imap_poller:insuremail-gmail-imap-poller"
    )

    foreach ($func in $lambdaFunctions) {
        $parts = $func -split ":"
        $fileName = $parts[0]
        $funcName = $parts[1]

        Write-Info "Deploying $funcName..."

        $zipFilePath = Join-Path $PSScriptRoot "..\backend\lambda-functions\$fileName.zip"
        if (-not (Test-Path $zipFilePath)) {
            Write-Error "Zip file for $funcName not found: $zipFilePath"
            continue
        }

        # Check if function exists
        try {
            aws lambda get-function --function-name "$funcName" --region "$AWSRegion" >$null 2>&1
            $updateResult = aws lambda update-function-code --function-name "$funcName" --zip-file "fileb://$zipFilePath" --region "$AWSRegion" 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Info "Updated $funcName"
            }
            else {
                Write-Error "Failed to update ${funcName}: ${updateResult}"
            }
        }
        catch {
            Write-Warn "Function $funcName does not exist. Please create it first."
        }
    }
}

# Deploy API Gateway
function New-ApiGateway {
    Write-Info "Deploying API Gateway..."

    $apiName = "insuremail-api"

    # Check if API exists
    try {
        $apiId = aws apigateway get-rest-apis --region "$AWSRegion" --query "items[?name=='$apiName'].id" --output text 2>$null
    }
    catch {
        Write-Warn "API Gateway access denied. Skipping API Gateway deployment."
        Write-Warn "Please ensure your IAM user has API Gateway permissions."
        return
    }

    if ([string]::IsNullOrEmpty($apiId) -or $apiId -eq "None") {
        Write-Info "Creating new API Gateway: $apiName"

        # Create REST API
        try {
            $apiId = aws apigateway create-rest-api --name "$apiName" --region "$AWSRegion" --query 'id' --output text 2>$null
            Write-Info "Created API with ID: $apiId"
        }
        catch {
            Write-Warn "Failed to create API Gateway. Check IAM permissions."
            return
        }
    }
    else {
        Write-Info "Using existing API: $apiId"
    }

    # Get root resource ID
    try {
        $rootResourceId = aws apigateway get-resources --rest-api-id "$apiId" --region "$AWSRegion" --query 'items[?path==`/`].id' --output text 2>$null
    }
    catch {
        Write-Warn "Failed to get API Gateway resources."
    }

    Write-Info "API Gateway deployment complete"
    if ($apiId -and $apiId -ne "None") {
        Write-Info "API Endpoint: https://$apiId.execute-api.$AWSRegion.amazonaws.com/prod"
    }
}

# Deploy Step Functions
function New-StepFunctions {
    Write-Info "Deploying Step Functions..."

    $stateMachineName = "insuremail-email-processor"

    # Read workflow definition
    $workflowDefinition = Get-Content "../backend/step-functions/email_processing_workflow.json" -Raw
    $workflowDefinition = $workflowDefinition.TrimStart([char]0xFEFF)

    # Check if state machine exists
    $listResult = aws stepfunctions list-state-machines --region "$AWSRegion" --query "stateMachines[?name=='$stateMachineName'].stateMachineArn" --output text 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Failed to list Step Functions state machines: $listResult"
        Write-Warn "Please ensure your IAM user has states:ListStateMachines permission."
        return
    }

    if ($listResult -eq $null) {
        $listResult = ""
    }
    elseif ($listResult -is [array]) {
        $listResult = $listResult -join "`n"
    }

    $stateMachineArn = $listResult.Trim()

    $accountId = aws sts get-caller-identity --query Account --output text 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to get AWS account ID: $accountId"
        return
    }
    $accountId = $accountId.Trim()
    $roleArn = "arn:aws:iam::${accountId}:role/machine-learning-role"

    if ([string]::IsNullOrEmpty($stateMachineArn) -or $stateMachineArn -eq "None") {
        Write-Info "Creating new state machine: $stateMachineName"

        # Create state machine - use a temporary file for the definition
        $tempFile = [System.IO.Path]::GetTempFileName()
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($tempFile, $workflowDefinition, $utf8NoBom)

        $createResult = aws stepfunctions create-state-machine --name "$stateMachineName" --definition "file://$tempFile" --role-arn "$roleArn" --region "$AWSRegion" --query 'stateMachineArn' --output text 2>&1
        if ($LASTEXITCODE -eq 0) {
            $stateMachineArn = $createResult.Trim()
            Write-Info "Created state machine: $stateMachineArn"
        }
        else {
            Write-Error "Failed to create state machine: $createResult"
            Write-Warn "Check that role $roleArn exists and your user has states:CreateStateMachine permission."
        }

        Remove-Item $tempFile -ErrorAction SilentlyContinue
    }
    else {
        Write-Info "Updating existing state machine: $stateMachineArn"

        # Update state machine - use a temporary file for the definition
        $tempFile = [System.IO.Path]::GetTempFileName()
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($tempFile, $workflowDefinition, $utf8NoBom)

        $updateResult = aws stepfunctions update-state-machine --state-machine-arn "$stateMachineArn" --definition "file://$tempFile" --region "$AWSRegion" --output text 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Info "Updated state machine: $stateMachineArn"
        }
        else {
            Write-Error "Failed to update state machine: $updateResult"
        }

        Remove-Item $tempFile -ErrorAction SilentlyContinue
    }

    Write-Info "Step Functions deployment complete"
}

# Create DynamoDB tables
function New-DynamoDBTables {
    Write-Info "Creating DynamoDB tables..."

    $tables = @(
        "InsureMail-Emails:email_id",
        "InsureMail-Customers:member_id",
        "InsureMail-Knowledge:doc_id"
    )

    foreach ($table in $tables) {
        $parts = $table -split ":"
        $tableName = $parts[0]
        $keyName = $parts[1]

        Write-Info "Creating table: $tableName..."
        
        $result = aws dynamodb create-table --table-name "$tableName" --attribute-definitions AttributeName="$keyName",AttributeType=S --key-schema AttributeName="$keyName",KeyType=HASH --billing-mode PAY_PER_REQUEST --region "$AWSRegion" 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Info "Created table: $tableName"
        } else {
            if ($result -match "ResourceInUseException") {
                Write-Warn "Table $tableName already exists"
            } else {
                Write-Error "Failed to create table: $tableName - $result"
            }
        }
    }
}

# Create S3 buckets
function New-S3Buckets {
    Write-Info "Creating S3 buckets..."

    $buckets = @(
        "insuremail-incoming",
        "insuremail-attachments",
        "insuremail-models",
        "insuremail-audit"
    )

    $accountId = aws sts get-caller-identity --query Account --output text

    foreach ($bucket in $buckets) {
        $bucketName = "$bucket-$accountId"

        Write-Info "Creating bucket: $bucketName..."
        
        $result = aws s3 mb "s3://$bucketName" --region "$AWSRegion" 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-Info "Created bucket: $bucketName"
            
            # Enable versioning
            aws s3api put-bucket-versioning --bucket "$bucketName" --versioning-configuration Status=Enabled
            Write-Info "Versioning enabled for: $bucketName"
        } else {
            if ($result -match "BucketAlreadyExists" -or $result -match "BucketAlreadyOwnedByYou") {
                Write-Warn "Bucket $bucketName already exists"
            } else {
                Write-Error "Failed to create bucket: $bucketName - $result"
            }
        }
    }
}

# Deploy frontend
function New-Frontend {
    Write-Info "Deploying frontend..."

    $accountId = aws sts get-caller-identity --query Account --output text
    $frontendBucket = "insuremail-dashboard-$accountId"

    $headResult = aws s3api head-bucket --bucket "$frontendBucket" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Info "Frontend bucket exists: $frontendBucket"
    }
    else {
        Write-Info "Frontend bucket does not exist; creating: $frontendBucket"
        $createResult = aws s3 mb "s3://$frontendBucket" --region "$AWSRegion" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to create frontend bucket ${frontendBucket}: ${createResult}"
            return
        }

        Write-Info "Configuring public website hosting for $frontendBucket"
        aws s3api put-public-access-block --bucket "$frontendBucket" --public-access-block-configuration BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false >$null 2>&1

        $websiteResult = aws s3 website "s3://$frontendBucket" --index-document index.html --error-document index.html 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Failed to configure website for ${frontendBucket}: ${websiteResult}"
        }
        else {
            Write-Info "Configured website hosting for $frontendBucket"
        }
    }

    # Ensure the frontend bucket policy allows public object reads
    $bucketPolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::$frontendBucket/*"
    }
  ]
}
"@
    aws s3api put-bucket-policy --bucket "$frontendBucket" --policy $bucketPolicy >$null 2>&1

    # Build frontend
    Push-Location "../frontend/dashboard"
    npm install
    npm run build
    Pop-Location

    # Upload to S3
    $syncResult = aws s3 sync "../frontend/dashboard/dist" "s3://$frontendBucket" --delete 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to sync frontend to ${frontendBucket}: ${syncResult}"
        return
    }

    Write-Info "Frontend deployed to: http://$frontendBucket.s3-website-$AWSRegion.amazonaws.com"
}

# Print deployment summary
function Write-Summary {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor $White
    Write-Host "Deployment Summary" -ForegroundColor $White
    Write-Host "==========================================" -ForegroundColor $White
    Write-Host "Region: $AWSRegion" -ForegroundColor $White
    Write-Host "Stack: $StackName" -ForegroundColor $White
    Write-Host "" -ForegroundColor $White
    Write-Host "Resources Created:" -ForegroundColor $White
    Write-Host "  - Lambda Functions: 8" -ForegroundColor $White
    Write-Host "  - DynamoDB Tables: 3" -ForegroundColor $White
    Write-Host "  - S3 Buckets: 5" -ForegroundColor $White
    Write-Host "  - Step Functions: 1" -ForegroundColor $White
    Write-Host "  - API Gateway: 1" -ForegroundColor $White
    Write-Host "" -ForegroundColor $White
    Write-Host "Next Steps:" -ForegroundColor $White
    Write-Host "  1. Configure Gmail IMAP credentials" -ForegroundColor $White
    Write-Host "  2. Verify SES email address" -ForegroundColor $White
    Write-Host "  3. Train and upload ML models" -ForegroundColor $White
    Write-Host "  4. Upload knowledge base documents" -ForegroundColor $White
    Write-Host "  5. Test the workflow" -ForegroundColor $White
    Write-Host "==========================================" -ForegroundColor $White
}

# Main deployment flow
function Main {
    Check-Prerequisites
    New-DeploymentBucket
    New-S3Buckets
    New-DynamoDBTables
    Build-LambdaPackages
    Update-LambdaFunctions
    New-StepFunctions
    New-ApiGateway
    New-Frontend
    Write-Summary
}

# Run main function
Main