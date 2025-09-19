from collections import defaultdict, Counter
from utils.tokenizer import tokenize
import pandas as pd

def to_vec(text):
    return Counter(tokenize(text))

def create_bow_matrix(documents, labels):
    bow = defaultdict(Counter)
    
    for i, doc in enumerate(documents):
        parsed_doc = to_vec(doc)
        bow[f'doc-{i}'] = parsed_doc
    
    bow_df = pd.DataFrame(bow, dtype='Int64').fillna(0).T
    return bow_df