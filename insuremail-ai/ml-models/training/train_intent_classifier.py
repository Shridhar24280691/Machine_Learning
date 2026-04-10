"""
Intent Classification Model Training
Trains traditional ML models (scikit-learn) for email intent classification
"""
import pandas as pd
import numpy as np
import pickle
import json
import re
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.pipeline import Pipeline
import boto3

# Configuration
DATA_PATH = os.environ.get('DATA_PATH', './data/training_data.csv')
MODEL_OUTPUT_PATH = os.environ.get('MODEL_OUTPUT_PATH', './output')
S3_BUCKET = os.environ.get('S3_BUCKET', 'insuremail-models')

# Intent categories
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

def load_data(filepath):
    """Load training data from CSV"""
    print(f"Loading data from {filepath}...")
    
    df = pd.read_csv(filepath)
    print(f"Loaded {len(df)} records")
    print(f"Columns: {df.columns.tolist()}")
    
    # Handle both 'intent' and 'customer_intent' column names
    intent_col = 'customer_intent' if 'customer_intent' in df.columns else 'intent'
    print(f"Intent distribution:\n{df[intent_col].value_counts()}")
    
    # Rename to 'intent' for consistency
    if intent_col != 'intent':
        df = df.rename(columns={intent_col: 'intent'})
    
    return df

def preprocess_text(text):
    """Preprocess text for training"""
    if pd.isna(text):
        return ""
    
    # Convert to lowercase
    text = str(text).lower()
    
    # Remove email addresses
    text = re.sub(r'\S+@\S+', ' ', text)
    
    # Remove URLs
    text = re.sub(r'http\S+|www\S+', ' ', text)
    
    # Remove special characters but keep spaces
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def extract_features(df):
    """Extract features from text"""
    print("Extracting features...")
    
    # Combine subject and body (handle both 'body' and 'body_text' column names)
    body_col = 'body_text' if 'body_text' in df.columns else 'body'
    df['combined_text'] = df['subject'].fillna('') + ' ' + df[body_col].fillna('')
    df['processed_text'] = df['combined_text'].apply(preprocess_text)
    
    # Add text length as feature
    df['text_length'] = df['processed_text'].str.len()
    
    # Add word count
    df['word_count'] = df['processed_text'].str.split().str.len()
    
    return df

def create_insurance_keywords():
    """Create insurance-specific keyword features"""
    keywords = {
        'claim_keywords': ['claim', 'claims', 'claimed', 'claiming', 'settlement'],
        'payment_keywords': ['payment', 'pay', 'paid', 'bill', 'billing', 'invoice', 'premium'],
        'policy_keywords': ['policy', 'policies', 'coverage', 'cover', 'plan'],
        'medical_keywords': ['hospital', 'doctor', 'medical', 'treatment', 'surgery', 'health'],
        'complaint_keywords': ['complaint', 'complain', 'unhappy', 'dissatisfied', 'problem', 'issue'],
        'urgent_keywords': ['urgent', 'emergency', 'asap', 'immediately', 'critical']
    }
    return keywords

def add_keyword_features(df):
    """Add keyword-based features"""
    keywords = create_insurance_keywords()
    
    for category, word_list in keywords.items():
        df[category] = df['processed_text'].apply(
            lambda x: sum(1 for word in word_list if word in x)
        )
    
    return df

def train_models(X_train, y_train, X_test, y_test):
    """Train multiple models and select best"""
    print("Training models...")
    
    models = {
        'logistic_regression': Pipeline([
            ('tfidf', TfidfVectorizer(max_features=10000, ngram_range=(1, 2))),
            ('clf', LogisticRegression(max_iter=1000, C=1.0))
        ]),
        'random_forest': Pipeline([
            ('tfidf', TfidfVectorizer(max_features=10000, ngram_range=(1, 2))),
            ('clf', RandomForestClassifier(n_estimators=100, random_state=42))
        ]),
        'gradient_boosting': Pipeline([
            ('tfidf', TfidfVectorizer(max_features=5000, ngram_range=(1, 2))),
            ('clf', GradientBoostingClassifier(n_estimators=100, random_state=42))
        ])
    }
    
    results = {}
    best_model = None
    best_score = 0
    
    for name, model in models.items():
        print(f"\nTraining {name}...")
        
        # Train
        model.fit(X_train, y_train)
        
        # Predict
        y_pred = model.predict(X_test)
        
        # Evaluate
        accuracy = accuracy_score(y_test, y_pred)
        cv_scores = cross_val_score(model, X_train, y_train, cv=5)
        
        print(f"Accuracy: {accuracy:.4f}")
        print(f"CV Score: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")
        print(f"\nClassification Report:\n{classification_report(y_test, y_pred)}")
        
        results[name] = {
            'model': model,
            'accuracy': accuracy,
            'cv_mean': cv_scores.mean(),
            'cv_std': cv_scores.std(),
            'predictions': y_pred
        }
        
        # Track best model
        if accuracy > best_score:
            best_score = accuracy
            best_model = model
    
    return best_model, results

def save_models(vectorizer, classifier, output_path):
    """Save models to disk and upload to S3"""
    print(f"\nSaving models to {output_path}...")
    
    os.makedirs(output_path, exist_ok=True)
    
    # Save vectorizer
    vectorizer_path = os.path.join(output_path, 'tfidf_vectorizer.pkl')
    with open(vectorizer_path, 'wb') as f:
        pickle.dump(vectorizer, f)
    print(f"Saved vectorizer to {vectorizer_path}")
    
    # Save classifier
    classifier_path = os.path.join(output_path, 'intent_classifier.pkl')
    with open(classifier_path, 'wb') as f:
        pickle.dump(classifier, f)
    print(f"Saved classifier to {classifier_path}")
    
    # Upload to S3
    s3 = boto3.client('s3')
    
    try:
        s3.upload_file(vectorizer_path, S3_BUCKET, 'models/tfidf_vectorizer.pkl')
        print(f"Uploaded vectorizer to s3://{S3_BUCKET}/models/tfidf_vectorizer.pkl")
        
        s3.upload_file(classifier_path, S3_BUCKET, 'models/intent_classifier.pkl')
        print(f"Uploaded classifier to s3://{S3_BUCKET}/models/intent_classifier.pkl")
        
    except Exception as e:
        print(f"S3 upload error: {str(e)}")

