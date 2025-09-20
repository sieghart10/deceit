from collections import Counter
from utils.tokenizer import tokenize
from utils.progress import show_progress
from utils.matrix import create_bow_matrix
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

def calculate_idf(documents, use_log=True):
    N = len(documents) # num of docs
    idf = {}
    all_tokens = set()
    
    print(f"Tokenizing {N:,} documents...")
    tokenized_docs = []
    show_progress_flag = N > 100
    update_freq = max(1, N // 100) if show_progress_flag else N

    for i, doc in enumerate(documents):
        tokens = tokenize(doc)
        tokenized_docs.append(tokens)
        all_tokens.update(tokens)

        if show_progress_flag and (i % update_freq == 0 or i == N - 1):
            show_progress(i + 1, N, "Tokenizing documents")
        
    if show_progress_flag:
        print(f"\n  ✓ Tokenized {N:,} documents, found {len(all_tokens):,} unique features")

    print("Calculating IDF values...")
    token_count = 0
    total_tokens = len(all_tokens)
    show_idf_progress = total_tokens > 1000
    update_freq_idf = max(1, total_tokens // 100) if show_idf_progress else total_tokens

    for term in all_tokens:
        docs_with_term = sum(1 for tokens in tokenized_docs if term in tokens)
        
        if use_log:
            idf[term] = math.log((N + 1) / (docs_with_term + 1))
        else:
            idf[term] = (N + 1) / (docs_with_term + 1)
    
        token_count += 1

        if show_idf_progress and (token_count % update_freq_idf == 0 or token_count == total_tokens):
            show_progress(token_count, total_tokens, "Calculating IDF")

    if show_idf_progress:
        print(f"\n  ✓ Calculated IDF for {total_tokens:,} features")

    return idf, tokenized_docs

def calculate_tfidf(documents):
    # calculate IDF
    idf_values, tokenized_docs = calculate_idf(documents)
    
    print("Calculating TF-IDF matrix...")
    tfidf_matrix = []
    doc_count = len(tokenized_docs)
    show_tfidf_progress = doc_count > 100
    update_freq = max(1, doc_count // 100) if show_tfidf_progress else doc_count
    
    for i, tokens in enumerate(tokenized_docs):
        # calculate TF for this document
        tf = calculate_tf(tokens)
        
        # calculate TF-IDF for each term
        doc_tfidf = {}
        for term in tf:
            doc_tfidf[term] = tf[term] * idf_values.get(term, 0)
        
        tfidf_matrix.append(doc_tfidf)
    
        if show_tfidf_progress and (i % update_freq == 0 or i == doc_count - 1):
            show_progress(i + 1, doc_count, "Computing TF-IDF")

    if show_tfidf_progress:
        print(f"\n  ✓ Computed TF-IDF matrix for {doc_count:,} documents")
    
    return tfidf_matrix, idf_values

def train_naive_bayes_tfidf(documents, labels):
    print("Training TF-IDF Naive Bayes Model")
    vocab_size = set()
    class_counter = {}
    class_word_counter = {}
    
    # calculate TF-IDF for all documents
    tfidf_matrix, idf_values = calculate_tfidf(documents)

    print("Training Naive Bayes classifier...")
    total_docs = len(documents)
    show_training_progress = total_docs > 100
    update_freq = max(1, total_docs // 100) if show_training_progress else total_docs
    
    for i, (doc, label) in enumerate(zip(documents, labels)):
        tokens = tokenize(doc)
        vocab_size.update(tokens)
        
        if label not in class_counter:
            class_counter[label] = 0
            class_word_counter[label] = {}
        
        class_counter[label] += 1
        
        # TF-IDF weights
        doc_tfidf = tfidf_matrix[i]
        for token in tokens:
            weight = doc_tfidf.get(token, 0)
            class_word_counter[label][token] = class_word_counter[label].get(token, 0) + weight

        if show_training_progress and (i % update_freq == 0 or i == total_docs - 1):
            show_progress(i + 1, total_docs, "Training classifier")

    if show_training_progress:
        print(f"\n  ✓ Trained on {total_docs:,} documents")

    return class_counter, class_word_counter, len(vocab_size), idf_values

def predict(text, class_counts, class_word_counts, vocab_size, idf_values, is_log=False):
    tokens = tokenize(text)
    total_docs = sum(class_counts.values())
    scores = {}
    
    if is_log:
        print(f"Tokens: {tokens}")
    
    # calculate TF for query document
    tf = calculate_tf(tokens)
    query_tfidf = {term: tf[term] * idf_values.get(term, 0) for term in tf}
    print(query_tfidf)
    for label in class_counts.keys():
        prob = math.log(class_counts[label] / total_docs)
        
        if is_log:
            print(f"--> logprior({label}): log({class_counts[label]} / {total_docs}) = {prob}")

        for token in tokens:
            token_weight = class_word_counts[label].get(token, 0)
            total_weight = sum(class_word_counts[label].values())
            query_weight = query_tfidf.get(token, 0)
            
            # likelihood = math.log((token_weight + 1) / (total_weight + vocab_size))
            likelihood = math.log((token_weight + 1) / (total_weight + vocab_size)) * query_weight
            
            if is_log:
                print(f"---> {token}: {likelihood}")

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

def evaluate_model(test_docs, test_labels, class_counts, class_word_counts, vocab_size, idf_values):
    print("Evaluating model...")
    score = 0
    total = len(test_docs)
    show_eval_progress = total > 50
    update_freq = max(1, total // 100) if show_eval_progress else total
    
    predictions = []
    for i, (doc, true_label) in enumerate(zip(test_docs, test_labels)):
        predicted_result = predict(doc, class_counts, class_word_counts, vocab_size, idf_values)
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

def analyze_prediction(text, class_counts, class_word_counts, vocab_size, idf_values, is_log=True):
    prediction = predict(text, class_counts, class_word_counts, vocab_size, idf_values, is_log)

    print("PREDICTION SUMMARY:")
    print(f"Predicted Class: {prediction['prediction'].upper()}")
    print(f"Confidence: {prediction['confidence']:.1%}")
    print(f"Score Difference: {prediction['score_difference']:.3f}")
    print("\nClass Probabilities:")
    for label, prob in prediction['probabilities'].items():
        print(f"  {label}: {prob:.1%}")

    print("\nInterpretation:")
    if prediction['confidence'] > 0.8:
        print("🟢 High confidence prediction")
    elif prediction['confidence'] > 0.6:
        print("🟡 Medium confidence prediction")
    else:
        print("🔴 Low confidence prediction - consider manual review")

    return prediction

VERSON = 1
FILEPATH = f'tf_idf_naive_bayes_model_v{VERSON}.pkl'

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
    set_random_seeds(RANDOM_SEED)
    TRAIN = False
    
    df_real = pd.read_csv("data/articles.csv")
    df_real2 = pd.read_csv("data/inquirer-articles.csv")
    df_fake = pd.read_csv("data/rappler_articles.csv")
    df_fake2 = pd.read_csv("data/breakingnews-articles-new.csv")

    df_real = pd.concat([df_real, df_real2], ignore_index=True)
    df_fake = pd.concat([df_fake, df_fake2], ignore_index=True)
    
    real_documents = list(zip(df_real['content'], ['real'] * len(df_real)))
    fake_documents = list(zip(df_fake['content'], ['fake'] * len(df_fake)))
    print(f"  ✓ Loaded {len(real_documents):,} real and {len(fake_documents):,} fake articles")
    
    print(f"=== Fake News Detection Using TF-IDF + Naive Bayes ===\n")
    
    train_docs, train_labels, test_docs, test_labels = train_test_split(real_documents, fake_documents, test_ratio=0.2)
    print(f"Train label distribution: {Counter(train_labels)}")
    print(f"Test label distribution: {Counter(test_labels)}")
    
    # print("\n=== Bag of Words Matrix (First 5 documents) ===")
    # bow_matrix = create_bow_matrix(train_docs[:10], train_labels[:10])
    # print(bow_matrix)
    # print(f"Matrix shape: {bow_matrix.shape}\n")

    text = "post shows a photo of Kabataan Representative Renee Co and embattled Ako Bicol Representative Zaldy Co, implying that they are close relatives"
    # text = "The Department of Education (DepEd) has directed all regional and division offices to submit detailed reports on uncompleted or “ghost” school buildings, stressing accountability in infrastructure projects and the need to ensure safe classrooms for learners. In a memorandum dated September 12, 2025, Assistant Secretary for Human Resource and Organizational Development and Education Facilities Division Aurelio Paulo R. Bartolome reminded field offices of their duty to uphold transparency following recent findings of irregularities in school construction. Regional directors, schools division superintendents, district supervisors, and DepEd engineers were specifically tasked to identify and report anomalous cases such as prolonged stoppage of construction, incomplete delivery, or structural defects."
    if TRAIN:
        class_counts, class_word_counts, vocab_size, idf_values = train_naive_bayes_tfidf(train_docs, train_labels)
        save_model(class_counts, class_word_counts, vocab_size, idf_values, FILEPATH)

        print(f"Class distribution: {class_counts}")
        
        print(f"Vocabulary size: {vocab_size}")
        print(f"Class distribution: {class_counts}\n")

        print("=== Model Evaluation ===")
        accuracy, predictions = evaluate_model(test_docs, test_labels, class_counts, class_word_counts, vocab_size, idf_values)
        print(f"Accuracy: {accuracy:.2%}\n")
        
        print("=== Testing Example ===")
        prediction = analyze_prediction(text, class_counts, class_word_counts, vocab_size, idf_values)
        print(prediction)

    else:
        model = load_model(FILEPATH)
        if model:
            EVALUATE=False
            class_counts, class_word_counts, vocab_size, idf_values = model
            prediction = analyze_prediction(text, class_counts, class_word_counts, vocab_size, idf_values, is_log=True)
            print(prediction)

            if EVALUATE:
                accuracy, predictions = evaluate_model(test_docs, test_labels, class_counts, class_word_counts, vocab_size, idf_values)
                print(f"Accuracy: {accuracy:.2%}")
            