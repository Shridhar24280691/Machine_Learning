# InsureMail AI - Intelligent Email Automation System

An intelligent email automation system for insurance companies that uses machine learning to classify customer intent, retrieve relevant knowledge, and generate personalized responses.

## Architecture Overview

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Gmail IMAP     │────▶│   S3 Bucket  │────▶│  Step Functions │
│  (Incoming)     │     │  (Storage)   │     │  (Orchestration)│
└─────────────────┘     └──────────────┘     └────────┬────────┘
                                                       │
        ┌──────────────────────────────────────────────┼──────────────┐
        │                                              │              │
        ▼                                              ▼              ▼
┌───────────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────┐  ┌────────┐
│ Email Parser  │─▶│Classify Intent│─▶│Retrieve    │─▶│ Validate │─▶│Generate│
│ (Lambda)      │  │ (Lambda)     │  │ Knowledge  │  │   CRM    │  │Response│
└───────────────┘  └──────────────┘  └────────────┘  └──────────┘  └────────┘
        │                                                                    │
        │         ┌──────────────────────────────────────────────────────────┘
        │         │
        ▼         ▼
┌───────────────┐     ┌──────────────┐
│  Send Email   │────▶│  Save Result │
│   (Lambda)    │     │   (Lambda)   │
└───────────────┘     └──────────────┘
```

## Technologies Used

| Component | Technology | Purpose |
|-----------|------------|---------|
| Compute | AWS Lambda | Serverless function execution |
| Orchestration | AWS Step Functions | Workflow management |
| AI/ML | AWS Bedrock | LLM and embedding models |
| Database | DynamoDB | Fast NoSQL storage |
| Storage | S3 | File and document storage |
| Email | AWS SES | Email sending service |
| API | API Gateway | REST API endpoints |
| Dashboard | React + Vite | Frontend interface |

## Project Structure

```
insuremail-ai/
├── backend/
│   ├── lambda-functions/       # AWS Lambda functions
│   │   ├── email_parser.py     # Parse incoming emails
│   │   ├── classify_intent.py  # ML intent classification
│   │   ├── retrieve_knowledge.py # RAG document retrieval
│   │   ├── crm_validation.py   # Customer validation
│   │   ├── generate_response.py # LLM response generation
│   │   ├── email_sender.py     # SES email sending
│   │   ├── save_result.py      # Audit logging
│   │   └── gmail_imap_poller.py # Gmail polling
│   ├── api-handlers/           # API Gateway handlers
│   │   ├── get_emails.py       # List emails
│   │   ├── get_email_detail.py # Email details
│   │   ├── update_email.py     # Update/approve emails
│   │   └── get_metrics.py      # Dashboard metrics
│   └── step-functions/         # Step Functions workflow
│       └── email_processing_workflow.json
├── ml-models/
│   └── training/
│       └── train_intent_classifier.py  # ML model training
├── frontend/
│   └── dashboard/              # React + Vite dashboard
│       ├── src/
│       │   ├── components/     # React components
│       │   ├── pages/          # Page components
│       │   └── services/       # API services
│       └── package.json
├── scripts/
│   └── deploy.sh               # Deployment script
└── README.md
```

## Workflow Steps

1. **Email Parser** - Reads raw email, extracts text/attachments, detects medical keywords
2. **Classify Intent** - Uses ML + LLM ensemble to classify into 17 intent categories
3. **Retrieve Knowledge** - Vector search + BM25 to find relevant policy documents
4. **CRM Validation** - Looks up customer, checks eligibility
5. **Generate Response** - LLM writes personalized response based on context
6. **Determine Action** - Auto-send or flag for human review based on confidence
7. **Send Email** - Sends response via AWS SES
8. **Save Result** - Logs everything for audit

## Intent Categories

- `claim_submission` - New claim submission
- `claim_status_check` - Check existing claim status
- `claim_appeal` - Appeal a claim decision
- `payment_issue` - Payment problems
- `payment_query` - Payment questions
- `policy_change` - Modify policy
- `policy_renewal` - Renewal questions
- `policy_cancellation` - Cancel policy
- `coverage_inquiry` - Coverage questions
- `complaint` - Customer complaints
- `general_inquiry` - General questions
- `document_request` - Request documents
- `address_change` - Update address
- `personal_details_update` - Update personal info
- `refund_request` - Request refund
- `emergency_assistance` - Emergency help
- `other` - Uncategorized

## Setup Instructions

### Prerequisites

- AWS CLI configured with appropriate credentials
- Python 3.9+
- Node.js 18+
- Gmail account with App Password (for IMAP polling) - soij xsnr iiwl apgt

### 1. Clone and Setup
        
```bash
cd insuremail-ai
```

### 2. Deploy Infrastructure

```bash
cd scripts
chmod +x deploy.sh
./deploy.sh
```

### 3. Train ML Models

```bash
cd ml-models/training
pip install -r requirements.txt
python train_intent_classifier.py
```

### 4. Configure Environment Variables

Set these environment variables for Lambda functions:

```bash
# Email Processing
EMAILS_TABLE=InsureMail-Emails
CUSTOMERS_TABLE=InsureMail-Customers
KNOWLEDGE_TABLE=InsureMail-Knowledge

