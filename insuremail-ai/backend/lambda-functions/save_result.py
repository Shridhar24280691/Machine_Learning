"""
Save Result Lambda Function
Saves final execution results for audit and analytics
"""
import json
import boto3
import os
from datetime import datetime

# AWS Clients
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

# Configuration
EMAILS_TABLE = os.environ.get('EMAILS_TABLE', 'InsureMail-Emails')
AUDIT_BUCKET = os.environ.get('AUDIT_BUCKET', 'insuremail-audit-227855914226')  # Updated default with account ID

def lambda_handler(event, context):
    """
    Save final execution results
    
    Expected event format:
    {
        "email_id": "unique-email-id",
        "execution_trace": { ... full pipeline trace ... }
    }
    """
    try:
        print(f"Saving result for: {event}")
        
        email_id = event.get('email_id')
        execution_trace = event.get('execution_trace', {})
        
        # Get final email record
        email_record = get_email_record(email_id)
        
        # Build audit record
        audit_record = {
            'email_id': email_id,
            'timestamp': datetime.utcnow().isoformat(),
            'execution_trace': execution_trace,
            'final_status': email_record.get('status', 'unknown'),
            'classification': email_record.get('classification', {}),
            'action_taken': email_record.get('action_decision', {}),
            'send_result': email_record.get('send_result', {}),
            'model_versions': {
                'intent_classifier': 'v1.0',
                'llm_model': 'claude-3-haiku',
                'embedding_model': 'titan-embed-v2'
            }
        }
        
        # Save to S3 for long-term audit
        save_audit_to_s3(audit_record)
        
        # Update final status in DynamoDB
        update_final_status(email_id, audit_record)
        
        return {
            'statusCode': 200,
            'email_id': email_id,
            'message': 'Execution result saved successfully',
            'final_status': audit_record['final_status']
        }
        
    except Exception as e:
        print(f"Save result error: {str(e)}")
        return {
            'statusCode': 500,
            'email_id': event.get('email_id'),
            'error': str(e)
        }

def get_email_record(email_id):
    """Get email record from DynamoDB"""
    if not email_id or not isinstance(email_id, str):
        print(f"Invalid email_id: {email_id}")
        return {}
    
    table = dynamodb.Table(EMAILS_TABLE)
    
    try:
        response = table.get_item(Key={'email_id': email_id})
        return response.get('Item', {})
    except Exception as e:
        print(f"Error getting email record: {str(e)}")
        return {}

def save_audit_to_s3(audit_record):
    """Save audit record to S3"""
    
    email_id = audit_record['email_id']
    timestamp = audit_record['timestamp']
    
    # Build S3 key with date partitioning
    date_prefix = datetime.utcnow().strftime('%Y/%m/%d')
    s3_key = f"audit/{date_prefix}/{email_id}.json"
    
    try:
        s3.put_object(
            Bucket=AUDIT_BUCKET,
            Key=s3_key,
            Body=json.dumps(audit_record, indent=2, default=str),
            ContentType='application/json'
        )
        print(f"Audit saved to S3: {s3_key}")
        
    except Exception as e:
        print(f"Error saving audit to S3: {str(e)}")

def update_final_status(email_id, audit_record):
    """Update final status in DynamoDB"""
    if not email_id or not isinstance(email_id, str):
        print(f"Invalid email_id for update: {email_id}")
        return
    
    table = dynamodb.Table(EMAILS_TABLE)
    
    table.update_item(
        Key={'email_id': email_id},
        UpdateExpression='SET audit_record = :a, #status = :s, completed_at = :t',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':a': {
                'audit_s3_key': f"audit/{datetime.utcnow().strftime('%Y/%m/%d')}/{email_id}.json",
                'model_versions': audit_record['model_versions'],
                'final_status': audit_record['final_status']
            },
            ':s': 'completed',
            ':t': datetime.utcnow().isoformat()
        }
    )
