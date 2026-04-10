"""
API Handler: Get Email Detail
Returns detailed information about a single email
"""
import json
import boto3
import os
from decimal import Decimal

# AWS Clients
dynamodb = boto3.resource('dynamodb')

# Configuration
EMAILS_TABLE = os.environ.get('EMAILS_TABLE', 'InsureMail-Emails')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """
    GET /emails/{id} - Get single email details
    """
    try:
        # Get email ID from path parameters
        path_params = event.get('pathParameters', {}) or {}
        email_id = path_params.get('id')
        
        if not email_id:
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Email ID is required'})
            }
        
        table = dynamodb.Table(EMAILS_TABLE)
        
        response = table.get_item(Key={'email_id': email_id})
        email = response.get('Item')
        
        if not email:
            return {
                'statusCode': 404,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Email not found'})
            }
        
        # Format detailed response
        detail = {
            'email_id': email.get('email_id'),
            'message_id': email.get('message_id'),
            'subject': email.get('subject'),
            'sender': email.get('sender'),
            'receiver': email.get('receiver'),
            'date': email.get('date'),
            'body_text': email.get('body_text'),
            'medical_keywords': email.get('medical_keywords', []),
            'extracted_fields': email.get('extracted_fields', {}),
            'attachments_count': email.get('attachments_count', 0),
            'classification': email.get('classification', {}),
            'retrieved_documents': email.get('retrieved_documents', []),
            'crm_validation': email.get('crm_validation', {}),
            'generated_response': email.get('generated_response', ''),
            'quality_score': email.get('quality_score', {}),
            'action_decision': email.get('action_decision', {}),
            'send_result': email.get('send_result', {}),
            'status': email.get('status'),
            'timestamp': email.get('timestamp'),
            'updated_at': email.get('updated_at'),
            'completed_at': email.get('completed_at')
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(detail, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"Error getting email detail: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }
