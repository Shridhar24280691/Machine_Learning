"""
Intent Classification Lambda Function
Classifies customer emails into 17 insurance intent categories
Uses both traditional ML (scikit-learn) and LLM-based classification
"""
import json
import boto3
import os
import pickle
import re
from datetime import datetime
import numpy as np

# AWS Clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime')

# Configuration
MODELS_BUCKET = os.environ.get('MODELS_BUCKET', 'insuremail-models-227855914226')
EMAILS_TABLE = os.environ.get('EMAILS_TABLE', 'InsureMail-Emails')

# Intent categories for insurance
INTENT_CATEGORIES = [
    'claim_submission',
    'claim_status_check',
    'claim_appeal',
    'payment_issue',
    'payment_query',
    'policy_change',
    'policy_renewal',
    'policy_cancellation',
    'coverage_inquiry',
    'complaint',
    'general_inquiry',
    'document_request',
    'address_change',
    'personal_details_update',
    'refund_request',
    'emergency_assistance',
    'other'
]

# Team routing mapping
INTENT_TO_TEAM = {
    'claim_submission': 'claims_team',
    'claim_status_check': 'claims_team',
    'claim_appeal': 'claims_team',
    'payment_issue': 'billing_team',
    'payment_query': 'billing_team',
    'policy_change': 'policy_team',
    'policy_renewal': 'policy_team',
    'policy_cancellation': 'policy_team',
    'coverage_inquiry': 'customer_service',
    'complaint': 'complaints_team',
    'general_inquiry': 'customer_service',
    'document_request': 'customer_service',
    'address_change': 'admin_team',
    'personal_details_update': 'admin_team',
    'refund_request': 'billing_team',
    'emergency_assistance': 'emergency_team',
    'other': 'customer_service'
}

# Load models globally for reuse
_vectorizer = None
_classifier = None

def load_models():
    """Load ML models from S3"""
    global _vectorizer, _classifier
    
    if _vectorizer is None or _classifier is None:
        try:
            # Download vectorizer
            vectorizer_obj = s3.get_object(
                Bucket=MODELS_BUCKET,
                Key='models/tfidf_vectorizer.pkl'
            )
            _vectorizer = pickle.loads(vectorizer_obj['Body'].read())
            
            # Download classifier
            classifier_obj = s3.get_object(
                Bucket=MODELS_BUCKET,
                Key='models/intent_classifier.pkl'
            )
            _classifier = pickle.loads(classifier_obj['Body'].read())
            
            print("Models loaded successfully")
        except Exception as e:
            print(f"Error loading models: {str(e)}")
            _vectorizer = None
            _classifier = None
    
    return _vectorizer, _classifier

def lambda_handler(event, context):
    """
    Main Lambda handler for intent classification
    
    Expected event format:
    {
        "email_id": "unique-email-id",
        "parsed_data": { ... parsed email data ... }
    }
    """
    try:
        print(f"Classifying intent for: {event}")
        
        email_id = event.get('email_id')
        parsed_data = event.get('parsed_data', {})
        
        email_text = parsed_data.get('body_text', '')
        subject = parsed_data.get('subject', '')
        
        # Combine subject and body for classification
        full_text = f"{subject} {email_text}"
        
        # Method 1: Traditional ML Classification
        ml_result = classify_with_ml(full_text)
        
        # Method 2: LLM-based Classification
        llm_result = classify_with_llm(full_text)
        
        # Ensemble: Combine both results
        final_result = ensemble_classification(ml_result, llm_result)
        
        # Update DynamoDB with classification
        update_classification_in_db(email_id, final_result)
        
        return {
            'statusCode': 200,
            'email_id': email_id,
            'classification': final_result,
            'next_step': 'retrieve_knowledge'
        }
        
    except Exception as e:
        print(f"Error classifying intent: {str(e)}")
        # Return fallback classification
        return {
            'statusCode': 200,
            'email_id': event.get('email_id'),
            'classification': {
                'primary_intent': 'other',
                'confidence': 0.5,
                'method': 'fallback'
            },
            'next_step': 'retrieve_knowledge'
        }

def classify_with_ml(text):
    """Classify using traditional ML model (scikit-learn)"""
    vectorizer, classifier = load_models()
    
    if vectorizer is None or classifier is None:
        return {
            'intent': 'other',
            'confidence': 0.0,
            'all_scores': {}
        }
    
    # Preprocess text
    processed_text = preprocess_text(text)
    
    # Vectorize
    X = vectorizer.transform([processed_text])
    
    # Predict probabilities
    probabilities = classifier.predict_proba(X)[0]
    predicted_idx = np.argmax(probabilities)
    
    # Build result
    all_scores = {
        INTENT_CATEGORIES[i]: float(probabilities[i])
        for i in range(len(INTENT_CATEGORIES))
    }
    
    return {
        'intent': INTENT_CATEGORIES[predicted_idx],
        'confidence': float(probabilities[predicted_idx]),
        'all_scores': all_scores
    }

