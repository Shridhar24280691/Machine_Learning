"""
CRM Validation Lambda Function
Looks up customer in database and validates eligibility
"""
import json
import boto3
import os
import re
from datetime import datetime

# AWS Clients
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime')

# Configuration
CUSTOMERS_TABLE = os.environ.get('CUSTOMERS_TABLE', 'InsureMail-Customers')
EMAILS_TABLE = os.environ.get('EMAILS_TABLE', 'InsureMail-Emails')

def lambda_handler(event, context):
    """
    Validate customer in CRM
    
    Expected event format:
    {
        "email_id": "unique-email-id",
        "parsed_data": { ... },
        "classification": { ... }
    }
    """
    try:
        print(f"Validating CRM for: {event}")
        
        email_id = event.get('email_id')
        parsed_data = event.get('parsed_data', {})
        classification = event.get('classification', {})
        
        extracted_fields = parsed_data.get('extracted_fields', {})
        sender_email = parsed_data.get('sender', '')
        
        # Extract email from sender string
        customer_email = extract_email(sender_email)
        
        # Try to find customer by various identifiers
        customer = None
        search_methods = []
        
        # Try policy number
        policy_number = extracted_fields.get('policy_number')
        if policy_number:
            customer = find_customer_by_policy(policy_number)
            if customer:
                search_methods.append('policy_number')
        
        # Try member ID
        if not customer:
            member_id = extracted_fields.get('member_id')
            if member_id:
                customer = find_customer_by_member_id(member_id)
                if customer:
                    search_methods.append('member_id')
        
        # Try email
        if not customer and customer_email:
            customer = find_customer_by_email(customer_email)
            if customer:
                search_methods.append('email')
        
        # Validate eligibility based on intent
        intent = classification.get('primary_intent', '')
        eligibility = check_eligibility(customer, intent)
        
        # Build validation result
        validation_result = {
            'customer_found': customer is not None,
            'search_methods_used': search_methods,
            'customer_profile': sanitize_customer_data(customer) if customer else None,
            'eligibility': eligibility,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Update database
        update_crm_validation(email_id, validation_result)
        
        return {
            'statusCode': 200,
            'email_id': email_id,
            'crm_validation': validation_result,
            'next_step': 'generate_response'
        }
        
    except Exception as e:
        print(f"CRM validation error: {str(e)}")
        return {
            'statusCode': 200,
            'email_id': event.get('email_id'),
            'crm_validation': {
                'customer_found': False,
                'error': str(e),
                'eligibility': {'eligible': False, 'reason': 'validation_error'}
            },
            'next_step': 'generate_response'
        }

def extract_email(sender_string):
    """Extract email address from sender string"""
    match = re.search(r'<([^>]+)>', sender_string)
    if match:
        return match.group(1)
    # Try to find email pattern
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', sender_string)
    if match:
        return match.group(0)
    return sender_string

def find_customer_by_policy(policy_number):
    """Find customer by policy number"""
    table = dynamodb.Table(CUSTOMERS_TABLE)
    
    try:
        # Query by GSI if available, otherwise scan
        response = table.scan(
            FilterExpression='policy_number = :pn',
            ExpressionAttributeValues={':pn': policy_number}
        )
        
        items = response.get('Items', [])
        return items[0] if items else None
        
    except Exception as e:
        print(f"Error finding by policy: {str(e)}")
        return None

def find_customer_by_member_id(member_id):
    """Find customer by member ID"""
    table = dynamodb.Table(CUSTOMERS_TABLE)
    
    try:
        response = table.get_item(Key={'member_id': member_id})
        return response.get('Item')
        
    except Exception as e:
        print(f"Error finding by member ID: {str(e)}")
        return None

def find_customer_by_email(email):
    """Find customer by email"""
    table = dynamodb.Table(CUSTOMERS_TABLE)
    
    try:
        response = table.scan(
            FilterExpression='email = :e',
            ExpressionAttributeValues={':e': email}
        )
        
        items = response.get('Items', [])
        return items[0] if items else None
        
    except Exception as e:
        print(f"Error finding by email: {str(e)}")
        return None

def check_eligibility(customer, intent):
    """Check if customer is eligible for the requested action"""
    
    if not customer:
        return {
            'eligible': False,
            'reason': 'customer_not_found',
            'message': 'Customer not found. Please provide policy number or member ID.'
        }
    
    # Check policy status
    policy_status = customer.get('policy_status', 'unknown')
    
    # For claims - need active policy
    if 'claim' in intent:
        if policy_status != 'active':
            return {
                'eligible': False,
                'reason': 'policy_not_active',
                'message': f'Policy is {policy_status}. Cannot process claims.'
            }
    
    # For policy changes - need active policy
    if 'policy' in intent and intent != 'policy_renewal':
        if policy_status != 'active':
            return {
                'eligible': False,
                'reason': 'policy_not_active',
                'message': f'Policy is {policy_status}. Cannot make changes.'
            }
    
    # Check for payment issues
    payment_status = customer.get('payment_status', 'unknown')
    if 'payment' in intent:
        return {
            'eligible': True,
            'reason': 'payment_query_allowed',
            'payment_status': payment_status
        }
    
    # Complaints are always allowed
    if intent == 'complaint':
        return {
            'eligible': True,
            'reason': 'complaints_always_allowed'
        }
    
    # Default - eligible
    return {
        'eligible': True,
        'reason': 'customer_verified',
        'policy_status': policy_status
    }

def sanitize_customer_data(customer):
    """Remove sensitive data from customer profile for storage"""
    if not customer:
        return None
    
    return {
        'customer_id': customer.get('customer_id'),
        'member_id': customer.get('member_id'),
        'policy_number': mask_policy_number(customer.get('policy_number')),
        'name': customer.get('name'),
        'policy_type': customer.get('policy_type'),
        'policy_status': customer.get('policy_status'),
        'coverage_start': customer.get('coverage_start'),
        'coverage_end': customer.get('coverage_end'),
        'plan_name': customer.get('plan_name')
    }

def mask_policy_number(policy_number):
    """Mask policy number for privacy"""
    if not policy_number:
        return None
    if len(policy_number) <= 4:
        return '*' * len(policy_number)
    return '*' * (len(policy_number) - 4) + policy_number[-4:]

def update_crm_validation(email_id, validation_result):
    """Update CRM validation in DynamoDB"""
    table = dynamodb.Table(EMAILS_TABLE)
    
    table.update_item(
        Key={'email_id': email_id},
        UpdateExpression='SET crm_validation = :c, #status = :s, updated_at = :t',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':c': validation_result,
            ':s': 'crm_validated',
            ':t': datetime.utcnow().isoformat()
        }
    )
