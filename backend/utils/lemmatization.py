def load_lemmatization_dict(filepath):
    lemma_dict = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '\t' in line:
                    parts = line.split('\t')
                    if len(parts) == 2:
                        base_form, inflected_form = parts
                        lemma_dict[inflected_form.lower()] = base_form.lower()
        print(f"Loaded {len(lemma_dict)} lemmatization mappings from {filepath}")
    except FileNotFoundError:
        print(f"Lemmatization file {filepath} not found. Using fallback rules only.")
    except Exception as e:
        print(f"Error loading lemmatization file: {e}")
    
    return lemma_dict

LEMMATIZATION_DICT = load_lemmatization_dict('data/lemmatization-en.txt')

def lemmatize(word):
    word_lower = word.lower()
    
    if word_lower in LEMMATIZATION_DICT:
        return LEMMATIZATION_DICT[word_lower]
    
    return word_lower