def classify_with_llm(text):
    """Classify using Bedrock LLM"""
    
    prompt = f"""You are an expert insurance customer service classifier. Analyze the following customer email and classify it into ONE of these categories:

Categories:
1. claim_submission - Customer is submitting a new claim
2. claim_status_check - Customer asking about existing claim status
3. claim_appeal - Customer appealing a claim decision
4. payment_issue - Problem with payment (failed, wrong amount)
5. payment_query - Question about payment schedule/amount
6. policy_change - Request to modify policy details
7. policy_renewal - Questions about renewing policy
8. policy_cancellation - Request to cancel policy
9. coverage_inquiry - Questions about what's covered
10. complaint - Customer expressing dissatisfaction
11. general_inquiry - General questions
12. document_request - Request for documents/cards
13. address_change - Update address
14. personal_details_update - Update personal information
15. refund_request - Request for refund
16. emergency_assistance - Emergency situation
17. other - None of the above

Email to classify:
{text[:2000]}

Respond ONLY with a JSON object in this exact format:
{{
    "intent": "one_of_the_categories_above",
    "confidence": 0.95,
    "reasoning": "brief explanation"
}}"""

    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-haiku-20240307-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 300,
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
        
        result = json.loads(response['body'].read())
        content = result['content'][0]['text']
        
        # Extract JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            llm_output = json.loads(json_match.group())
            return {
                'intent': llm_output.get('intent', 'other'),
                'confidence': llm_output.get('confidence', 0.5),
                'reasoning': llm_output.get('reasoning', '')
            }
        
        return {'intent': 'other', 'confidence': 0.5, 'reasoning': 'parse_error'}
        
    except Exception as e:
        print(f"LLM classification error: {str(e)}")
        return {'intent': 'other', 'confidence': 0.5, 'reasoning': 'error'}

def ensemble_classification(ml_result, llm_result):
    """Combine ML and LLM classifications"""
    
    ml_intent = ml_result['intent']
    ml_conf = ml_result['confidence']
    
    llm_intent = llm_result['intent']
    llm_conf = llm_result['confidence']
    
    # If both agree, high confidence
    if ml_intent == llm_intent:
        final_intent = ml_intent
        final_confidence = max(ml_conf, llm_conf) * 0.95
    else:
        # Weighted average - trust LLM more for complex cases
        if llm_conf > 0.85:
            final_intent = llm_intent
            final_confidence = llm_conf
        elif ml_conf > 0.8:
            final_intent = ml_intent
            final_confidence = ml_conf
        else:
            # Use LLM when uncertain
            final_intent = llm_intent
            final_confidence = llm_conf * 0.8
    
    # Determine routing team
    assigned_team = INTENT_TO_TEAM.get(final_intent, 'customer_service')
    
    # Calculate priority based on intent
    priority = calculate_priority(final_intent, ml_result.get('all_scores', {}))
    
    return {
        'primary_intent': final_intent,
        'confidence': round(final_confidence, 3),
        'ml_classification': {
            'intent': ml_intent,
            'confidence': ml_conf
        },
        'llm_classification': {
            'intent': llm_intent,
            'confidence': llm_conf,
            'reasoning': llm_result.get('reasoning', '')
        },
        'assigned_team': assigned_team,
        'priority': priority,
        'requires_human_review': final_confidence < 0.7,
        'timestamp': datetime.utcnow().isoformat()
    }

def calculate_priority(intent, all_scores):
    """Calculate ticket priority based on intent"""
    high_priority = ['emergency_assistance', 'complaint', 'claim_appeal']
    medium_priority = ['claim_submission', 'payment_issue', 'refund_request']
    
    if intent in high_priority:
        return 'high'
    elif intent in medium_priority:
        return 'medium'
    else:
        return 'low'

def preprocess_text(text):
    """Preprocess text for ML model"""
    # Lowercase
    text = text.lower()
    # Remove special characters but keep spaces
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    # Remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def update_classification_in_db(email_id, classification):
    """Update classification in DynamoDB"""
    table = dynamodb.Table(EMAILS_TABLE)
    
    table.update_item(
        Key={'email_id': email_id},
        UpdateExpression='SET classification = :c, #status = :s, updated_at = :t',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':c': classification,
            ':s': 'classified',
            ':t': datetime.utcnow().isoformat()
        }
    )
