"""
Flag for Review Lambda Function
Flags emails that need human review
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
REVIEW_TOPIC_ARN = os.environ.get('REVIEW_TOPIC_ARN', '')

def lambda_handler(event, context):
    """
    Flag email for human review
    
    Expected event:
    {
        "email_id": "...",
        "response_data": { ... }
    }
    """
    try:
        print(f"Flagging for review: {event}")
        
        email_id = event.get('email_id')
        response_data = event.get('response_data', {})
        action_decision = response_data.get('action_decision', {})
        
        # Update status in DynamoDB
        flag_in_dynamodb(email_id, action_decision)
        
        # Send notification
        send_review_notification(email_id, action_decision)
        
        return {
            'statusCode': 200,
            'email_id': email_id,
            'flagged': True,
            'reasons': action_decision.get('reasons', [])
        }
        
    except Exception as e:
        print(f"Error flagging for review: {str(e)}")
        return {
            'statusCode': 500,
            'email_id': event.get('email_id'),
            'error': str(e)
        }

def flag_in_dynamodb(email_id, action_decision):
    """Update email status to flagged"""
    table = dynamodb.Table(EMAILS_TABLE)
    
    table.update_item(
        Key={'email_id': email_id},
        UpdateExpression='SET #status = :s, flagged_for_review = :f, review_reasons = :r, flagged_at = :t',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':s': 'flagged',
            ':f': True,
            ':r': action_decision.get('reasons', []),
            ':t': datetime.utcnow().isoformat()
        }
    )
    
    print(f"Email {email_id} flagged for review")

def send_review_notification(email_id, action_decision):
    """Send notification that email needs review"""
    if not REVIEW_TOPIC_ARN:
        return
    
    reasons = action_decision.get('reasons', [])
    
    try:
        sns.publish(
            TopicArn=REVIEW_TOPIC_ARN,
            Subject='InsureMail AI: Email Requires Human Review',
            Message=json.dumps({
                'email_id': email_id,
                'dashboard_url': f'https://dashboard.insuremail.ai/emails/{email_id}',
                'reasons': reasons,
                'timestamp': datetime.utcnow().isoformat()
            }, indent=2)
        )
    except Exception as e:
        print(f"Error sending notification: {str(e)}")
