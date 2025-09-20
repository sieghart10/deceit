from utils.lemmatization import lemmatize
from utils.contraction import expand_contraction
import re

def normalize(text):
    text = text.lower()
    text = re.sub(r"\W", "", text)
    text = re.sub(r"\s+", "", text)
    return text

# NEGATED_WORDS = [
#     "aint", "arent", "cannot", "cant", "couldnt", "darent", "didnt", "doesnt",
#     "ain't", "aren't", "can't", "couldn't", "daren't", "didn't", "doesn't",
#     "dont", "hadnt", "hasnt", "havent", "isnt", "mightnt", "mustnt", "neither",
#     "don't", "hadn't", "hasn't", "haven't", "isn't", "mightn't", "mustn't",
#     "neednt", "needn't", "never", "none", "nope", "nor", "not", "nothing",
#     "nowhere", "oughtnt", "shant", "shouldnt", "uhuh", "wasnt", "werent",
#     "oughtn't", "shan't", "shouldn't", "uh-uh", "wasn't", "weren't", "without",
#     "wont", "wouldnt", "won't", "wouldn't", "rarely", "seldom", "despite",
#     "no", "n't"
# ]

NEGATED_WORDS = [
    "am not", "are not", "cannot", "could not", "dare not", "did not", "does not",
    "do not", "had not", "has not", "have not", "is not", "might not", "must not", "neither",
    "need not", "never", "none", "nope", "nor", "not", "nothing",
    "nowhere", "ought not", "shall not", "should not", "was not", "were not",
    "without", "will not", "would not", "rarely", "seldom", "despite", "no"
]

def tag_negation(tokens):
    negated = False
    updated = []
    
    for token in tokens:
        norm_token = normalize(token)
        
        if len(norm_token) == 1 and norm_token not in ['a', 'i']:
            continue
        
        if token.lower() in NEGATED_WORDS:
            negated = True
            updated.append(norm_token)
        elif re.search(r"[.!?,;:]", token):
            updated.append(norm_token)
            negated = False
        else:
            updated.append(f"NOT_{norm_token}" if negated else norm_token)
    
    return updated

# STOP_WORDS = [
#     "the", "and", "is", "in", "of", "to", "a", "an", "on", "for", "with",
#     "that", "this", "it", "as", "at", "by", "from", "be", "or", "but", 
#     "are", "was", "were", "been", "has", "had", "have", "do", "does", 
#     "did", "not", "so", "if", "then", "than", "because", "while", "when",
#     "where", "which", "who", "whom", "what", "why", "how", "can", "could",
#     "should", "would", "may", "might", "must", "will", "shall"
# ]
STOP_WORDS = ["the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "is", "which", "at", "on", "it"]

def tokenize(text, special_tokens=False, remove_stopwords=True, use_lemmatization=True):
    tokens = re.sub(r"http\S+|www\.\S+", "", text)
    tokens = expand_contraction(tokens)
    tokens = re.split("[- ]", tokens)
    tokens = re.findall(r"\w+|[.!?,;:]", text)

    if use_lemmatization:
        tokens = [lemmatize(token) for token in tokens]
    
    tokens = tag_negation(tokens)

    if remove_stopwords:
        tokens = [t for t in tokens if normalize(t) not in STOP_WORDS]

    if special_tokens:
        tokens = ["<s>"] + list(map(normalize, tokens)) + ["</s>"]

    tokens = [token for token in tokens if token.strip()]

    return tokens