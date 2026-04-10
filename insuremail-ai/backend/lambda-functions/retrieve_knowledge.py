"""
Knowledge Retrieval Lambda Function (RAG)
Retrieves relevant policy documents using vector search + keyword search
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
KNOWLEDGE_TABLE = os.environ.get('KNOWLEDGE_TABLE', 'InsureMail-Knowledge')
EMAILS_TABLE = os.environ.get('EMAILS_TABLE', 'InsureMail-Emails')

def lambda_handler(event, context):
    """
    Retrieve relevant knowledge for the email
    
    Expected event format:
    {
        "email_id": "unique-email-id",
        "parsed_data": { ... },
        "classification": { ... }
    }
    """
    try:
        print(f"Retrieving knowledge for: {event}")
        
        email_id = event.get('email_id')
        parsed_data = event.get('parsed_data', {})
        classification = event.get('classification', {})
        
        query_text = build_search_query(parsed_data, classification)
        
        # Generate embedding for the query
        query_embedding = generate_embedding(query_text)
        
        # Retrieve documents using vector search
        vector_results = vector_search(query_embedding, top_k=10)
        
        # Retrieve documents using keyword search (BM25-like)
        keyword_results = keyword_search(query_text, top_k=10)
        
        # Combine results using RRF (Reciprocal Rank Fusion)
        combined_results = reciprocal_rank_fusion(vector_results, keyword_results, k=60)
        
        # Rerank with cross-encoder (using LLM)
        final_results = rerank_with_llm(query_text, combined_results[:5])
        
        # Update database
        update_knowledge_in_db(email_id, final_results)
        
        return {
            'statusCode': 200,
            'email_id': email_id,
            'retrieved_documents': final_results,
            'query_text': query_text,
            'next_step': 'validate_crm'
        }
        
    except Exception as e:
        print(f"Error retrieving knowledge: {str(e)}")
        return {
            'statusCode': 200,
            'email_id': event.get('email_id'),
            'retrieved_documents': [],
            'query_text': '',
            'next_step': 'validate_crm'
        }

def build_search_query(parsed_data, classification):
    """Build search query from email content and intent"""
    subject = parsed_data.get('subject', '')
    body = parsed_data.get('body_text', '')
    intent = classification.get('primary_intent', '')
    
    # Extract key phrases from body
    key_phrases = extract_key_phrases(body)
    
    # Build query
    query_parts = [subject, intent.replace('_', ' ')]
    query_parts.extend(key_phrases[:5])  # Top 5 key phrases
    
    return ' '.join(query_parts)

def extract_key_phrases(text):
    """Extract key phrases from text"""
    # Simple extraction - in production use NLP library
    words = re.findall(r'\b[A-Za-z]{4,}\b', text.lower())
    
    # Insurance-specific keywords get higher weight
    insurance_keywords = [
        'claim', 'policy', 'coverage', 'premium', 'deductible',
        'benefit', 'hospital', 'medical', 'treatment', 'surgery',
        'emergency', 'inpatient', 'outpatient', 'exclusion',
        'waiting period', 'pre-existing', 'renewal'
    ]
    
    # Filter and prioritize
    phrases = []
    for word in words:
        if word in insurance_keywords:
            phrases.append(word)
    
    # Add other significant words
    for word in words:
        if word not in phrases and len(phrases) < 10:
            phrases.append(word)
    
    return list(dict.fromkeys(phrases))  # Remove duplicates

def generate_embedding(text):
    """Generate embedding using Amazon Titan"""
    try:
        response = bedrock.invoke_model(
            modelId='amazon.titan-embed-text-v2:0',
            body=json.dumps({
                'inputText': text[:8000]  # Titan has token limit
            })
        )
        
        result = json.loads(response['body'].read())
        return result['embedding']
        
    except Exception as e:
        print(f"Embedding generation error: {str(e)}")
        return None

def vector_search(embedding, top_k=10):
    """Search documents by vector similarity"""
    if embedding is None:
        return []
    
    table = dynamodb.Table(KNOWLEDGE_TABLE)
    
    # Scan all documents (in production, use OpenSearch or Pinecone)
    # For DynamoDB, we'll use a simplified approach
    try:
        response = table.scan(
            ProjectionExpression='doc_id, title, content, embedding, category'
        )
        
        documents = response.get('Items', [])
        
        # Calculate cosine similarity
        results = []
        for doc in documents:
            doc_embedding = doc.get('embedding')
            if doc_embedding:
                similarity = cosine_similarity(embedding, doc_embedding)
                results.append({
                    'doc_id': doc['doc_id'],
                    'title': doc.get('title', ''),
                    'content': doc.get('content', '')[:2000],
                    'category': doc.get('category', ''),
                    'vector_score': similarity
                })
        
        # Sort by similarity
        results.sort(key=lambda x: x['vector_score'], reverse=True)
        return results[:top_k]
        
    except Exception as e:
        print(f"Vector search error: {str(e)}")
        return []

def keyword_search(query, top_k=10):
    """Search documents using keyword matching (BM25-like)"""
    table = dynamodb.Table(KNOWLEDGE_TABLE)
    
    try:
        response = table.scan(
            ProjectionExpression='doc_id, title, content, keywords, category'
        )
        
        documents = response.get('Items', [])
        query_terms = set(query.lower().split())
        
        results = []
        for doc in documents:
            content = doc.get('content', '').lower()
            title = doc.get('title', '').lower()
            keywords = doc.get('keywords', [])
            
            # Calculate BM25-like score
            score = 0
            
            # Title matches get higher weight
            for term in query_terms:
                if term in title:
                    score += 3
                if term in content:
                    score += 1
                if term in [k.lower() for k in keywords]:
                    score += 2
            
            if score > 0:
                results.append({
                    'doc_id': doc['doc_id'],
                    'title': doc.get('title', ''),
                    'content': doc.get('content', '')[:2000],
                    'category': doc.get('category', ''),
                    'keyword_score': score
                })
        
        # Sort by score
        results.sort(key=lambda x: x['keyword_score'], reverse=True)
        return results[:top_k]
        
    except Exception as e:
        print(f"Keyword search error: {str(e)}")
        return []

def reciprocal_rank_fusion(vector_results, keyword_results, k=60):
    """Combine vector and keyword search results using RRF"""
    
    scores = {}
    doc_info = {}
    
    # Score from vector search
    for rank, doc in enumerate(vector_results):
        doc_id = doc['doc_id']
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        doc_info[doc_id] = doc
    
    # Score from keyword search
    for rank, doc in enumerate(keyword_results):
        doc_id = doc['doc_id']
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
        if doc_id not in doc_info:
            doc_info[doc_id] = doc
    
    # Combine and sort
    combined = []
    for doc_id, score in scores.items():
        doc = doc_info[doc_id].copy()
        doc['rrf_score'] = score
        combined.append(doc)
    
    combined.sort(key=lambda x: x['rrf_score'], reverse=True)
    return combined

def rerank_with_llm(query, documents):
    """Rerank documents using LLM relevance scoring"""
    
    if not documents:
        return []
    
    reranked = []
    
    for doc in documents:
        prompt = f"""Rate the relevance of this document to the query on a scale of 0-10.

