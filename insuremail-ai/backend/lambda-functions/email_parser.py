"""
Email Parser Lambda Function
Reads raw email from Gmail/SES, extracts text, attachments, and metadata
"""
import json
import boto3
import email
import re
import os
from datetime import datetime
from email.header import decode_header
import hashlib

# AWS Clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime')
textract = boto3.client('textract')

# Configuration
EMAILS_TABLE = os.environ.get('EMAILS_TABLE', 'InsureMail-Emails')
ATTACHMENTS_BUCKET = os.environ.get('ATTACHMENTS_BUCKET', 'insuremail-attachments-227855914226')

def lambda_handler(event, context):
    """
    Main Lambda handler for email parsing
    
    Expected event format:
    {
        "s3_bucket": "incoming-emails-bucket",
        "s3_key": "emails/email_123.eml",
        "email_id": "unique-email-id"
    }
    """
    try:
        print(f"Processing email: {event}")
        
        s3_bucket = event.get('s3_bucket')
        s3_key = event.get('s3_key')
        email_id = event.get('email_id')
        
        # Download email from S3
        email_obj = s3.get_object(Bucket=s3_bucket, Key=s3_key)
        email_body = email_obj['Body'].read()
        
        # Parse email
        parsed_email = parse_email(email_body, email_id)
        
        # Extract text from attachments if any
        attachments_data = process_attachments(parsed_email.get('attachments', []), email_id)
        parsed_email['attachments_data'] = attachments_data
        
        # Extract specific fields using Bedrock
        extracted_fields = extract_fields_with_llm(parsed_email)
        parsed_email['extracted_fields'] = extracted_fields
        
        # Redact PII
        parsed_email = redact_pii(parsed_email)
        
        # Save to DynamoDB
        save_to_dynamodb(parsed_email)
        
        return {
            'statusCode': 200,
            'email_id': email_id,
            'parsed_data': parsed_email,
            'next_step': 'classify_intent'
        }
        
    except Exception as e:
        print(f"Error processing email: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e),
            'email_id': event.get('email_id')
        }

def parse_email(email_body, email_id):
    """Parse RFC 2822 email format"""
    msg = email.message_from_bytes(email_body)
    
    # Extract headers
    subject = decode_header_value(msg.get('Subject', ''))
    sender = decode_header_value(msg.get('From', ''))
    receiver = decode_header_value(msg.get('To', ''))
    date = msg.get('Date', '')
    message_id = msg.get('Message-ID', email_id)
    
    # Extract body and attachments
    body_text = ""
    body_html = ""
    attachments = []
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get('Content-Disposition', ''))
            
            if 'attachment' in content_disposition:
                # Handle attachment
                filename = part.get_filename()
                if filename:
                    attachment_data = {
                        'filename': filename,
                        'content_type': content_type,
                        'content': part.get_payload(decode=True)
                    }
                    attachments.append(attachment_data)
            elif content_type == 'text/plain':
                payload = part.get_payload(decode=True)
                if payload:
                    body_text = payload.decode('utf-8', errors='ignore')
            elif content_type == 'text/html':
                payload = part.get_payload(decode=True)
                if payload:
                    body_html = payload.decode('utf-8', errors='ignore')
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            if content_type == 'text/plain':
                body_text = payload.decode('utf-8', errors='ignore')
            elif content_type == 'text/html':
                body_html = payload.decode('utf-8', errors='ignore')
    
    # Detect medical keywords
    medical_keywords = detect_medical_keywords(body_text + body_html)
    
    return {
        'email_id': email_id,
        'message_id': message_id,
        'subject': subject,
        'sender': sender,
        'receiver': receiver,
        'date': date,
        'body_text': body_text,
        'body_html': body_html,
        'attachments': attachments,
        'medical_keywords_detected': medical_keywords,
        'timestamp': datetime.utcnow().isoformat(),
        'status': 'parsed'
    }

def decode_header_value(header_value):
    """Decode email header value"""
    if not header_value:
        return ""
    decoded_parts = decode_header(header_value)
    result = ""
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result += part.decode(charset or 'utf-8', errors='ignore')
        else:
            result += part
    return result

