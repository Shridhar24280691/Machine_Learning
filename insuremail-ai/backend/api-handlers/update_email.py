"""
API Handler: Update Email
Allows humans to edit responses and update status
"""
import json
import boto3
import os
from datetime import datetime

# AWS Clients
dynamodb = boto3.resource('dynamodb')

# Configuration
EMAILS_TABLE = os.environ.get('EMAILS_TABLE', 'InsureMail-Emails')

def lambda_handler(event, context):
    """
    POST /emails/{id} - Update email (edit response, approve, etc.)
    
    Request Body:
    - action: 'edit_response', 'approve', 'reject', 'send'
    - response_text: new response text (for edit_response)
    - notes: human notes
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
        
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        action = body.get('action')
        
        if not action:
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Action is required'})
            }
        
        table = dynamodb.Table(EMAILS_TABLE)
        
        # Get current email
        response = table.get_item(Key={'email_id': email_id})
        email = response.get('Item')
        
        if not email:
            return {
                'statusCode': 404,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Email not found'})
            }
        
        # Handle different actions
        if action == 'edit_response':
            result = edit_response(table, email_id, body)
        elif action == 'approve':
            result = approve_email(table, email_id, body)
        elif action == 'reject':
            result = reject_email(table, email_id, body)
        elif action == 'send':
            result = mark_for_send(table, email_id, body)
        else:
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': f'Unknown action: {action}'})
            }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': f'Email {action}d successfully',
                'email_id': email_id,
                'result': result
            })
        }
        
    except Exception as e:
        print(f"Error updating email: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)})
        }

def edit_response(table, email_id, body):
    """Edit the generated response"""
    new_response = body.get('response_text', '')
    editor = body.get('editor', 'unknown')
    
    table.update_item(
        Key={'email_id': email_id},
        UpdateExpression='SET generated_response = :r, human_edited = :he, edited_by = :eb, edited_at = :t, #status = :s',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':r': new_response,
            ':he': True,
            ':eb': editor,
            ':t': datetime.utcnow().isoformat(),
            ':s': 'edited'
        }
    )
    
    return {'edited': True, 'editor': editor}

def approve_email(table, email_id, body):
    """Approve email for sending"""
    approver = body.get('approver', 'unknown')
    notes = body.get('notes', '')
    
    table.update_item(
        Key={'email_id': email_id},
        UpdateExpression='SET approved = :a, approved_by = :ab, approval_notes = :an, approved_at = :t, #status = :s',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':a': True,
            ':ab': approver,
            ':an': notes,
            ':t': datetime.utcnow().isoformat(),
            ':s': 'approved'
        }
    )
    
    return {'approved': True, 'approver': approver}

def reject_email(table, email_id, body):
    """Reject email (needs rework)"""
    reviewer = body.get('reviewer', 'unknown')
    reason = body.get('reason', '')
    
    table.update_item(
        Key={'email_id': email_id},
        UpdateExpression='SET rejected = :r, rejected_by = :rb, rejection_reason = :rr, rejected_at = :t, #status = :s',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':r': True,
            ':rb': reviewer,
            ':rr': reason,
            ':t': datetime.utcnow().isoformat(),
            ':s': 'rejected'
        }
    )
    
    return {'rejected': True, 'reviewer': reviewer}

def mark_for_send(table, email_id, body):
    """Mark email ready for sending"""
    sender = body.get('sender', 'unknown')
    
    table.update_item(
        Key={'email_id': email_id},
        UpdateExpression='SET ready_to_send = :r, marked_by = :mb, marked_at = :t, #status = :s',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':r': True,
            ':mb': sender,
            ':t': datetime.utcnow().isoformat(),
            ':s': 'ready_to_send'
        }
    )
    
    return {'ready_to_send': True, 'marked_by': sender}
