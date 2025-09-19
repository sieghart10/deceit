from collections import Counter
from utils.tokenizer import tokenize
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

def train_naive_bayes(documents, labels):
    print("Training Naive Bayes classifier...")
    vocab_size = set()
    
    class_counter = {} # P(class) = number of docs in class ∣ total docs
    class_word_counter = {} # P(word ∣ class) = count of word in class ∣ total words in class
    
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
        
        for token in tokens:
            class_word_counter[label][token] = class_word_counter[label].get(token, 0) + 1
        
        if show_training_progress and (i % update_freq == 0 or i == total_docs - 1):
            show_progress(i + 1, total_docs, "Training classifier")
    
    if show_training_progress:
        print(f"\n  ✓ Trained on {total_docs:,} documents")
    
    return class_counter, class_word_counter, len(vocab_size)

def predict(text, class_counts, class_word_counts, vocab_size, is_log=True):
    # P(c∣ d) ∝ P(c) ⋅ P(d ∣ c)
    # log P(c ∣ d) ∝ log P(c) + ∑ tokens  ​log P(token ∣ c)

    tokens = tokenize(text)
    total_docs = sum(class_counts.values())
    scores = {}
    
    if is_log:
        print(f"Tokens: {tokens}")
    
    for label in class_counts.keys():
        prob = math.log(class_counts[label] / total_docs)
        if is_log:
            print(f"--> logprior({label}): log({class_counts[label]} / {total_docs}) = {prob}")
        
        for token in tokens:
            token_count = class_word_counts[label].get(token, 0)
            total_tokens = sum(class_word_counts[label].values())
            
            # laplace smoothing
            likelihood = math.log((token_count + 1) / (total_tokens + vocab_size))
            if is_log:
                print(f"---> {token}: log({token_count + 1} / {total_tokens + vocab_size}) = {likelihood}")
            
            prob += likelihood
        
        if is_log:
            print(f"{label} final score: {prob}")
        scores[label] = prob
    
    predicted_class = max(scores, key=scores.get)
    
    # Calculate confidence metrics
    real_score = scores.get('real', float('-inf'))
    fake_score = scores.get('fake', float('-inf'))
    
    score_difference = abs(real_score - fake_score)
    
    max_score = max(scores.values())
    exp_scores = {label: math.exp(score - max_score) for label, score in scores.items()}
    total_exp = sum(exp_scores.values())
    probabilities = {label: exp_score/total_exp for label, exp_score in exp_scores.items()}
    
    return {
        'prediction': predicted_class,
        'raw_scores': scores,
        'score_difference': score_difference,
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

def evaluate_model(test_docs, test_labels, class_counts, class_word_counts, vocab_size):
    print("Evaluating model...")
    correct = 0
    total = len(test_docs)
    show_eval_progress = total > 50
    update_freq = max(1, total // 100) if show_eval_progress else total
    
    predictions = []
    for i, (doc, true_label) in enumerate(zip(test_docs, test_labels)):
        predicted_result = predict(doc, class_counts, class_word_counts, vocab_size, is_log=False)
        predicted_label = predicted_result['prediction']
        
        predictions.append((doc[:50] + "...", true_label, predicted_result))
        
        if predicted_label == true_label:
            correct += 1
        
        if show_eval_progress and (i % update_freq == 0 or i == total - 1):
            show_progress(i + 1, total, "Evaluating")
    
    if show_eval_progress:
        print(f"\n  ✓ Evaluated {total:,} documents")
    
    accuracy = correct / total if total > 0 else 0
    return accuracy, predictions

def analyze_prediction(text, class_counts, class_word_counts, vocab_size):
    print(f"Analyzing: '{text}'")
    print("=" * 50)
    result = predict(text, class_counts, class_word_counts, vocab_size, is_log=True)
    
    print("=" * 50)
    print("PREDICTION SUMMARY:")
    print(f"Predicted Class: {result['prediction'].upper()}")
    print(f"Confidence: {result['confidence']:.1%}")
    print(f"Score Difference: {result['score_difference']:.3f}")
    print("\nClass Probabilities:")
    for label, prob in result['probabilities'].items():
        print(f"  {label}: {prob:.1%}")
    
    print("\nInterpretation:")
    if result['confidence'] > 0.8:
        print("🟢 High confidence prediction")
    elif result['confidence'] > 0.6:
        print("🟡 Medium confidence prediction")
    else:
        print("🔴 Low confidence prediction - consider manual review")
    
    return result

VERSION = 1
FILEPATH = f"bow_naive_bayes_model{VERSION}.pkl"

def save_model(class_counts, class_word_counts, vocab_size, filepath):
    print("Saving model...")
    save_dir = 'trained_models'
    os.makedirs(save_dir, exist_ok=True)
    full_path = os.path.join(save_dir, filepath)

    model_data = {
        'class_counts': class_counts,
        'class_word_counts': class_word_counts,
        'vocab_size': vocab_size
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
    
    print(f"  ✓ Model loaded from {full_path}")
    return model_data['class_counts'], model_data['class_word_counts'], model_data['vocab_size']

if __name__ == "__main__":
    set_random_seeds(RANDOM_SEED)
    TRAIN = True

    df_real = pd.read_csv("data/articles.csv")
    df_fake = pd.read_csv("data/rappler_articles.csv")
    
    real_documents = list(zip(df_real['content'], ['real'] * len(df_real)))
    fake_documents = list(zip(df_fake['content'], ['fake'] * len(df_fake)))
    print(f"  ✓ Loaded {len(real_documents):,} real and {len(fake_documents):,} fake articles")
    
    print(f"\n=== Fake News Detection Using Bag of Words + Naive Bayes ===\n")
    
    train_docs, train_labels, test_docs, test_labels = train_test_split(
        real_documents, fake_documents, test_ratio=0.2
    )
    print(f"Train label distribution: {Counter(train_labels)}")
    print(f"Test label distribution: {Counter(test_labels)}")
    
    if TRAIN:
        class_counts, class_word_counts, vocab_size = train_naive_bayes(train_docs, train_labels)
        save_model(class_counts, class_word_counts, vocab_size, FILEPATH)
        
        print(f"Vocabulary size: {vocab_size:,}")
        print(f"Class distribution: {class_counts}\n")
        
        print("=== Model Evaluation ===")
        accuracy, predictions = evaluate_model(
            test_docs, test_labels, class_counts, class_word_counts, vocab_size
        )
        
        print(f"Accuracy: {accuracy:.2%}\n")
        
        print("Sample predictions (first 5):")
        for doc_preview, true_label, predicted_result in predictions[:5]:
            predicted_label = predicted_result['prediction']
            status = "✓" if true_label == predicted_label else "✗"
            confidence = predicted_result['confidence']
            print(f"{status} '{doc_preview}' | True: {true_label} | Predicted: {predicted_label} ({confidence:.1%})")
    else:
        # Load existing model
        model = load_model(FILEPATH)
        if model:
            class_counts, class_word_counts, vocab_size = model
            
            print(f"Vocabulary size: {vocab_size:,}")
            print(f"Class distribution: {class_counts}\n")
            
            EVALUATE = True  # set False to skip evaluation
            if EVALUATE:
                accuracy, predictions = evaluate_model(
                    test_docs, test_labels, class_counts, class_word_counts, vocab_size
                )
                print(f"Accuracy: {accuracy:.2%}\n")
    
    # Testing with detailed analysis
    print("\n=== Detailed Prediction Example ===")
    test_text = "A Chinese warship announced live fire exercises in waters some 90 nautical miles from the Zambales coastline yesterday morning, forcing Philippine Coast Guard vessels and dozens of Filipino fishing boats caught inside the designated danger zone to leave the area."
    prediction = analyze_prediction(test_text, class_counts, class_word_counts, vocab_size)

    # print("Individual predictions:")
    # for doc_preview, true_label, predicted_result in predictions:
    #     predicted_label = predicted_result['prediction']
    #     status = "✓" if true_label == predicted_label else "✗"
    #     print(f"{status} '{doc_preview}' | True: {true_label} | Predicted: {predicted_result}")