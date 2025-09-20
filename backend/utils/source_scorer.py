import re
from urllib.parse import urlparse
from typing import Dict, Tuple

class SourceScorer:
    def __init__(self):
        # source reliability scores (0.0 to 1.0)
        # higher scores likely a reliable sources
        self.domain_scores = {
            # PH reliable soruces
            'inquirer.net': 0.9,
            'philstar.com': 0.9,
            'abs-cbn.com': 0.9,
            'gmanetwork.com': 0.9,
            'rappler.com': 0.9,
            'cnnphilippines.com': 0.9,
            'businessworld.com.ph': 0.9,
            'manilatimes.net': 0.85,
            'tribune.net.ph': 0.8,
            'pna.gov.ph': 0.95,
            
            # international trusted sources
            'bbc.com': 0.95,
            'reuters.com': 0.95,
            'apnews.com': 0.95,
            'cnn.com': 0.85,
            'nytimes.com': 0.9,
            'theguardian.com': 0.9,
            'washingtonpost.com': 0.9,
            'npr.org': 0.9,
            
            # social media platforms (lower reliability)
            'facebook.com': 0.3,
            'twitter.com': 0.3,
            'instagram.com': 0.25,
            'tiktok.com': 0.2,
            'youtube.com': 0.35,
            
            # some fake news sources
            'breakingnewsaz.today': 0.5,
            'breakingnews24.com': 0.1,
            'fakenewssite.com': 0.05,
            'clickbait-news.com': 0.1,
            
            # some blogs and personal sites (medium reliability)
            'medium.com': 0.6,
            'blogspot.com': 0.4,
            'wordpress.com': 0.4,
            
            # some government and official sources
            'gov.ph': 0.95,
            'who.int': 0.95,
            'cdc.gov': 0.95,
        }
        
        # domain patterns for scoring
        self.domain_patterns = {
            r'\.gov\.ph$': 0.95,
            r'\.edu\.ph$': 0.85,
            r'\.org\.ph$': 0.75,
            r'\.gov$': 0.9,
            r'\.edu$': 0.85,
            r'\.org$': 0.7,
        }
        
        # some keywords that might come from unreliable sources
        self.unreliable_keywords = [
            'breaking', 'shocking', 'exclusive', 'leaked', 'secret',
            'exposed', 'revealed', 'hidden', 'conspiracy', 'truth',
            'clickbait', 'viral', 'trending', 'you-wont-believe'
        ]
        
        # some keywords that might come from reliable sources
        # self.reliable_keywords = [
        #     'official', 'statement', 'press-release', 'announcement',
        #     'report', 'study', 'research', 'analysis', 'investigation'
        # ]

    def get_domain_score(self, url: str) -> float:
        try:
            parsed = urlparse(url.lower())
            domain = parsed.netloc.replace('www.', '')
            
            if domain in self.domain_scores:
                return self.domain_scores[domain]
            
            for pattern, score in self.domain_patterns.items():
                if re.search(pattern, domain):
                    return score
            
            # default score for unknown domains
            return 0.5
            
        except Exception:
            return 0.5

    def analyze_url_structure(self, url: str) -> float:
        url_lower = url.lower()
        score = 0.5  # base score
        
        # penalize
        for keyword in self.unreliable_keywords:
            if keyword in url_lower:
                score -= 0.05
        
        # boost
        # for keyword in self.reliable_keywords:
        #     if keyword in url_lower:
        #         score += 0.05
        
        # penalize for excessive hyphens or numbers
        if url_lower.count('-') > 5:
            score -= 0.1
        if len(re.findall(r'\d', url_lower)) > 10:
            score -= 0.05
        
        # penalize for suspicious TLDs
        suspicious_tlds = ['.tk', '.ml', '.ga', '.cf', '.click', '.info']
        for tld in suspicious_tlds:
            if url_lower.endswith(tld):
                score -= 0.2
                break
        
        return max(0.0, min(1.0, score))

    def calculate_source_confidence(self, url: str, page_title: str = "", content_preview: str = "") -> Dict:
        domain_score = self.get_domain_score(url)
        url_structure_score = self.analyze_url_structure(url)
        
        title_score = self.analyze_text_reliability(page_title)
        content_score = self.analyze_text_reliability(content_preview)
        
        # weighted average
        weights = {
            'domain': 0.4,
            'url_structure': 0.2,
            'title': 0.2,
            'content': 0.2
        }
        
        overall_score = (
            domain_score * weights['domain'] +
            url_structure_score * weights['url_structure'] +
            title_score * weights['title'] +
            content_score * weights['content']
        )
        
        return {
            'overall_score': round(overall_score, 3),
            'domain_score': round(domain_score, 3),
            'url_structure_score': round(url_structure_score, 3),
            'title_score': round(title_score, 3),
            'content_score': round(content_score, 3),
            'domain': urlparse(url).netloc.replace('www.', ''),
            'confidence_level': self.get_confidence_level(overall_score)
        }

    def analyze_text_reliability(self, text: str) -> float:
        if not text:
            return 0.5
        
        text_lower = text.lower()
        score = 0.5
        
        unreliable_count = sum(1 for keyword in self.unreliable_keywords 
                              if keyword in text_lower)
        score -= unreliable_count * 0.05
        
        # reliable_count = sum(1 for keyword in self.reliable_keywords 
        #                     if keyword in text_lower)
        # score += reliable_count * 0.05
        
        # check for excessive capitalization
        # if len(re.findall(r'[A-Z]{3,}', text)) > 3:
        #     score -= 0.1
        
        # check for excessive punctuation
        # if text.count('!') > 3 or text.count('?') > 3:
        #     score -= 0.05
        
        return max(0.0, min(1.0, score))

    def get_confidence_level(self, score: float) -> str:
        if score >= 0.8:
            return "very_high"
        elif score >= 0.6:
            return "high"
        elif score >= 0.4:
            return "medium"
        elif score >= 0.2:
            return "low"
        else:
            return "very_low"

    def boost_prediction_confidence(self, original_confidence: float, source_score: float, prediction: str) -> Tuple[float, str]:
        if source_score >= 0.7:  # highly reliable source
            if prediction == 'real':
                # boost confidence for real news from reliable sources
                boost_factor = 1.0 + (source_score - 0.7) * 0.5
            else:
                # reduce confidence for fake prediction from reliable sources
                boost_factor = 1.0 - (source_score - 0.7) * 0.2
        elif source_score <= 0.3:  # unreliable source
            if prediction == 'fake':
                # boost confidence for fake news from unreliable sources
                boost_factor = 1.0 + (0.3 - source_score) * 0.4
            else:
                # reduce confidence for real prediction from unreliable sources
                boost_factor = 1.0 - (0.3 - source_score) * 0.3
        else:
            # neutral sources do not affect confidence
            boost_factor = 1.0
        
        # apply boost with limits
        new_confidence = min(0.99, max(0.01, original_confidence * boost_factor))
        
        if boost_factor > 1.05:
            explanation = f"Confidence boosted due to {self.get_source_reliability_text(source_score)} source"
        elif boost_factor < 0.95:
            explanation = f"Confidence reduced due to {self.get_source_reliability_text(source_score)} source"
        else:
            explanation = "Source reliability is neutral"
        
        return new_confidence, explanation

    def get_source_reliability_text(self, score: float) -> str:
        if score >= 0.8:
            return "highly reliable"
        elif score >= 0.6:
            return "reliable"
        elif score >= 0.4:
            return "moderately reliable"
        elif score >= 0.2:
            return "questionable"
        else:
            return "unreliable"