def generate_sample_data(output_path):
    """Generate sample training data for demonstration"""
    print("Generating sample training data...")
    
    sample_data = []
    
    # Claim submission samples
    claim_samples = [
        ("Claim for hospital visit", "I would like to submit a claim for my recent hospital stay. The treatment was on 15th March.", "claim_submission"),
        ("Submitting new claim", "Please find attached my claim form for dental treatment.", "claim_submission"),
        ("Claim form submission", "I am writing to submit a claim for my surgery last month.", "claim_submission"),
    ]
    
    # Claim status check samples
    status_samples = [
        ("Status of my claim", "Can you tell me the status of claim number 12345? I submitted it two weeks ago.", "claim_status_check"),
        ("Where is my claim?", "I haven't heard back about my claim. Can you update me?", "claim_status_check"),
        ("Claim progress", "What is happening with my recent claim submission?", "claim_status_check"),
    ]
    
    # Payment issue samples
    payment_samples = [
        ("Payment failed", "My direct debit failed this month. What should I do?", "payment_issue"),
        ("Wrong amount charged", "I was charged the wrong amount on my last bill.", "payment_issue"),
        ("Payment problem", "There seems to be an issue with my premium payment.", "payment_issue"),
    ]
    
    # Policy change samples
    policy_samples = [
        ("Change my policy", "I would like to upgrade my policy to include family coverage.", "policy_change"),
        ("Add dependent", "Please add my newborn baby to my policy.", "policy_change"),
        ("Modify coverage", "Can I change my coverage level?", "policy_change"),
    ]
    
    # Complaint samples
    complaint_samples = [
        ("Very unhappy with service", "I am extremely dissatisfied with the handling of my claim.", "complaint"),
        ("Complaint about claim denial", "My claim was unfairly rejected and I want to complain.", "complaint"),
        ("Poor service", "The customer service I received was unacceptable.", "complaint"),
    ]
    
    # Coverage inquiry samples
    coverage_samples = [
        ("What is covered?", "Does my policy cover physiotherapy sessions?", "coverage_inquiry"),
        ("Coverage question", "I need to know if my plan includes optical coverage.", "coverage_inquiry"),
        ("Benefits enquiry", "What benefits am I entitled to under my current plan?", "coverage_inquiry"),
    ]
    
    # General inquiry samples
    general_samples = [
        ("Question about my account", "I have a question about my policy details.", "general_inquiry"),
        ("Information request", "Could you send me information about your plans?", "general_inquiry"),
        ("General question", "I need some help understanding my policy.", "general_inquiry"),
    ]
    
    # Document request samples
    document_samples = [
        ("Request policy documents", "Please send me a copy of my policy documents.", "document_request"),
        ("Need insurance card", "I have lost my insurance card, can I get a replacement?", "document_request"),
        ("Send me certificate", "I need a certificate of insurance for my mortgage.", "document_request"),
    ]
    
    # Combine all samples
    all_samples = (claim_samples + status_samples + payment_samples + 
                   policy_samples + complaint_samples + coverage_samples + 
                   general_samples + document_samples)
    
    # Create DataFrame
    df = pd.DataFrame(all_samples, columns=['subject', 'body', 'intent'])
    
    # Augment data by duplicating with variations
    augmented = []
    for _, row in df.iterrows():
        augmented.append(row.to_dict())
        # Add slight variations
        for i in range(3):
            aug_row = row.to_dict().copy()
            aug_row['body'] = row['body'] + f" (variant {i})"
            augmented.append(aug_row)
    
    df_augmented = pd.DataFrame(augmented)
    
    # Save to CSV
    os.makedirs(output_path, exist_ok=True)
    output_file = os.path.join(output_path, 'training_data.csv')
    df_augmented.to_csv(output_file, index=False)
    print(f"Saved sample data to {output_file}")
    
    return output_file

def main():
    """Main training pipeline"""
    print("=" * 60)
    print("InsureMail AI - Intent Classification Model Training")
    print("=" * 60)
    
    # Check if training data exists, generate sample if not
    data_path = DATA_PATH
    if not os.path.exists(data_path):
        print(f"Training data not found at {data_path}")
        data_path = generate_sample_data('./data')
    
    # Load data
    df = load_data(data_path)
    
    # Preprocess
    df = extract_features(df)
    df = add_keyword_features(df)
    
    # Prepare training data
    X = df['processed_text']
    y = df['intent']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"\nTraining set size: {len(X_train)}")
    print(f"Test set size: {len(X_test)}")
    
    # Train models
    best_model, results = train_models(X_train, y_train, X_test, y_test)
    
    # Extract vectorizer and classifier from pipeline
    vectorizer = best_model.named_steps['tfidf']
    classifier = best_model.named_steps['clf']
    
    # Save models
    save_models(vectorizer, classifier, MODEL_OUTPUT_PATH)
    
    # Print summary
    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)
    print(f"Best Model: {max(results, key=lambda x: results[x]['accuracy'])}")
    print(f"Test Accuracy: {max(r['accuracy'] for r in results.values()):.4f}")
    print("=" * 60)

if __name__ == '__main__':
    main()
