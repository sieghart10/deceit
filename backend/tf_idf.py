from collections import Counter
from utils.tokenizer import tokenize
from utils.ngram import tokenize_with_ngrams
from utils.progress import show_progress
import pandas as pd
import math
import random
import os
import pickle

RANDOM_SEED = 42

def set_random_seeds(seed=42):
    random.seed(seed)
    print(f"Random seed set to: {seed}")

def calculate_tf(doc_tokens):
    tf = {}
    total_terms = len(doc_tokens)
    term_counts = Counter(doc_tokens)
    
    for term, count in term_counts.items():
        # TF = (Number of times term appears in doc) / (Total number of terms in doc)
        tf[term] = count / total_terms
    
    return tf

def calculate_idf_with_ngrams(documents, use_log=True, include_bigrams=True, include_trigrams=False):
    N = len(documents)
    idf = {}
    all_features = set()
    
    print(f"Tokenizing {N:,} documents...")
    tokenized_docs = []
    show_progress_flag = N > 100
    update_freq = max(1, N // 100) if show_progress_flag else N

    for i, doc in enumerate(documents):
        features = tokenize_with_ngrams(doc, include_bigrams, include_trigrams)
        tokenized_docs.append(features)
        all_features.update(features)

        if show_progress_flag and (i % update_freq == 0 or i == N - 1):
            show_progress(i + 1, N, "Tokenizing documents")
        
    if show_progress_flag:
        print(f"\n  ✓ Tokenized {N:,} documents, found {len(all_features):,} unique features")

    print("Calculating IDF values...")
    feature_count = 0
    total_features = len(all_features)
    show_idf_progress = total_features > 1000
    update_freq_idf = max(1, total_features // 100) if show_idf_progress else total_features

    for feature in all_features:
        docs_with_feature = sum(1 for features in tokenized_docs if feature in features)
        
        if use_log:
            idf[feature] = math.log(N / docs_with_feature)
            # idf[feature] = math.log((N + 1) / (docs_with_feature + 1))
        else:
            idf[feature] = N / docs_with_feature
    
        feature_count += 1

        if show_idf_progress and (feature_count % update_freq_idf == 0 or feature_count == total_features):
            show_progress(feature_count, total_features, "Calculating IDF")

    if show_idf_progress:
        print(f"\n  ✓ Calculated IDF for {total_features:,} features")

    return idf, tokenized_docs

def calculate_tfidf_with_ngrams(documents, include_bigrams=True, include_trigrams=False):
    idf_values, tokenized_docs = calculate_idf_with_ngrams(documents, use_log=True, include_bigrams=include_bigrams, include_trigrams=include_trigrams)
    
    print("Calculating TF-IDF matrix...")
    tfidf_matrix = []
    doc_count = len(tokenized_docs)
    show_tfidf_progress = doc_count > 100
    update_freq = max(1, doc_count // 100) if show_tfidf_progress else doc_count
    
    for i, features in enumerate(tokenized_docs):
        tf = calculate_tf(features)
        
        doc_tfidf = {}
        for feature in tf:
            doc_tfidf[feature] = tf[feature] * idf_values.get(feature, 0)
        
        tfidf_matrix.append(doc_tfidf)
    
        if show_tfidf_progress and (i % update_freq == 0 or i == doc_count - 1):
            show_progress(i + 1, doc_count, "Computing TF-IDF")

    if show_tfidf_progress:
        print(f"\n  ✓ Computed TF-IDF matrix for {doc_count:,} documents")
    
    return tfidf_matrix, idf_values

def train_naive_bayes_tfidf_ngram(documents, labels, include_bigrams=False, include_trigrams=False):
    print("Training TF-IDF Naive Bayes Model")

    vocab_size = set()
    
    class_counter = {}
    class_word_counter = {}
    
    # calculate TF-IDF with n-grams
    tfidf_matrix, idf_values = calculate_tfidf_with_ngrams(
        documents, include_bigrams=include_bigrams, include_trigrams=include_trigrams
    )

    print("Training Naive Bayes classifier...")
    total_docs = len(documents)
    show_training_progress = total_docs > 100
    update_freq = max(1, total_docs // 100) if show_training_progress else total_docs
    
    for i, (doc, label) in enumerate(zip(documents, labels)):
        features = tokenize_with_ngrams(doc, include_bigrams, include_trigrams)
        vocab_size.update(features)
        
        if label not in class_counter:
            class_counter[label] = 0
            class_word_counter[label] = {}
        
        class_counter[label] += 1
        
        doc_tfidf = tfidf_matrix[i]
        for feature in features:
            weight = doc_tfidf.get(feature, 0)
            class_word_counter[label][feature] = class_word_counter[label].get(feature, 0) + weight

        if show_training_progress and (i % update_freq == 0 or i == total_docs - 1):
            show_progress(i + 1, total_docs, "Training classifier")

    if show_training_progress:
        print(f"\n  ✓ Trained on {total_docs:,} documents")

    return class_counter, class_word_counter, len(vocab_size), idf_values

def predict(text, class_counts, class_word_counts, vocab_size, idf_values, include_bigrams=True, include_trigrams=False, is_log=False):
    features = tokenize_with_ngrams(text, include_bigrams, include_trigrams)
    total_docs = sum(class_counts.values())
    scores = {}
    
    if is_log:
        print(f"Features (with n-grams): {features[:10]}...")  # onnly show first 10
    
    # calculate TF for query document with n-grams
    tf = calculate_tf(features)
    query_tfidf = {feature: tf[feature] * idf_values.get(feature, 0) for feature in tf}
    
    for label in class_counts.keys():
        prob = math.log(class_counts[label] / total_docs)
        
        for feature in features:
            feature_weight = class_word_counts[label].get(feature, 0)
            total_weight = sum(class_word_counts[label].values())
            query_weight = query_tfidf.get(feature, 0)
            
            likelihood = math.log((feature_weight + 1) / (total_weight + vocab_size)) * query_weight
            # likelihood = math.log((feature_weight + 1) / (total_weight + vocab_size))
            prob += likelihood
        
        scores[label] = prob
    
    predicted_class = max(scores, key=scores.get)
    
    max_score = max(scores.values())
    exp_scores = {label: math.exp(score - max_score) for label, score in scores.items()}
    total_exp = sum(exp_scores.values())
    probabilities = {label: exp_score/total_exp for label, exp_score in exp_scores.items()}
    
    return {
        'prediction': predicted_class,
        'raw_scores': scores,
        'score_difference': abs(scores.get('real', float('-inf')) - scores.get('fake', float('-inf'))),
        'probabilities': probabilities,
        'confidence': max(probabilities.values())
    }

def train_test_split(real_docs, fake_docs, test_ratio=0.2):
    # randomize
    random.shuffle(real_docs)
    random.shuffle(fake_docs)

    # calculate where to split
    test_size_real = math.ceil(len(real_docs) * test_ratio)
    test_size_fake = math.ceil(len(fake_docs) * test_ratio)

    # split real news
    test_real = real_docs[:test_size_real]
    train_real = real_docs[test_size_real:]

    # split fake news
    test_fake = fake_docs[:test_size_fake]
    train_fake = fake_docs[test_size_fake:]

    # combine train and test sets
    train_data = train_real + train_fake
    test_data = test_real + test_fake

    # randomize again
    random.shuffle(train_data)
    random.shuffle(test_data)

    # separate documents and labels
    train_docs, train_labels = zip(*train_data) if train_data else ([], [])
    test_docs, test_labels = zip(*test_data) if test_data else ([], [])

    print(f"  ✓ Split complete: {len(train_docs):,} train, {len(test_docs):,} test")
    return list(train_docs), list(train_labels), list(test_docs), list(test_labels)

def evaluate_model(test_docs, test_labels, class_counts, class_word_counts, vocab_size, idf_values, include_bigrams, include_trigrams):
    print("Evaluating model...")
    score = 0
    total = len(test_docs)
    show_eval_progress = total > 50
    update_freq = max(1, total // 100) if show_eval_progress else total
    
    predictions = []
    for i, (doc, true_label) in enumerate(zip(test_docs, test_labels)):
        predicted_result = predict(doc, class_counts, class_word_counts, vocab_size, idf_values, include_bigrams, include_trigrams, is_log=False)
        predicted_label = predicted_result['prediction']
        predictions.append((doc[:50] + "...", true_label, predicted_result))
        
        if predicted_label == true_label:
            score += 1
    
        if show_eval_progress and (i % update_freq == 0 or i == total - 1):
            show_progress(i + 1, total, "Evaluating")

    if show_eval_progress:
        print(f"\n  ✓ Evaluated {total:,} documents")

    accuracy = score / total if total > 0 else 0
    return accuracy, predictions

FILEPATH = 'tf_idf_naive_bayes_model.pkl'

def save_model(class_counts, class_word_counts, vocab_size, idf_values, filepath):
    print("Saving model...")
    save_dir = 'trained_models'
    os.makedirs(save_dir, exist_ok=True)
    full_path = os.path.join(save_dir, filepath)

    model_data = {
        'class_counts': class_counts,
        'class_word_counts': class_word_counts,
        'vocab_size': vocab_size,
        'idf_values': idf_values
    }
    
    with open(full_path, 'wb') as f:
        pickle.dump(model_data, f)
    
    file_size = os.path.getsize(full_path) / (1024 * 1024)
    print(f"  ✓ Model saved to {full_path} ({file_size:.2f} MB)")

def load_model(filepath):
    load_dir = 'trained_models'
    full_path = os.path.join(load_dir, filepath)

    if not os.path.exists(full_path):
        print(f"Model file {full_path} not found")
        return None
    
    with open(full_path, 'rb') as f:
        model_data = pickle.load(f)
    
    idf_values = model_data.get('idf_values', None)
    print(f"  ✓ Model loaded from {full_path}")
    
    return (model_data['class_counts'], 
            model_data['class_word_counts'], 
            model_data['vocab_size'],
            idf_values)

if __name__ == "__main__":
    # set_random_seeds(RANDOM_SEED)
    TRAIN = False

    df_real = pd.read_csv("data/articles.csv")
    df_fake = pd.read_csv("data/rappler_articles.csv")
    
    real_documents = list(zip(df_real['content'], ['real'] * len(df_real)))
    fake_documents = list(zip(df_fake['content'], ['fake'] * len(df_fake)))
    print(f"  ✓ Loaded {len(real_documents):,} real and {len(fake_documents):,} fake articles")

    # # print("=== Bag of Words Matrix (First 5 documents) ===")
    # # bow_matrix = create_bow_matrix(sample_documents[:5], sample_labels[:5])
    # # print(bow_matrix)
    # # print(f"Matrix shape: {bow_matrix.shape}\n")
    
    # print(f"=== Fake News Detection Using TF-IDF + Naive Bayes ===\n")
    
    # # Train-test split
    train_docs, train_labels, test_docs, test_labels = train_test_split(real_documents, fake_documents, test_ratio=0.2)
    print(f"Train label distribution: {Counter(train_labels)}")
    print(f"Test label distribution: {Counter(test_labels)}")
    
    if TRAIN:
        print("Training with TF-IDF + bigrams...")
        class_counts, class_word_counts, vocab_size, idf_values = train_naive_bayes_tfidf_ngram(
            train_docs, train_labels, include_bigrams=False, include_trigrams=False
        )
        save_model(class_counts, class_word_counts, vocab_size, idf_values, FILEPATH)

        print(f"Class distribution: {class_counts}")
        
        # print(f"Vocabulary size: {vocab_size}")
        print(f"Vocabulary size (with n-grams): {vocab_size}")
        print(f"Class distribution: {class_counts}\n")

        # Test the classifier
        print("=== Model Evaluation ===")
        accuracy, predictions = evaluate_model(test_docs, test_labels, class_counts, class_word_counts, vocab_size, idf_values, include_bigrams=False, include_trigrams=False)
        print(f"Accuracy: {accuracy:.2%}\n")
        
        # Testing with detailed analysis
        print("=== Testing Example ===")
        example_text = "A Chinese warship announced live fire exercises in waters some 90 nautical miles from the Zambales coastline yesterday morning, forcing Philippine Coast Guard vessels and dozens of Filipino fishing boats caught inside the designated danger zone to leave the area."
        
        prediction = predict(example_text, class_counts, class_word_counts, 
                               vocab_size, idf_values, include_bigrams=False, 
                               include_trigrams=False, is_log=True)
        
        print("=" * 50)
        print("PREDICTION SUMMARY:")
        print(f"Predicted Class: {prediction['prediction'].upper()}")
        print(f"Confidence: {prediction['confidence']:.1%}")
        print(f"Score Difference: {prediction['score_difference']:.3f}")
        print("\nClass Probabilities:")
        for label, prob in prediction['probabilities'].items():
            print(f"  {label}: {prob:.1%}")
    
    model = load_model(FILEPATH)
    if model:
        EVALUATE=False
        class_counts, class_word_counts, vocab_size, idf_values = model

        test_text = "A Chinese warship announced live fire exercises in waters some 90 nautical miles from the Zambales coastline yesterday morning, forcing Philippine Coast Guard vessels and dozens of Filipino fishing boats caught inside the designated danger zone to leave the area."
        print()
        prediction = predict(test_text, class_counts, class_word_counts, vocab_size, idf_values, include_bigrams=False, include_trigrams=False, is_log=True)
        print(prediction)

        if EVALUATE:
            accuracy, predictions = evaluate_model(test_docs, test_labels, class_counts, class_word_counts, vocab_size, idf_values, include_bigrams=True, include_trigrams=False)
            print(f"Accuracy: {accuracy:.2%}")
        
        print("=" * 50)
        print("PREDICTION SUMMARY:")
        print(f"Predicted Class: {prediction['prediction'].upper()}")
        print(f"Confidence: {prediction['confidence']:.1%}")
        print(f"Score Difference: {prediction['score_difference']:.3f}")
        print("\nClass Probabilities:")
        for label, prob in prediction['probabilities'].items():
            print(f"  {label}: {prob:.1%}")