if __name__ == "__main__":
    scorer = SourceScorer()
    
    test_cases = [
        {
            'url': 'https://www.inquirer.net/politics/latest-news',
            'title': 'Official Statement from Government',
            'content': 'The Department of Health announced new guidelines...'
        },
        {
            'url': 'https://facebook.com/posts/123456',
            'title': 'SHOCKING! SECRET REVEALED!',
            'content': 'You won\'t believe what happened next!!!'
        },
        {
            'url': 'https://breakingnews24.com/exposed-scandal',
            'title': 'BREAKING: Exclusive leaked documents expose conspiracy',
            'content': 'Hidden truth finally revealed after years...'
        },
        {
            'url': 'https://pna.gov.ph/articles/official-announcement',
            'title': 'Press Release: New Policy Implementation',
            'content': 'The administration announces the implementation of...'
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"Test Case {i}")
        print(f"URL: {case['url']}")
        
        result = scorer.calculate_source_confidence(
            case['url'], case['title'], case['content']
        )
        
        print(f"Overall Score: {result['overall_score']}")
        print(f"Domain: {result['domain']}")
        print(f"Confidence Level: {result['confidence_level']}")
        print(f"Domain Score: {result['domain_score']}")
        print(f"URL Structure Score: {result['url_structure_score']}")
        print(f"Title Score: {result['title_score']}")
        print(f"Content Score: {result['content_score']}")
        
        original_conf = 0.75
        prediction = 'fake'
        new_conf, explanation = scorer.boost_prediction_confidence(
            original_conf, result['overall_score'], prediction
        )
        
        print(f"\nPrediction Confidence Boost:")
        print(f"Original: {original_conf:.3f}")
        print(f"Boosted: {new_conf:.3f}")
        print(f"Explanation: {explanation}")