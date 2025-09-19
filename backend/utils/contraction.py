import re

def normalize_quotes_and_apostrophes(text):
    # dictionary of Unicode characters to normalize
    quote_mappings = {
        '\u2019': "'",  # ' (RIGHT SINGLE QUOTATION MARK)
        '\u2018': "'",  # ' (LEFT SINGLE QUOTATION MARK) 
        
        # Grave accent (backtick)
        '\u0060': "'",  # ` (GRAVE ACCENT)
        
        # Acute accent
        '\u00B4': "'",  # ´ (ACUTE ACCENT)
        
        # Prime symbols
        '\u2032': "'",  # ′ (PRIME)
        
        # Double quotes
        '\u201C': '"',  # " (LEFT DOUBLE QUOTATION MARK)
        '\u201D': '"',  # " (RIGHT DOUBLE QUOTATION MARK)
        '\u201E': '"',  # „ (DOUBLE LOW-9 QUOTATION MARK)
        '\u201A': "'",  # ‚ (SINGLE LOW-9 QUOTATION MARK)
        
        # Other apostrophe-like characters
        '\u02BC': "'",  # ʼ (MODIFIER LETTER APOSTROPHE)
        '\u02C8': "'",  # ˈ (MODIFIER LETTER VERTICAL LINE)
    }
    
    for unicode_char, ascii_char in quote_mappings.items():
        text = text.replace(unicode_char, ascii_char)
    
    return text

def load_contractions_dict(filepath):
    contractions = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    contraction, expansions = line.split(':', 1)
                    contraction = contraction.strip()
                    contraction = normalize_quotes_and_apostrophes(contraction)
                    expansion_options = [exp.strip() for exp in expansions.split('|')]
                    contractions[contraction.lower()] = expansion_options[0].strip()
        
        print(f"Loaded {len(contractions)} contraction mappings from {filepath}")
    except FileNotFoundError:
        print(f"Contractions file {filepath} not found. Using built-in contractions.")
        # fallback
        contractions = {
            "don't": "do not",
            "can't": "cannot",
            "won't": "will not",
            "shouldn't": "should not",
            "wouldn't": "would not",
            "i'm": "i am",
            "isn't": "is not",
            "aren't": "are not",
            "wasn't": "was not",
            "weren't": "were not",
            "didn't": "did not",
            "couldn't": "could not",
            "mustn't": "must not",
            "mightn't": "might not",
            "shan't": "shall not",
            "n't": " not"
        }
    except Exception as e:
        print(f"Error loading contractions file: {e}")
        contractions = {}
    
    return contractions

def expand_contractions(text, contractions_dict):
    text = normalize_quotes_and_apostrophes(text)
    
    possessive_pattern = r"\b(\w+)'s\b"
    def replace_possessive(match):
        noun = match.group(1)
        if noun.lower() in ['he', 'she', 'it', 'that', 'what', 'who', 'there', 'here']:
            return f"{noun} is"
        else:
            return f"{noun} is"
    
    text = re.sub(possessive_pattern, replace_possessive, text, flags=re.IGNORECASE)
    
    for contraction, expansion in contractions_dict.items():
        if contraction == "<noun>'s":
            continue
        if contraction == "n't":
            pattern = r"\b(\w+)n't\b"
            text = re.sub(pattern, r'\1 not', text, flags=re.IGNORECASE)
        else:
            pattern = r'\b' + re.escape(contraction) + r'\b'
            text = re.sub(pattern, expansion, text, flags=re.IGNORECASE)
    
    return text

CONTRACTIONS = load_contractions_dict('data/contractions-en.txt')

def expand_contraction(text):
    return expand_contractions(text, CONTRACTIONS)
