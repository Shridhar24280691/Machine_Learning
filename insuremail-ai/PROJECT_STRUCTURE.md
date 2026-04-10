# InsureMail AI - Project Structure

## Complete File Listing

```
insuremail-ai/
├── README.md                          # Main project documentation
├── PROJECT_STRUCTURE.md               # This file
│
├── backend/
│   ├── lambda-functions/              # AWS Lambda Functions (10 functions)
│   │   ├── email_parser.py            # Parse incoming emails from S3
│   │   ├── classify_intent.py         # ML + LLM intent classification
│   │   ├── retrieve_knowledge.py      # RAG document retrieval
│   │   ├── crm_validation.py          # Customer lookup & validation
│   │   ├── generate_response.py       # LLM response generation
│   │   ├── email_sender.py            # SES email sending
│   │   ├── save_result.py             # Audit logging
│   │   ├── gmail_imap_poller.py       # Gmail IMAP polling
│   │   ├── error_handler.py           # Error handling
│   │   ├── flag_for_review.py         # Human review flagging
│   │   ├── rag_ingestion.py           # Document ingestion
│   │   └── requirements.txt           # Python dependencies
│   │
│   ├── api-handlers/                  # API Gateway Lambda handlers (4 handlers)
│   │   ├── get_emails.py              # GET /emails - List emails
│   │   ├── get_email_detail.py        # GET /emails/{id} - Email details
│   │   ├── update_email.py            # POST /emails/{id} - Update email
│   │   └── get_metrics.py             # GET /metrics - Dashboard metrics
│   │
│   └── step-functions/                # Step Functions
│       └── email_processing_workflow.json  # Main workflow definition
│
├── ml-models/
│   └── training/                      # ML Model Training
│       ├── train_intent_classifier.py # Scikit-learn classifier training
│       └── requirements.txt           # Training dependencies
│
├── frontend/
│   └── dashboard/                     # React + Vite Dashboard
│       ├── package.json               # NPM dependencies
│       ├── vite.config.js             # Vite configuration
│       ├── tailwind.config.js         # Tailwind CSS config
│       ├── postcss.config.js          # PostCSS config
│       ├── index.html                 # HTML entry point
│       ├── .env.example               # Environment variables template
│       └── src/
│           ├── main.jsx               # React entry point
│           ├── App.jsx                # Main app component
│           ├── index.css              # Global styles
│           ├── components/
│           │   └── Layout.jsx         # Dashboard layout
│           ├── pages/
│           │   ├── Dashboard.jsx      # Main dashboard
│           │   ├── EmailList.jsx      # Email list view
│           │   ├── EmailDetail.jsx    # Email detail view
│           │   └── Metrics.jsx        # Analytics page
│           └── services/
│               └── api.js             # API service layer
│
└── scripts/
    └── deploy.sh                      # AWS deployment script
```

## Lambda Functions (12 total)

### Core Processing Functions (8)
1. **email_parser** - Parses RFC 2822 emails, extracts text/PDFs, detects medical keywords
2. **classify_intent** - Ensemble ML + LLM classification into 17 intent categories
3. **retrieve_knowledge** - Vector search + BM25 + RRF for document retrieval
4. **crm_validation** - Customer lookup and eligibility checking
5. **generate_response** - LLM-powered response generation with quality evaluation
6. **email_sender** - SES email sending with HTML templates
7. **save_result** - Audit logging to S3 and DynamoDB
8. **gmail_imap_poller** - Scheduled Gmail inbox polling

### Supporting Functions (4)
9. **error_handler** - Graceful error handling and alerting
10. **flag_for_review** - Human review flagging and notifications
11. **rag_ingestion** - Document chunking and embedding generation

### API Handlers (4)
12. **get_emails** - List emails with filtering
13. **get_email_detail** - Get single email details
14. **update_email** - Edit, approve, reject emails
15. **get_metrics** - Dashboard analytics

## Technologies Stack

### Backend
- **AWS Lambda** - Serverless compute
- **AWS Step Functions** - Workflow orchestration
- **AWS Bedrock** - LLM (Claude 3 Haiku) and Embeddings (Titan)
- **Amazon Textract** - PDF OCR
- **DynamoDB** - NoSQL database
- **S3** - Object storage
- **SES** - Email service
- **API Gateway** - REST API

