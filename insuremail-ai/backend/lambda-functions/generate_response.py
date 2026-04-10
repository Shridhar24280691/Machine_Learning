"""
Response Generation Lambda Function
Generates personalized email responses using LLM
"""
import json
import boto3
import os
import re
from datetime import datetime

# AWS Clients
bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')

# Configuration
EMAILS_TABLE = os.environ.get('EMAILS_TABLE', 'InsureMail-Emails')

def lambda_handler(event, context):
    """
    Generate response for customer email
    
    Expected event format:
    {
        "email_id": "unique-email-id",
        "parsed_data": { ... },
        "classification": { ... },
        "retrieved_documents": [...],
        "crm_validation": { ... }
    }
    """
    try:
        print(f"Generating response for: {event}")
        
        email_id = event.get('email_id')
        parsed_data = event.get('parsed_data', {})
        classification = event.get('classification', {})
        retrieved_docs = event.get('retrieved_documents', [])
        crm_validation = event.get('crm_validation', {})
        
        # Build context for response generation
        context = build_context(parsed_data, classification, retrieved_docs, crm_validation)
        
        # Generate response using LLM
        response_text = generate_with_llm(context)
        
        # Evaluate response quality
        quality_score = evaluate_response_quality(response_text, context)
        
        # Determine if auto-send or human review
        action_decision = determine_action(classification, quality_score, crm_validation)
        
        result = {
            'email_id': email_id,
            'generated_response': response_text,
            'quality_score': quality_score,
            'action_decision': action_decision,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Update database
        update_response_in_db(email_id, result)
        
        return {
            'statusCode': 200,
            'email_id': email_id,
            'response_data': result,
            'next_step': 'send_email' if action_decision['auto_send'] else 'flag_for_review'
        }
        
    except Exception as e:
        print(f"Response generation error: {str(e)}")
        # Return fallback response
        fallback = generate_fallback_response(event)
        return {
            'statusCode': 200,
            'email_id': event.get('email_id'),
            'response_data': fallback,
            'next_step': 'flag_for_review'
        }

def build_context(parsed_data, classification, retrieved_docs, crm_validation):
    """Build context for LLM response generation"""
    
    # Customer email info
    customer_email = parsed_data.get('body_text', '')
    subject = parsed_data.get('subject', '')
    sender = parsed_data.get('sender', '')
    
    # Classification info
    intent = classification.get('primary_intent', 'general_inquiry')
    confidence = classification.get('confidence', 0.5)
    assigned_team = classification.get('assigned_team', 'customer_service')
    
    # CRM info
    customer_found = crm_validation.get('customer_found', False)
    customer_profile = crm_validation.get('customer_profile', {})
    eligibility = crm_validation.get('eligibility', {})
    
    # Build knowledge context from retrieved documents
    knowledge_context = ""
    for i, doc in enumerate(retrieved_docs[:3], 1):
        knowledge_context += f"\nDocument {i}: {doc.get('title', '')}\n"
        knowledge_context += f"Content: {doc.get('content', '')[:800]}\n"
    
    return {
        'customer_email': customer_email,
        'subject': subject,
        'sender': sender,
        'intent': intent,
        'confidence': confidence,
        'assigned_team': assigned_team,
        'customer_found': customer_found,
        'customer_profile': customer_profile,
        'eligibility': eligibility,
        'knowledge_context': knowledge_context
    }

def generate_with_llm(context):
    """Generate response using Bedrock LLM"""
    
    # Check eligibility constraints
    eligibility = context.get('eligibility', {})
    if not eligibility.get('eligible', True):
        return generate_constraint_response(eligibility, context)
    
    prompt = f"""You are a professional customer service representative for Laya Healthcare, an Irish health insurance company. Write a helpful, professional email response.

CUSTOMER EMAIL:
Subject: {context['subject']}
Body: {context['customer_email'][:1500]}

CUSTOMER INTENT: {context['intent']}

CUSTOMER INFORMATION:
- Customer Found: {context['customer_found']}
- Policy Status: {context['customer_profile'].get('policy_status', 'Unknown')}
- Plan Name: {context['customer_profile'].get('plan_name', 'Unknown')}

RELEVANT POLICY INFORMATION:
{context['knowledge_context']}

GUIDELINES:
1. Address the customer by name if available
2. Be empathetic and professional
3. Provide specific, accurate information based on the policy documents above
4. If you don't have enough information, acknowledge and say you'll escalate
5. Include relevant policy details and coverage information
6. Add appropriate next steps or actions
7. End with a professional closing

Write the complete email response (subject line and body):"""

    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-haiku-20240307-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 1500,
                'temperature': 0.3,
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
        
        result = json.loads(response['body'].read())
        generated_text = result['content'][0]['text']
        
        # Clean up response
        generated_text = clean_response(generated_text)
        
        return generated_text
        
    except Exception as e:
        print(f"LLM generation error: {str(e)}")
        return generate_fallback_response(context)

def generate_constraint_response(eligibility, context):
    """Generate response when customer is not eligible"""
    reason = eligibility.get('reason', '')
    message = eligibility.get('message', '')
    
    customer_name = context.get('customer_profile', {}).get('name', 'Valued Customer')
    
    responses = {
        'customer_not_found': f"""Subject: Re: {context['subject']}

Dear Customer,

Thank you for contacting Laya Healthcare.

We were unable to locate your account with the information provided. To assist you promptly, please reply with:

- Your policy number, OR
- Your member ID, OR
- The email address associated with your account

Once we have this information, we'll be happy to help with your inquiry.

Best regards,
Laya Healthcare Customer Service""",
        
        'policy_not_active': f"""Subject: Re: {context['subject']}

Dear {customer_name},

Thank you for contacting Laya Healthcare.

{message}

To discuss your policy status and options for reinstatement, please contact our Customer Service team at 0818 123 456 or visit our website.

Best regards,
Laya Healthcare Customer Service"""
    }
    
    return responses.get(reason, f"""Subject: Re: {context['subject']}

Dear Customer,

Thank you for contacting Laya Healthcare.

{message}

We apologize for any inconvenience. Please contact us at 0818 123 456 for further assistance.

Best regards,
Laya Healthcare Customer Service""")

def clean_response(text):
    """Clean up LLM response"""
    # Remove any markdown code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove extra newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def evaluate_response_quality(response_text, context):
    """Evaluate quality of generated response"""
    
    prompt = f"""Rate the following customer service response on these dimensions (0-10 scale):

Response to evaluate:
{response_text[:1000]}

Original customer query:
{context['customer_email'][:500]}

Rate on:
1. Faithfulness - Does it stick to facts without making things up?
2. Helpfulness - Does it address the customer's question?
3. Completeness - Does it provide all necessary information?
4. Professionalism - Is the tone appropriate?
5. Safety - Is it safe and compliant?

Return ONLY a JSON object:
{{
    "faithfulness": 8,
    "helpfulness": 9,
    "completeness": 7,
    "professionalism": 9,
    "safety": 10,
    "overall": 8.6
}}"""

    try:
        eval_response = bedrock.invoke_model(
            modelId='anthropic.claude-3-haiku-20240307-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 200,
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
        
        result = json.loads(eval_response['body'].read())
        content = result['content'][0]['text']
        
        # Extract JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            scores = json.loads(json_match.group())
            return scores
        
        return {'overall': 7.0, 'faithfulness': 7, 'helpfulness': 7}
        
    except Exception as e:
        print(f"Quality evaluation error: {str(e)}")
        return {'overall': 7.0, 'faithfulness': 7, 'helpfulness': 7}

def determine_action(classification, quality_score, crm_validation):
    """Determine whether to auto-send or flag for review"""
    
    # Get scores
    overall_quality = quality_score.get('overall', 0)
    intent_confidence = classification.get('confidence', 0)
    customer_found = crm_validation.get('customer_found', False)
    eligibility = crm_validation.get('eligibility', {})
    
    # Decision logic
    auto_send = True
    reasons = []
    
    # Check quality threshold
    if overall_quality < 7.5:
        auto_send = False
        reasons.append('low_quality_score')
    
    # Check intent confidence
    if intent_confidence < 0.75:
        auto_send = False
        reasons.append('low_intent_confidence')
    
    # Check if customer found
    if not customer_found:
        auto_send = False
        reasons.append('customer_not_found')
    
    # Check eligibility
    if not eligibility.get('eligible', True):
        auto_send = False
        reasons.append('customer_not_eligible')
    
    # High priority items need review
    priority = classification.get('priority', 'low')
    if priority == 'high':
        auto_send = False
        reasons.append('high_priority_item')
    
    # Complaints need human review
    intent = classification.get('primary_intent', '')
    if intent == 'complaint':
        auto_send = False
        reasons.append('complaint_requires_review')
    
    return {
        'auto_send': auto_send,
        'reasons': reasons if reasons else ['meets_all_criteria'],
        'confidence_score': (overall_quality / 10) * intent_confidence
    }

def generate_fallback_response(context):
    """Generate fallback response when LLM fails"""
    subject = context.get('subject', 'Your Inquiry')
    
    return f"""Subject: Re: {subject}

Dear Valued Customer,

Thank you for contacting Laya Healthcare. We have received your inquiry and are reviewing it carefully.

A member of our customer service team will respond to you within 24-48 hours with a detailed answer to your question.

If your matter is urgent, please call us at 0818 123 456.

Thank you for your patience.

Best regards,
Laya Healthcare Customer Service Team"""

def update_response_in_db(email_id, result):
    """Update response in DynamoDB"""
    table = dynamodb.Table(EMAILS_TABLE)
    
    table.update_item(
        Key={'email_id': email_id},
        UpdateExpression='SET generated_response = :r, quality_score = :q, action_decision = :a, #status = :s, updated_at = :t',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':r': result['generated_response'],
            ':q': result['quality_score'],
            ':a': result['action_decision'],
            ':s': 'response_generated',
            ':t': datetime.utcnow().isoformat()
        }
    )
