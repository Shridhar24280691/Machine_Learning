"""
Email Sender Lambda Function
Sends responses via AWS SES
"""
import json
import boto3
import os
import re
from datetime import datetime

# AWS Clients
ses = boto3.client('ses')
dynamodb = boto3.resource('dynamodb')

# Configuration
EMAILS_TABLE = os.environ.get('EMAILS_TABLE', 'InsureMail-Emails')
SES_FROM_EMAIL = os.environ.get('SES_FROM_EMAIL', 'noreply@layahealthcare.ie')
SES_CONFIGURATION_SET = os.environ.get('SES_CONFIGURATION_SET', 'InsureMail-Tracking')

def lambda_handler(event, context):
    """
    Send email response via SES
    
    Expected event format:
    {
        "email_id": "unique-email-id",
        "response_data": { ... },
        "parsed_data": { ... }
    }
    """
    try:
        print(f"Sending email for: {event}")
        
        email_id = event.get('email_id')
        response_data = event.get('response_data', {})
        parsed_data = event.get('parsed_data', {})
        
        # Get recipient email
        recipient = extract_email(parsed_data.get('sender', ''))
        
        # Get response text
        response_text = response_data.get('generated_response', '')
        
        # Parse subject and body from response
        subject, body = parse_response(response_text)
        
        # Build HTML email
        html_body = build_html_email(body, response_data)
        
        # Send via SES
        send_result = send_via_ses(recipient, subject, body, html_body)
        
        # Update database
        update_sent_status(email_id, send_result)
        
        return {
            'statusCode': 200,
            'email_id': email_id,
            'send_result': send_result,
            'next_step': 'save_result'
        }
        
    except Exception as e:
        print(f"Email sending error: {str(e)}")
        return {
            'statusCode': 500,
            'email_id': event.get('email_id'),
            'error': str(e),
            'next_step': 'save_result'
        }

def extract_email(sender_string):
    """Extract email address from sender string"""
    match = re.search(r'<([^>]+)>', sender_string)
    if match:
        return match.group(1)
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', sender_string)
    if match:
        return match.group(0)
    return sender_string

def parse_response(response_text):
    """Parse subject and body from generated response"""
    lines = response_text.split('\n')
    
    subject = "Re: Your Inquiry"
    body = response_text
    
    # Look for subject line
    for line in lines:
        if line.lower().startswith('subject:'):
            subject = line.split(':', 1)[1].strip()
            body = '\n'.join(lines[lines.index(line)+1:]).strip()
            break
    
    return subject, body

def build_html_email(text_body, response_data):
    """Build professional HTML email"""
    
    action_decision = response_data.get('action_decision', {})
    confidence = action_decision.get('confidence_score', 0)
    
    # Determine confidence badge color
    if confidence >= 0.8:
        badge_color = '#28a745'  # Green
        badge_text = 'High Confidence'
    elif confidence >= 0.6:
        badge_color = '#ffc107'  # Yellow
        badge_text = 'Medium Confidence'
    else:
        badge_color = '#dc3545'  # Red
        badge_text = 'Reviewed by Agent'
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #6B46C1, #805AD5); padding: 20px; text-align: center; }}
        .header h1 {{ color: white; margin: 0; font-size: 24px; }}
        .content {{ background: #f9f9f9; padding: 30px; border-radius: 8px; margin-top: 20px; }}
        .badge {{ display: inline-block; padding: 5px 15px; border-radius: 20px; color: white; font-size: 12px; margin-top: 10px; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
        .disclaimer {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin-top: 20px; font-size: 11px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Laya Healthcare</h1>
        </div>
        
        <div class="content">
            {text_body.replace(chr(10), '<br>')}
            
            <span class="badge" style="background-color: {badge_color};">{badge_text}</span>
        </div>
        
        <div class="disclaimer">
            <strong>Important Notice:</strong> This email was generated with AI assistance and reviewed by our team. 
            For urgent matters, please call 0818 123 456. This email contains confidential information intended 
            solely for the addressee.
        </div>
        
        <div class="footer">
            <p><strong>Laya Healthcare</strong><br>
            Eastgate Road, Eastgate, Little Island, Co. Cork, Ireland<br>
            Phone: 0818 123 456 | Email: info@layahealthcare.ie</p>
            
            <p>Registered in Ireland. Laya Healthcare Limited is regulated by the Central Bank of Ireland.</p>
        </div>
    </div>
</body>
</html>
"""
    return html

def send_via_ses(recipient, subject, text_body, html_body):
    """Send email via AWS SES"""
    
    try:
        response = ses.send_email(
            Source=SES_FROM_EMAIL,
            Destination={
                'ToAddresses': [recipient]
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': text_body,
                        'Charset': 'UTF-8'
                    },
                    'Html': {
                        'Data': html_body,
                        'Charset': 'UTF-8'
                    }
                }
            },
            ConfigurationSetName=SES_CONFIGURATION_SET
        )
        
        return {
            'success': True,
            'message_id': response['MessageId'],
            'recipient': recipient,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"SES send error: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'recipient': recipient,
            'timestamp': datetime.utcnow().isoformat()
        }

def update_sent_status(email_id, send_result):
    """Update email sent status in DynamoDB"""
    table = dynamodb.Table(EMAILS_TABLE)
    
    status = 'sent' if send_result.get('success') else 'send_failed'
    
    table.update_item(
        Key={'email_id': email_id},
        UpdateExpression='SET send_result = :sr, #status = :s, updated_at = :t',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':sr': send_result,
            ':s': status,
            ':t': datetime.utcnow().isoformat()
        }
    )
