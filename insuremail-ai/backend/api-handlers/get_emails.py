"""
API Handler: Get Emails List
Returns list of emails with filtering and pagination
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
    GET /emails - List all emails with filters
    
    Query Parameters:
    - status: filter by status (parsed, classified, sent, etc.)
    - intent: filter by intent
    - priority: filter by priority
    - limit: number of results (default 20, max 100)
    - next_token: pagination token
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        
        status_filter = query_params.get('status')
        intent_filter = query_params.get('intent')
        priority_filter = query_params.get('priority')
        limit = int(query_params.get('limit', 20))
        limit = min(limit, 100)  # Cap at 100
        
        table = dynamodb.Table(EMAILS_TABLE)
        
        # Build filter expression
        filter_expressions = []
        expr_values = {}
        expr_names = {}
        
        if status_filter:
            filter_expressions.append('#status = :status')
            expr_values[':status'] = status_filter
            expr_names['#status'] = 'status'
        
        if intent_filter:
            filter_expressions.append('classification.primary_intent = :intent')
            expr_values[':intent'] = intent_filter
        
        if priority_filter:
            filter_expressions.append('classification.priority = :priority')
            expr_values[':priority'] = priority_filter
        
        # Query DynamoDB
        scan_kwargs = {
            'Limit': limit,
            'ProjectionExpression': 'email_id, subject, sender, #status, classification, timestamp, action_decision',
            'ScanIndexForward': False  # Most recent first
        }
        
        if expr_names:
            scan_kwargs['ExpressionAttributeNames'] = expr_names
        
        if filter_expressions:
            scan_kwargs['FilterExpression'] = ' AND '.join(filter_expressions)
            scan_kwargs['ExpressionAttributeValues'] = expr_values
        
        response = table.scan(**scan_kwargs)
        
        emails = response.get('Items', [])
        
        # Format response
        formatted_emails = []
        for email in emails:
            formatted_emails.append({
                'email_id': email.get('email_id'),
                'subject': email.get('subject', ''),
                'sender': email.get('sender', ''),
                'status': email.get('status', ''),
                'intent': email.get('classification', {}).get('primary_intent', ''),
                'priority': email.get('classification', {}).get('priority', ''),
                'confidence': email.get('classification', {}).get('confidence', 0),
                'auto_send': email.get('action_decision', {}).get('auto_send', False),
                'timestamp': email.get('timestamp', '')
            })
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'emails': formatted_emails,
                'count': len(formatted_emails),
                'next_token': response.get('LastEvaluatedKey')
            }, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"Error getting emails: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }
