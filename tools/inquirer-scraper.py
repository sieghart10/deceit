import asyncio
import random
import csv
import os
from playwright.async_api import async_playwright, TimeoutError
from bs4 import BeautifulSoup

# user agents
USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone17,1; CPU iPhone OS 18_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:15.0) Gecko/20100101 Firefox/15.0.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

CSV_PATH = os.path.join("data", "inquirer-articles.csv")

# Ensure directory exists
os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

def save_to_csv(data, write_header=False):
    """Save article data to CSV file"""
    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["source", "title", "content", "link", "label"]
        )
        if write_header and not file_exists:
            writer.writeheader()
        writer.writerow(data)
    print(f"✓ Saved: {data['title'][:60]}...")

async def scrape_article_content(page, url):
    """Scrape individual article content"""
    try:
        await page.goto(url, timeout=20000, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)  # Wait for dynamic content

        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        
        # Inquirer.net specific content selectors
        content_selectors = [
            "#article_content p",
            ".entry-content p", 
            ".post-content p",
            ".article-body p",
            "article .content p"
        ]
        
        content_paragraphs = []
        for selector in content_selectors:
            content_paragraphs = soup.select(selector)
            if content_paragraphs:
                break
        
        # Extract text content
        content = " ".join([p.get_text(strip=True) for p in content_paragraphs if p.get_text(strip=True)])
        
        return content if len(content) > 100 else None  # Only return if substantial content
        
    except Exception as e:
        print(f"Error scraping article {url}: {e}")
        return None

async def extract_article_links(page):
    """Extract article links from current page"""
    await page.wait_for_load_state('networkidle', timeout=15000)
    
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    
    articles = []
    
    # Try different article selectors for Inquirer.net
    selectors = [
        "article.post",
        ".post-item", 
        ".entry",
        ".story-item"
    ]
    
    for selector in selectors:
        articles = soup.select(selector)
        if articles:
            print(f"Found {len(articles)} articles using selector: {selector}")
            break
    
    # Fallback: look for links that appear to be articles
    if not articles:
        print("Using fallback method to find articles...")
        all_links = soup.find_all('a', href=True)
        
        potential_articles = []
        for link in all_links:
            href = link.get('href', '')
            title = link.get_text(strip=True)
            
            # Filter for article-like links
            if (href and title and 
                len(title) > 30 and  # Substantial title
                ('newsinfo.inquirer.net' in href or href.startswith('/')) and
                not any(skip in href.lower() for skip in [
                    '#', 'javascript:', 'mailto:', 'category', 'tag', 'author', 
                    'search', 'page/', '.jpg', '.png', '.pdf'
                ]) and
                not any(skip in title.lower() for skip in [
                    'read more', 'continue', 'home', 'about', 'contact', 'menu'
                ])):
                
                potential_articles.append({
                    'title': title,
                    'link': href if href.startswith('http') else f"https://newsinfo.inquirer.net{href}"
                })
        
        return potential_articles[:20]  # Limit to first 20
    
    # Extract title and link from article elements
    article_data = []
    for article in articles:
        # Look for title link within article
        title_link = (article.select_one('h2 a') or 
                     article.select_one('h3 a') or 
                     article.select_one('.entry-title a') or
                     article.select_one('a'))
        
        if title_link:
            title = title_link.get_text(strip=True)
            href = title_link.get('href', '')
            
            if title and href and len(title) > 20:
                # Ensure full URL
                if href.startswith('/'):
                    href = f"https://newsinfo.inquirer.net{href}"
                
                article_data.append({
                    'title': title,
                    'link': href
                })
    
    return article_data

async def handle_verification(page):
    """Handle verification, CAPTCHA, or bot detection"""
    try:
        # Wait a bit for page to load completely
        await page.wait_for_timeout(3000)
        
        # Check for common verification elements
        verification_selectors = [
            'iframe[src*="captcha"]',
            '[class*="captcha"]',
            '[id*="captcha"]',
            '.cf-browser-verification',
            '.challenge-form',
            '#challenge-form',
            '.verification',
            '[class*="cloudflare"]'
        ]
        
        verification_found = False
        for selector in verification_selectors:
            element = await page.query_selector(selector)
            if element:
                verification_found = True
                print(f"Verification detected: {selector}")
                break
        
        # Check if page title suggests verification
        title = await page.title()
        if any(word in title.lower() for word in ['verify', 'captcha', 'challenge', 'checking', 'security']):
            verification_found = True
            print(f"Verification detected in title: {title}")
        
        # Check for specific text content
        content = await page.content()
        verification_phrases = [
            'verify you are human',
            'checking your browser',
            'security check',
            'please wait',
            'cloudflare'
        ]
        
        if any(phrase in content.lower() for phrase in verification_phrases):
            verification_found = True
            print("Verification detected in page content")
        
        if verification_found:
            print("⚠️  Verification/CAPTCHA detected!")
            print("Please solve the verification manually in the browser window.")
            print("The script will wait for 60 seconds...")
            
            # Wait up to 60 seconds for verification to be completed
            for i in range(60):
                await page.wait_for_timeout(2000)
                
                # Check if verification is completed by looking for expected content
                current_url = page.url
                current_title = await page.title()
                
                # If URL changed or title no longer contains verification words
                if ('world-latest-stories' in current_url and 
                    not any(word in current_title.lower() for word in ['verify', 'captcha', 'challenge', 'checking'])):
                    print("✅ Verification appears to be completed!")
                    break
                    
                if i % 10 == 0:  # Print every 10 seconds
                    print(f"Still waiting... {60-i} seconds remaining")
            
            # Final check
            await page.wait_for_timeout(3000)
            final_url = page.url
            if 'world-latest-stories' not in final_url:
                print("❌ Verification may not be completed. Please check manually.")
                input("Press Enter to continue anyway, or Ctrl+C to exit...")
        else:
            print("✅ No verification detected, proceeding...")
            
    except Exception as e:
        print(f"Error checking for verification: {e}")
        print("Proceeding anyway...")