### Machine Learning
- **scikit-learn** - Traditional classification (Random Forest, Logistic Regression)
- **TF-IDF** - Text vectorization
- **Ensemble Methods** - ML + LLM voting

### Frontend
- **React 18** - UI framework
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **Recharts** - Charts and visualizations
- **Lucide React** - Icons
- **date-fns** - Date formatting

## Data Flow

```
Customer Email
    ↓
Gmail IMAP Poller (scheduled)
    ↓
S3 Bucket (incoming-emails)
    ↓
Step Functions Execution
    ↓
├─→ Email Parser
├─→ Classify Intent (ML + LLM)
├─→ Retrieve Knowledge (RAG)
├─→ CRM Validation
├─→ Generate Response (LLM)
├─→ Determine Action
│   ├─ High Confidence → Send Email
│   └─ Low Confidence → Flag for Review
└─→ Save Result
    ↓
Dashboard (React)
```

## Intent Categories (17)

| Category | Description |
|----------|-------------|
| claim_submission | New claim submission |
| claim_status_check | Check existing claim |
| claim_appeal | Appeal claim decision |
| payment_issue | Payment problems |
| payment_query | Payment questions |
| policy_change | Modify policy |
| policy_renewal | Renewal questions |
| policy_cancellation | Cancel policy |
| coverage_inquiry | Coverage questions |
| complaint | Customer complaints |
| general_inquiry | General questions |
| document_request | Request documents |
| address_change | Update address |
| personal_details_update | Update personal info |
| refund_request | Request refund |
| emergency_assistance | Emergency help |
| other | Uncategorized |

## DynamoDB Tables

| Table | Primary Key | Purpose |
|-------|-------------|---------|
| InsureMail-Emails | email_id | Store processed emails |
| InsureMail-Customers | member_id | Customer data |
| InsureMail-Knowledge | doc_id | Document chunks + embeddings |

## S3 Buckets

| Bucket | Purpose |
|--------|---------|
| insuremail-incoming | Raw incoming emails |
| insuremail-attachments | Email attachments |
| insuremail-models | ML model artifacts |
| insuremail-audit | Audit logs |
| insuremail-documents | Policy documents |
| insuremail-dashboard | Frontend hosting |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /emails | List emails with filters |
| GET | /emails/{id} | Get email details |
| POST | /emails/{id} | Update/approve/reject |
| GET | /metrics | Get dashboard metrics |

## Environment Variables

### Lambda Functions
```bash
EMAILS_TABLE=InsureMail-Emails
CUSTOMERS_TABLE=InsureMail-Customers
KNOWLEDGE_TABLE=InsureMail-Knowledge
INCOMING_BUCKET=insuremail-incoming-{account}
ATTACHMENTS_BUCKET=insuremail-attachments-{account}
MODELS_BUCKET=insuremail-models-{account}
AUDIT_BUCKET=insuremail-audit-{account}
SES_FROM_EMAIL=noreply@yourdomain.com
SES_CONFIGURATION_SET=InsureMail-Tracking
GMAIL_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password
STATE_MACHINE_ARN=arn:aws:states:...
```

### Frontend
```bash
VITE_API_URL=https://your-api.execute-api.region.amazonaws.com/prod
```

## Deployment

```bash
# Deploy all resources
cd scripts
./deploy.sh

# Train ML models
cd ml-models/training
pip install -r requirements.txt
python train_intent_classifier.py

# Deploy frontend
cd frontend/dashboard
npm install
npm run build
aws s3 sync dist/ s3://insuremail-dashboard-{account}
```

## Performance Targets

| Metric | Target |
|--------|--------|
| Intent Classification Accuracy | >92% |
| Response Quality Score | >8/10 |
| Document Retrieval Hit Rate | >60% |
| Auto-Send Rate | ~70% |
| Processing Time | <30 seconds |

## Cost Estimates

| Volume | Monthly Cost |
|--------|--------------|
| 100 emails/day | $2-5 |
| 1,000 emails/day | $15-25 |
| 10,000 emails/day | $150-200 |
