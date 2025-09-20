import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import logging
from typing import Optional
from utils.tesseract import image_to_text
from utils.tokenizer import tokenize
import re

# Set up logging
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone17,1; CPU iPhone OS 18_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:15.0) Gecko/20100101 Firefox/15.0.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

def scrape_link(url: str, timeout: int = 10) -> Optional[str]:
    """
    Scrape main content from a URL
    
    Args:
        url: The URL to scrape
        timeout: Request timeout in seconds
    
    Returns:
        Extracted text content or None if failed
    """
    try:
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            logger.error(f"Invalid URL: {url}")
            return None
        
        # Set headers to avoid bot detection
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Make request
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "meta", "link", "noscript"]):
            script.decompose()
        
        # Try different methods to extract main content
        text_content = ""
        
        # Method 1: Look for article tags
        article = soup.find('article')
        if article:
            text_content = article.get_text()
        
        # Method 2: Look for main content areas
        if not text_content:
            main_content = soup.find('main') or soup.find('div', {'class': re.compile('content|article|post|entry|main', re.I)})
            if main_content:
                text_content = main_content.get_text()
        
        # Method 3: Look for specific news site patterns
        if not text_content:
            # Common patterns for news sites
            content_selectors = [
                {'class': re.compile('article-body|story-body|post-content|entry-content', re.I)},
                {'id': re.compile('article|content|main|story', re.I)},
                {'itemprop': 'articleBody'},
                {'role': 'main'}
            ]
            
            for selector in content_selectors:
                content_div = soup.find('div', selector)
                if content_div:
                    text_content = content_div.get_text()
                    break
        
        # Method 4: Extract all paragraphs if no specific content area found
        if not text_content:
            paragraphs = soup.find_all('p')
            if paragraphs:
                # Filter out very short paragraphs (likely navigation/footer text)
                valid_paragraphs = [p.get_text() for p in paragraphs if len(p.get_text().strip()) > 50]
                if valid_paragraphs:
                    text_content = ' '.join(valid_paragraphs)
        
        # Method 5: Fallback to body text
        if not text_content:
            body = soup.find('body')
            if body:
                text_content = body.get_text()
        
        # Clean the extracted text
        if text_content:
            text_content = tokenize(text_content)
            
            # Check if we got meaningful content
            if len(text_content) < 100:
                logger.warning(f"Extracted text too short from {url}: {len(text_content)} characters")
                return None
            
            return text_content
        
        logger.warning(f"No content extracted from {url}")
        return None
        
    except requests.RequestException as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error scraping {url}: {e}")
        return None

def scrape_fb_content(post_container: str) -> Optional[str]:
    """
    Scrape Facebook post content from HTML container
    
    Args:
        post_container: HTML string of the Facebook post container
    
    Returns:
        Extracted text content or None if failed
    """
    try:
        # Parse the HTML container
        soup = BeautifulSoup(post_container, 'html.parser')
        
        extracted_texts = []
        
        # Method 1: Look for Facebook-specific content areas
        # Facebook uses various classes for post content
        content_selectors = [
            {'data-ad-rendering-role': 'story_message'},
            {'role': 'article'},
            {'class': re.compile('userContent|story_body_container|mtm', re.I)},
            # Modern Facebook uses obfuscated class names starting with 'x'
            {'class': re.compile('x[0-9a-z]+', re.I)}
        ]
        
        for selector in content_selectors:
            content_areas = soup.find_all(['div', 'span', 'p'], selector)
            for area in content_areas:
                text = area.get_text().strip()
                if text and len(text) > 20:  # Filter out very short text
                    extracted_texts.append(text)
        
        # Method 2: Extract all meaningful text if specific selectors don't work
        if not extracted_texts:
            # Get all text-containing elements
            text_elements = soup.find_all(['p', 'span', 'div'])
            for element in text_elements:
                # Skip elements with many nested children (likely containers)
                if len(element.find_all()) > 5:
                    continue
                
                text = element.get_text().strip()
                # Filter out UI elements and very short text
                if text and len(text) > 20 and not any(skip in text.lower() for skip in ['like', 'comment', 'share', 'see more', 'view', 'reply']):
                    extracted_texts.append(text)
        
        # Method 3: Look for images and extract text from them
        images = soup.find_all('img')
        for img in images:
            # Skip small images (likely icons)
            if img.get('width') and int(img.get('width', 0)) < 100:
                continue
            if img.get('height') and int(img.get('height', 0)) < 100:
                continue
            
            # Get image URL
            img_url = img.get('src') or img.get('data-src')
            if img_url:
                try:
                    # Download and process image
                    response = requests.get(img_url, timeout=5)
                    if response.status_code == 200:
                        # Here you would use image_to_text to extract text
                        # For now, we'll just note that there's an image
                        logger.info(f"Found image in Facebook post: {img_url}")
                        # text_from_image = image_to_text(response.content)
                        # if text_from_image:
                        #     extracted_texts.append(f"[Image text]: {text_from_image}")
                except Exception as e:
                    logger.warning(f"Failed to process image: {e}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_texts = []
        for text in extracted_texts:
            cleaned = tokenize(text)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                unique_texts.append(cleaned)
        
        # Combine all extracted text
        if unique_texts:
            combined_text = ' '.join(unique_texts)
            
            # Final validation
            if len(combined_text) < 50:
                logger.warning(f"Extracted Facebook content too short: {len(combined_text)} characters")
                return None
            
            return combined_text
        
        logger.warning("No content extracted from Facebook post container")
        return None
        
    except Exception as e:
        logger.error(f"Error parsing Facebook content: {e}")
        return None

def extract_text_from_html(html_content: str) -> Optional[str]:
    """
    Generic HTML text extraction
    
    Args:
        html_content: Raw HTML string
    
    Returns:
        Extracted text or None if failed
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'meta', 'link', 'noscript']):
            element.decompose()
        
        # Get text
        text = soup.get_text()
        
        # Clean text
        text = tokenize(text)
        
        if text and len(text) > 50:
            return text
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting text from HTML: {e}")
        return None

# Additional utility functions for specific news sites
def scrape_rappler(url: str) -> Optional[str]:
    """Special handler for Rappler articles"""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Rappler-specific selectors
        article = soup.find('div', {'class': 'post-single__content'}) or \
                 soup.find('div', {'class': 'story-content'})
        
        if article:
            return tokenize(article.get_text())
        
        return scrape_link(url)  # Fallback to generic scraper
        
    except Exception as e:
        logger.error(f"Error scraping Rappler article: {e}")
        return None

def scrape_inquirer(url: str) -> Optional[str]:
    """Special handler for Philippine Inquirer articles"""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Inquirer-specific selectors
        article = soup.find('div', {'id': 'article-content'}) or \
                 soup.find('div', {'class': 'article-content'})
        
        if article:
            return tokenize(article.get_text())
        
        return scrape_link(url)  # Fallback to generic scraper
        
    except Exception as e:
        logger.error(f"Error scraping Inquirer article: {e}")
        return None

# Export a smart scraper that detects the site
def smart_scrape(url: str) -> Optional[str]:
    """
    Intelligently scrape content based on the website
    
    Args:
        url: The URL to scrape
    
    Returns:
        Extracted text content or None if failed
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Use specialized scrapers for known sites
        if 'rappler.com' in domain:
            return scrape_rappler(url)
        elif 'inquirer.net' in domain:
            return scrape_inquirer(url)
        # Add more specialized scrapers as needed
        else:
            return scrape_link(url)
            
    except Exception as e:
        logger.error(f"Error in smart scrape: {e}")
        return None