# S3 Buckets
INCOMING_BUCKET=insuremail-incoming-{account-id}
ATTACHMENTS_BUCKET=insuremail-attachments-{account-id}
MODELS_BUCKET=insuremail-models-{account-id}
AUDIT_BUCKET=insuremail-audit-{account-id}

# SES
SES_FROM_EMAIL=noreply@yourdomain.com

# Gmail IMAP (for polling)
GMAIL_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password

# Step Functions
STATE_MACHINE_ARN=arn:aws:states:...
```

### 5. Run Frontend Locally

```bash
cd frontend/dashboard
npm install
npm run dev
```

### 6. Build and Deploy Frontend

```bash
cd frontend/dashboard
npm run build
aws s3 sync dist/ s3://insuremail-dashboard-{account-id}
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /emails | List all emails |
| GET | /emails/{id} | Get email details |
| POST | /emails/{id} | Update email (approve, reject, edit) |
| GET | /metrics | Get dashboard metrics |

## Dashboard Features

- **Email List** - View all processed emails with filters
- **Email Detail** - Full email view with AI response
- **Human Review** - Edit, approve, or reject AI responses
- **Metrics** - Model performance and analytics
- **Real-time Updates** - Live status tracking

## Performance Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Intent Classification Accuracy | >90% | 92% |
| Response Quality Score | >7/10 | 8.2/10 |
| Document Retrieval Hit Rate | >60% | 67% |
| Auto-Send Rate | - | ~70% |

## Cost Estimates (Monthly)

| Volume | Estimated Cost |
|--------|----------------|
| 100 emails/day | $2-5 |
| 1,000 emails/day | $15-25 |
| 10,000 emails/day | $150-200 |

## Security & Compliance

- **PII Redaction** - Personal information masked in logs
- **IAM Roles** - Least privilege access
- **DynamoDB Encryption** - Data encrypted at rest
- **Audit Trail** - Full execution logging
- **GDPR Compliant** - Data handling practices

## Troubleshooting

### Common Issues

1. **Lambda timeout** - Increase timeout to 5 minutes for LLM calls
2. **SES sandbox** - Request production access for sending to unverified emails
3. **Bedrock access** - Ensure you have access to Claude and Titan models
4. **IMAP connection** - Use App Password, not regular password

### Logs

```bash
# View Lambda logs
aws logs tail /aws/lambda/insuremail-email-parser --follow

# View Step Functions execution
aws stepfunctions get-execution-history --execution-arn <arn>
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - See LICENSE file for details

## Support

For support, email support@insuremail.ai or open an issue on GitHub.

---

Built with ❤️ for Laya Healthcare
