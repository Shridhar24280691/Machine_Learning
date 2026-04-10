"""
Gmail IMAP Poller Lambda Function
Polls Gmail inbox for new emails and triggers Step Functions
"""
import json
import boto3
import os
import imaplib
import email
import uuid
from datetime import datetime

# AWS Clients
s3 = boto3.client('s3')
stepfunctions = boto3.client('stepfunctions')

# Configuration
INCOMING_BUCKET = os.environ.get('INCOMING_BUCKET', 'insuremail-incoming-227855914226')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN', 'arn:aws:iam::227855914226:role/machine-learning-role')
GMAIL_EMAIL = os.environ.get('GMAIL_EMAIL', 'firebreather1097@gmail.com')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')

def lambda_handler(event, context):
    """
    Poll Gmail inbox for new emails
    
    Triggered by CloudWatch Events (scheduled)
    """
    try:
        print("Starting Gmail IMAP poll...")
        
        # Connect to Gmail IMAP
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        mail.select('inbox')
        
        # Search for unread emails
        status, messages = mail.search(None, 'UNSEEN')
        
        if status != 'OK':
            print("No new messages")
            return {'statusCode': 200, 'processed': 0}
        
        email_ids = messages[0].split()
        print(f"Found {len(email_ids)} new emails")
        
        processed = []
        
        for email_id in email_ids:
            try:
                # Fetch email
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                
                if status != 'OK':
                    continue
                
                raw_email = msg_data[0][1]
                
                # Generate unique ID
                unique_id = str(uuid.uuid4())
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                s3_key = f"emails/{timestamp}_{unique_id}.eml"
                
                # Save to S3
                s3.put_object(
                    Bucket=INCOMING_BUCKET,
                    Key=s3_key,
                    Body=raw_email
                )
                
                print(f"Saved email to S3: {s3_key}")
                
                # Trigger Step Functions
                execution_input = {
                    's3_bucket': INCOMING_BUCKET,
                    's3_key': s3_key,
                    'email_id': unique_id
                }
                
                if STATE_MACHINE_ARN:
                    response = stepfunctions.start_execution(
                        stateMachineArn=STATE_MACHINE_ARN,
                        name=f"email-processing-{unique_id}",
                        input=json.dumps(execution_input)
                    )
                    print(f"Started Step Functions execution: {response['executionArn']}")
                
                processed.append({
                    'email_id': unique_id,
                    's3_key': s3_key,
                    'gmail_id': email_id.decode()
                })
                
                # Mark as read (optional)
                # mail.store(email_id, '+FLAGS', '\\Seen')
                
            except Exception as e:
                print(f"Error processing email {email_id}: {str(e)}")
                continue
        
        # Close connection
        mail.close()
        mail.logout()
        
        return {
            'statusCode': 200,
            'processed': len(processed),
            'emails': processed
        }
        
    except Exception as e:
        print(f"IMAP polling error: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e)
        }
