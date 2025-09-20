from utils.tokenizer import tokenize

def generate_ngrams_for_tfidf(tokens, n=2):
    ngrams = []
    for i in range(len(tokens) - n + 1):
        ngram = '_'.join(tokens[i:i+n])  # underscore for unique n-gram identifier
        ngrams.append(ngram)
    return ngrams

def tokenize_with_ngrams(text, include_bigrams=True, include_trigrams=True):
    tokens = tokenize(text)
    
    # combined feature list
    features = tokens.copy()
    
    if include_bigrams:
        bigrams = generate_ngrams_for_tfidf(tokens, 2)
        features.extend(bigrams)
    
    if include_trigrams:
        trigrams = generate_ngrams_for_tfidf(tokens, 3)
        features.extend(trigrams)
    
    return features

# test_text = "A Chinese warship announced live fire exercises in waters some 90 nautical miles from the Zambales coastline yesterday morning, forcing Philippine Coast Guard vessels and dozens of Filipino fishing boats caught inside the designated danger zone to leave the area."
# print(tokenize_with_ngrams(test_text))
