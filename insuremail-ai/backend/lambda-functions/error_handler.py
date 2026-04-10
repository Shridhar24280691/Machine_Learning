"""
Error Handler Lambda Function
Handles errors gracefully and logs them for debugging
"""
import json
import boto3
import os
from datetime import datetime

# AWS Clients
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

# Configuration
EMAILS_TABLE = os.environ.get('EMAILS_TABLE', 'InsureMail-Emails')
ERROR_TOPIC_ARN = os.environ.get('ERROR_TOPIC_ARN', '')

def lambda_handler(event, context):
    """
    Handle errors from the workflow
    
    Expected event:
    {
        "error_type": "parse_error",
        "email_id": "...",
        "error": "..." (optional)
    }
    """
    try:
        print(f"Handling error: {event}")
        
        error_type = event.get('error_type', 'unknown')
        email_id = event.get('email_id')
        error_message = event.get('error', 'Unknown error')
        
        # Log error to DynamoDB
        log_error(email_id, error_type, error_message)
        
        # Send alert for critical errors
        if error_type in ['send_error', 'generation_error']:
            send_alert(email_id, error_type, error_message)
        
        return {
            'statusCode': 200,
            'email_id': email_id,
            'error_handled': True,
            'error_type': error_type
        }
        
    except Exception as e:
        print(f"Error in error handler: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e)
        }

def log_error(email_id, error_type, error_message):
    """Log error to DynamoDB"""
    table = dynamodb.Table(EMAILS_TABLE)
    
    try:
        table.update_item(
            Key={'email_id': email_id},
            UpdateExpression='SET error = :e, error_type = :et, error_timestamp = :t',
            ExpressionAttributeValues={
                ':e': error_message,
                ':et': error_type,
                ':t': datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        print(f"Error logging to DynamoDB: {str(e)}")

def send_alert(email_id, error_type, error_message):
    """Send SNS alert for critical errors"""
    if not ERROR_TOPIC_ARN:
        return
    
    try:
        sns.publish(
            TopicArn=ERROR_TOPIC_ARN,
            Subject=f'InsureMail AI Error: {error_type}',
            Message=json.dumps({
                'email_id': email_id,
                'error_type': error_type,
                'error_message': error_message,
                'timestamp': datetime.utcnow().isoformat()
            }, indent=2)
        )
    except Exception as e:
        print(f"Error sending alert: {str(e)}")