Query: {query}

Document Title: {doc['title']}
Document Content: {doc['content'][:1000]}

Respond with ONLY a number from 0 to 10."""

        try:
            response = bedrock.invoke_model(
                modelId='anthropic.claude-3-haiku-20240307-v1:0',
                body=json.dumps({
                    'anthropic_version': 'bedrock-2023-05-31',
                    'max_tokens': 10,
                    'messages': [{'role': 'user', 'content': prompt}]
                })
            )
            
            result = json.loads(response['body'].read())
            score_text = result['content'][0]['text'].strip()
            
            # Extract number
            match = re.search(r'\d+', score_text)
            if match:
                llm_score = int(match.group()) / 10.0  # Normalize to 0-1
            else:
                llm_score = 0.5
            
            doc['llm_relevance_score'] = llm_score
            doc['final_score'] = (doc.get('rrf_score', 0) * 0.5) + (llm_score * 0.5)
            reranked.append(doc)
            
        except Exception as e:
            print(f"Reranking error: {str(e)}")
            doc['llm_relevance_score'] = 0.5
            doc['final_score'] = doc.get('rrf_score', 0)
            reranked.append(doc)
    
    reranked.sort(key=lambda x: x['final_score'], reverse=True)
    return reranked

def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors"""
    import math
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0
    
    return dot_product / (magnitude1 * magnitude2)

def update_knowledge_in_db(email_id, documents):
    """Update retrieved knowledge in DynamoDB"""
    table = dynamodb.Table(EMAILS_TABLE)
    
    # Store top 5 documents
    top_docs = [
        {
            'doc_id': d['doc_id'],
            'title': d['title'],
            'category': d.get('category', ''),
            'score': d.get('final_score', 0)
        }
        for d in documents[:5]
    ]
    
    table.update_item(
        Key={'email_id': email_id},
        UpdateExpression='SET retrieved_documents = :d, updated_at = :t',
        ExpressionAttributeValues={
            ':d': top_docs,
            ':t': datetime.utcnow().isoformat()
        }
    )
