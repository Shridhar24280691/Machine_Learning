"""
RAG Ingestion Lambda Function
Processes and ingests policy documents into the knowledge base
"""
import json
import boto3
import os
import re
import hashlib
from datetime import datetime

# AWS Clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime')
textract = boto3.client('textract')

# Configuration
KNOWLEDGE_TABLE = os.environ.get('KNOWLEDGE_TABLE', 'InsureMail-Knowledge')
DOCUMENTS_BUCKET = os.environ.get('DOCUMENTS_BUCKET', 'insuremail-documents')

def lambda_handler(event, context):
    """
    Ingest documents into knowledge base
    
    Triggered by S3 upload of new documents
    """
    try:
        print(f"Processing document ingestion: {event}")
        
        # Get S3 event details
        for record in event.get('Records', []):
            s3_bucket = record['s3']['bucket']['name']
            s3_key = record['s3']['object']['key']
            
            # Process document
            result = process_document(s3_bucket, s3_key)
            
            print(f"Processed document: {s3_key}")
        
        return {
            'statusCode': 200,
            'processed': len(event.get('Records', [])),
            'results': result
        }
        
    except Exception as e:
        print(f"Error in document ingestion: {str(e)}")
        return {
            'statusCode': 500,
            'error': str(e)
        }

def process_document(bucket, key):
    """Process a single document"""
    
    # Download document
    doc_obj = s3.get_object(Bucket=bucket, Key=key)
    doc_content = doc_obj['Body'].read()
    
    # Calculate hash for deduplication
    doc_hash = hashlib.md5(doc_content).hexdigest()
    
    # Check if already exists
    if document_exists(doc_hash):
        print(f"Document {key} already exists (hash: {doc_hash})")
        return {'status': 'duplicate', 'hash': doc_hash}
    
    # Extract text based on file type
    file_extension = key.split('.')[-1].lower()
    
    if file_extension == 'pdf':
        text = extract_text_from_pdf(doc_content)
    elif file_extension in ['txt', 'md']:
        text = doc_content.decode('utf-8')
    else:
        text = extract_text_with_textract(doc_content)
    
    # Chunk the document
    chunks = chunk_document(text, chunk_size=500, overlap=50)
    
    # Process each chunk
    doc_id = key.replace('/', '_').replace('.', '_')
    title = extract_title(text) or key.split('/')[-1]
    category = extract_category(key, text)
    
    for idx, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}_chunk_{idx}"
        
        # Generate embedding
        embedding = generate_embedding(chunk)
        
        # Store in DynamoDB
        store_chunk(chunk_id, doc_id, title, chunk, category, embedding, key)
    
    return {
        'status': 'success',
        'doc_id': doc_id,
        'title': title,
        'chunks': len(chunks),
        'hash': doc_hash
    }

def extract_text_from_pdf(content):
    """Extract text from PDF using Textract"""
    try:
        response = textract.detect_document_text(Document={'Bytes': content})
        text = ' '.join([
            block['Text'] for block in response['Blocks']
            if block['BlockType'] == 'LINE'
        ])
        return text
    except Exception as e:
        print(f"Textract error: {str(e)}")
        return ""

def extract_text_with_textract(content):
    """Extract text using Textract for various formats"""
    try:
        response = textract.detect_document_text(Document={'Bytes': content})
        text = ' '.join([
            block['Text'] for block in response['Blocks']
            if block['BlockType'] == 'LINE'
        ])
        return text
    except Exception as e:
        print(f"Textract error: {str(e)}")
        return ""

def chunk_document(text, chunk_size=500, overlap=50):
    """Split document into overlapping chunks"""
    words = text.split()
    chunks = []
    
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = ' '.join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    
    return chunks

def generate_embedding(text):
    """Generate embedding using Amazon Titan"""
    try:
        response = bedrock.invoke_model(
            modelId='amazon.titan-embed-text-v2:0',
            body=json.dumps({
                'inputText': text[:8000]
            })
        )
        
        result = json.loads(response['body'].read())
        return result['embedding']
        
    except Exception as e:
        print(f"Embedding generation error: {str(e)}")
        return None

def store_chunk(chunk_id, doc_id, title, content, category, embedding, source_key):
    """Store document chunk in DynamoDB"""
    table = dynamodb.Table(KNOWLEDGE_TABLE)
    
    # Extract keywords
    keywords = extract_keywords(content)
    
    item = {
        'doc_id': chunk_id,
        'parent_doc_id': doc_id,
        'title': title,
        'content': content[:4000],  # Limit content size
        'category': category,
        'keywords': keywords,
        'embedding': embedding,
        'source_key': source_key,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    table.put_item(Item=item)

def extract_title(text):
    """Extract title from document text"""
    lines = text.split('\n')
    for line in lines[:10]:
        line = line.strip()
        if line and len(line) < 200:
            return line
    return None

def extract_category(key, text):
    """Extract category from file path or content"""
    # Check path
    if 'policy' in key.lower():
        return 'policy'
    elif 'claim' in key.lower():
        return 'claims'
    elif 'coverage' in key.lower():
        return 'coverage'
    elif 'faq' in key.lower():
        return 'faq'
    
    # Check content
    text_lower = text.lower()[:1000]
    if 'policy' in text_lower:
        return 'policy'
    elif 'claim' in text_lower:
        return 'claims'
    elif 'coverage' in text_lower:
        return 'coverage'
    
    return 'general'

def extract_keywords(text):
    """Extract keywords from text"""
    # Insurance-specific keywords
    insurance_keywords = [
        'claim', 'policy', 'coverage', 'premium', 'deductible', 'benefit',
        'hospital', 'medical', 'treatment', 'surgery', 'health', 'insurance',
        'exclusion', 'waiting period', 'pre-existing', 'renewal', 'cancellation'
    ]
    
    text_lower = text.lower()
    found_keywords = [kw for kw in insurance_keywords if kw in text_lower]
    
    return found_keywords[:10]  # Limit to 10 keywords

def document_exists(doc_hash):
    """Check if document already exists"""
    table = dynamodb.Table(KNOWLEDGE_TABLE)
    
    try:
        # Query by hash (would need a GSI in production)
        response = table.scan(
            FilterExpression='doc_hash = :h',
            ExpressionAttributeValues={':h': doc_hash},
            Limit=1
        )
        return len(response.get('Items', [])) > 0
    except:
        return False