async def click_next_page(page):
    """Navigate to next page"""
    print("Looking for Next button...")
    
    try:
        # Wait for page to stabilize
        await page.wait_for_load_state('networkidle', timeout=10000)
        
        # Common next page selectors for WordPress/Inquirer
        next_selectors = [
            '.wp-pagenavi .nextpostslink',
            '.pagination .next',
            'a[rel="next"]',
            '.nav-links .next',
            '.page-numbers.next'
        ]
        
        for selector in next_selectors:
            try:
                next_btn = await page.query_selector(selector)
                if next_btn:
                    is_visible = await next_btn.is_visible()
                    href = await next_btn.get_attribute('href')
                    
                    if is_visible and href and 'inquirer.net' in href:
                        print(f"Found next button with selector: {selector}")
                        await next_btn.scroll_into_view_if_needed()
                        await page.wait_for_timeout(2000)
                        await next_btn.click()
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        return True
            except Exception as e:
                continue
        
        # Fallback: look for any link with "Next" text
        all_links = await page.query_selector_all('a')
        for link in all_links:
            try:
                text = await link.text_content()
                href = await link.get_attribute('href')
                
                if (text and 'next' in text.lower() and 
                    len(text.strip()) < 20 and  # Short text, likely navigation
                    href and 'inquirer.net' in href and
                    'world-latest-stories' in href):  # Stay in same category
                    
                    is_visible = await link.is_visible()
                    if is_visible:
                        print(f"Clicking next link: {text}")
                        await link.scroll_into_view_if_needed()
                        await page.wait_for_timeout(2000)
                        await link.click()
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        return True
            except Exception:
                continue
                
        print("No next button found")
        return False
        
    except Exception as e:
        print(f"Error finding next button: {e}")
        return False

async def scrape_inquirer_world():
    """Main scraping function"""
    start_url = "https://newsinfo.inquirer.net/category/latest-stories/world-latest-stories/page/43"
    scraped_links = set()
    
    # Load existing articles to avoid duplicates
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                scraped_links.add(row['link'])
        print(f"Loaded {len(scraped_links)} existing articles")
    
    async with async_playwright() as p:
        # Launch browser with additional anti-detection measures
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={'width': 1920, 'height': 1080},
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        
        # Remove webdriver property to avoid detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            })
        """)
        
        # Create pages
        list_page = await context.new_page()
        content_page = await context.new_page()
        
        try:
            print(f"Starting scrape from: {start_url}")
            await list_page.goto(start_url, timeout=60000)
            
            # Check for verification/CAPTCHA
            await handle_verification(list_page)
            
            await list_page.wait_for_load_state('networkidle')
            
            page_num = 1
            total_scraped = 0
            write_header = not os.path.exists(CSV_PATH)
            
            while page_num <= 200:  # Limit to 50 pages max
                print(f"\n--- Page {page_num} ---")
                
                # Extract article links from current page
                articles = await extract_article_links(list_page)
                print(f"Found {len(articles)} articles on page {page_num}")
                
                new_articles = 0
                
                # Process each article
                for article in articles:
                    title = article['title']
                    link = article['link']
                    
                    # Skip if already scraped
                    if link in scraped_links:
                        print(f"⏭️  Skipping (already scraped): {title[:50]}...")
                        continue
                    
                    # Scrape article content
                    print(f"📰 Scraping: {title[:60]}...")
                    content = await scrape_article_content(content_page, link)
                    
                    if content:
                        # Save to CSV
                        article_data = {
                            'source': 'inquirer',
                            'title': title,
                            'content': content,
                            'link': link,
                            'label': 'real'
                        }
                        
                        save_to_csv(article_data, write_header)
                        write_header = False
                        
                        scraped_links.add(link)
                        new_articles += 1
                        total_scraped += 1
                        
                        # Small delay between articles
                        await asyncio.sleep(1)
                    else:
                        print(f"❌ Failed to get content for: {title[:50]}")
                
                print(f"Page {page_num}: {new_articles} new articles scraped")
                
                # Try to go to next page
                if not await click_next_page(list_page):
                    print("No more pages found. Scraping complete.")
                    break
                
                page_num += 1
                await asyncio.sleep(1)  # Delay between pages
                
        except KeyboardInterrupt:
            print("\nScraping interrupted by user")
        except Exception as e:
            print(f"Error during scraping: {e}")
    
    print(f"\n🎉 Scraping completed!")
    print(f"📊 Total articles scraped this session: {total_scraped}")
    print(f"📁 Data saved to: {CSV_PATH}")

if __name__ == "__main__":
    asyncio.run(scrape_inquirer_world())