def detect_medical_keywords(text):
    """Detect medical/insurance related keywords"""
    keywords = [
        'hospital', 'doctor', 'diagnosis', 'treatment', 'surgery', 'medical',
        'claim', 'policy', 'coverage', 'insurance', 'injury', 'accident',
        'prescription', 'medication', 'therapy', 'consultation', 'emergency',
        'inpatient', 'outpatient', 'specialist', 'referral', 'gp', 'dentist',
        'optical', 'maternity', 'mental health', 'physiotherapy'
    ]
    
    text_lower = (text or '').lower()
    detected = [kw for kw in keywords if kw in text_lower]
    return detected

def process_attachments(attachments, email_id):
    """Process attachments - extract text from PDFs using Textract"""
    attachments_data = []
    
    for idx, attachment in enumerate(attachments):
        filename = attachment['filename']
        content = attachment['content']
        content_type = attachment['content_type']
        
        attachment_id = f"{email_id}_att_{idx}"
        
        # Save to S3
        s3_key = f"attachments/{email_id}/{filename}"
        s3.put_object(
            Bucket=ATTACHMENTS_BUCKET,
            Key=s3_key,
            Body=content
        )
        
        extracted_text = ""
        
        # Extract text from PDF using Textract
        if 'pdf' in content_type.lower():
            try:
                response = textract.detect_document_text(Document={'Bytes': content})
                extracted_text = ' '.join([
                    block['Text'] for block in response['Blocks'] 
                    if block['BlockType'] == 'LINE'
                ])
            except Exception as e:
                print(f"Textract error for {filename}: {str(e)}")
        
        attachments_data.append({
            'attachment_id': attachment_id,
            'filename': filename,
            's3_key': s3_key,
            'content_type': content_type,
            'extracted_text': extracted_text[:5000]  # Limit text size
        })
    
    return attachments_data

def extract_fields_with_llm(parsed_email):
    """Use Bedrock to extract specific fields like policy number, member ID"""
    
    prompt = f"""You are an intelligent email parser for an insurance company. Extract the following fields from the email:

Email Subject: {parsed_email['subject']}
Email Body: {parsed_email['body_text'][:3000]}

Extract these fields (return as JSON):
- policy_number: Insurance policy number if mentioned
- member_id: Member ID if mentioned
- claim_number: Claim number if mentioned
- customer_name: Customer's full name
- phone_number: Phone number if mentioned
- date_of_birth: Date of birth if mentioned
- request_type: Brief description of what customer is asking for
- urgency: High/Medium/Low based on content

Return ONLY valid JSON with these exact keys. Use null if not found."""

    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-haiku-20240307-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 500,
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
        
        result = json.loads(response['body'].read())
        extracted = ''
        if isinstance(result.get('content'), list) and len(result['content']) > 0:
            extracted = result['content'][0].get('text', '')
        
        # Parse JSON from response
        if not extracted:
            return {}
        json_match = re.search(r'\{.*\}', extracted, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        
        return {}
        
    except Exception as e:
        print(f"LLM extraction error: {str(e)}")
        return {}

def redact_pii(parsed_email):
    """Redact personally identifiable information"""
    
    # Patterns for PII
    patterns = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'credit_card': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'
    }
    
    text = parsed_email.get('body_text', '')
    
    for pii_type, pattern in patterns.items():
        text = re.sub(pattern, f'[REDACTED_{pii_type.upper()}]', text)
    
    parsed_email['body_text_redacted'] = text
    parsed_email['pii_redacted'] = True
    
    return parsed_email

def save_to_dynamodb(parsed_email):
    """Save parsed email to DynamoDB"""
    table = dynamodb.Table(EMAILS_TABLE)
    
    # Prepare item for DynamoDB
    item = {
        'email_id': parsed_email['email_id'],
        'message_id': parsed_email.get('message_id', ''),
        'subject': parsed_email.get('subject', ''),
        'sender': parsed_email.get('sender', ''),
        'receiver': parsed_email.get('receiver', ''),
        'date': parsed_email.get('date', ''),
        'body_text': parsed_email.get('body_text', '')[:4000],  # Truncate for storage
        'medical_keywords': parsed_email.get('medical_keywords_detected', []),
        'extracted_fields': parsed_email.get('extracted_fields', {}),
        'attachments_count': len(parsed_email.get('attachments', [])),
        'timestamp': parsed_email.get('timestamp', ''),
        'status': 'parsed'
    }
    
    table.put_item(Item=item)
    print(f"Saved email {parsed_email['email_id']} to DynamoDB")
