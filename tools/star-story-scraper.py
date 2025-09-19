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

CSV_PATH = os.path.join("data", "breakingnews-articles-new.csv")

# Ensure directory exists
os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

# -------- save data to CSV --------
def save_to_csv(data, write_header=False):
    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["source", "title", "content", "link", "label"]
        )
        if write_header and not file_exists:
            writer.writeheader()
        writer.writerow(data)

async def fetch_article_content(context, url, retries=3, delay=2):
    for attempt in range(1, retries + 1):
        page = None
        try:
            page = await context.new_page()
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")

            # Wait for content to load
            await page.wait_for_timeout(3000)

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            
            # More comprehensive selectors for article content
            content_selectors = [
                "div.entry-content p",
                "div.story_main p", 
                "div.article-body p",
                "div.ncaa_article_body p",
                ".post-content p",
                "article p",
                ".content p",
                ".article-content p",
                ".post-body p",
                ".entry-content p",
                "main p",
                ".single-post p",
                ".blog-post p"
            ]
            
            paragraphs = []
            for selector in content_selectors:
                paragraphs = soup.select(selector)
                if paragraphs:
                    break
            
            # If no paragraphs found with specific selectors, try general approach
            if not paragraphs:
                # Try to find the main content area first
                main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
                if main_content:
                    paragraphs = main_content.find_all('p')
                else:
                    paragraphs = soup.find_all('p')

            content = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            return content if content.strip() else None

        except TimeoutError:
            print(f"[Attempt {attempt}] Timeout for article: {url}")
        except Exception as e:
            print(f"[Attempt {attempt}] Error scraping {url}: {e}")
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

        await asyncio.sleep(delay)

    return None

# -------- navigate to next page --------
async def click_next_page(page, current_page_number):
    target_page = current_page_number + 1
    print(f"=== Looking for page {target_page} button (from page {current_page_number}) ===")
    
    try:
        # First, look for numbered page buttons/links
        all_buttons = await page.query_selector_all('button')
        all_links = await page.query_selector_all('a')
        
        print(f"Scanning {len(all_buttons)} buttons and {len(all_links)} links for page numbers...")
        
        # Check buttons for page numbers
        for button in all_buttons:
            try:
                text = await button.text_content()
                if text and text.strip().isdigit():
                    page_num = int(text.strip())
                    print(f"Found page button: {page_num}")
                    
                    if page_num == target_page:
                        is_visible = await button.is_visible()
                        is_enabled = await button.is_enabled()
                        
                        if is_visible and is_enabled:
                            print(f"*** Clicking page button: {target_page} ***")
                            await button.scroll_into_view_if_needed()
                            await page.wait_for_timeout(1000)
                            await button.click()
                            await page.wait_for_timeout(4000)
                            return True
                        else:
                            print(f"Page button {target_page} not clickable: visible={is_visible}, enabled={is_enabled}")
                            
            except Exception:
                continue
        
        # Check links for page numbers
        for link in all_links:
            try:
                text = await link.text_content()
                href = await link.get_attribute('href')
                
                if text and text.strip().isdigit() and href:
                    page_num = int(text.strip())
                    print(f"Found page link: {page_num} -> {href}")
                    
                    if page_num == target_page:
                        is_visible = await link.is_visible()
                        
                        if is_visible and href != '#' and 'javascript:' not in href:
                            print(f"*** Clicking page link: {target_page} ***")
                            await link.scroll_into_view_if_needed()
                            await page.wait_for_timeout(1000)
                            await link.click()
                            await page.wait_for_timeout(4000)
                            return True
                        else:
                            print(f"Page link {target_page} not suitable: visible={is_visible}, href='{href}'")
                            
            except Exception:
                continue
        
        # If we can't find the specific next page, look for "Next" or ">" buttons
        print(f"Could not find page {target_page}, looking for Next/More buttons...")
        
        for button in all_buttons:
            try:
                text = await button.text_content()
                if text:
                    text_lower = text.lower().strip()
                    if any(keyword in text_lower for keyword in ['next', 'more', '→', '»', '>']):
                        is_visible = await button.is_visible()
                        is_enabled = await button.is_enabled()
                        
                        if is_visible and is_enabled:
                            print(f"*** Clicking Next button: '{text}' ***")
                            await button.scroll_into_view_if_needed()
                            await page.wait_for_timeout(1000)
                            await button.click()
                            await page.wait_for_timeout(4000)
                            return True
            except Exception:
                continue
        
        for link in all_links:
            try:
                text = await link.text_content()
                href = await link.get_attribute('href')
                
                if text:
                    text_lower = text.lower().strip()
                    if any(keyword in text_lower for keyword in ['next', '→', '»', '>', 'older']):
                        is_visible = await link.is_visible()
                        
                        if is_visible and href and href != '#':
                            print(f"*** Clicking Next link: '{text}' ***")
                            await link.scroll_into_view_if_needed()
                            await page.wait_for_timeout(1000)
                            await link.click()
                            await page.wait_for_timeout(4000)
                            return True
            except Exception:
                continue
                
    except Exception as e:
        print(f"Error during pagination search: {e}")
    
    print(f"Could not find way to navigate to page {target_page}")
    return False

# -------- extract links --------
async def extract_article_links(page):
    print("=== Extracting article links ===")
    
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    
    # Save HTML for debugging
    with open('debug_page.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Saved current page HTML to debug_page.html")

    links_data = []
    
    # More flexible selectors for articles
    article_selectors = [
        "article",
        ".post",
        ".entry", 
        ".article-item",
        ".news-item",
        ".blog-post",
        ".card",
        ".item",
        "[class*='post']",
        "[class*='article']",
        "[class*='entry']",
        "[id*='post']"
    ]
    
    articles = []
    for selector in article_selectors:
        try:
            if selector.startswith('[') and '*=' in selector:
                # Handle attribute selectors with contains
                if 'class*=' in selector:
                    attr_value = selector.split("'")[1]
                    articles = soup.find_all(attrs={'class': lambda x: x and attr_value in ' '.join(x) if isinstance(x, list) else attr_value in x if x else False})
                elif 'id*=' in selector:
                    attr_value = selector.split("'")[1]
                    articles = soup.find_all(attrs={'id': lambda x: x and attr_value in x if x else False})
            else:
                articles = soup.select(selector)
            
            if articles:
                print(f"Found {len(articles)} articles with selector: {selector}")
                break
                
        except Exception as e:
            print(f"Error with selector {selector}: {e}")
            continue
    
    # If no articles found with specific selectors, try more general approach
    if not articles:
        print("No articles found with specific selectors, trying general approach...")
        
        # Look for any links that might be articles
        all_links = soup.find_all('a', href=True)
        print(f"Found {len(all_links)} total links on page")
        
        # Filter for likely article links
        potential_articles = []
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # More detailed filtering for breakingnewsaz.today
            if (href and text and 
                len(text) > 25 and  # Reasonable title length
                not any(skip in href.lower() for skip in ['#', 'javascript:', 'mailto:', 'tel:', '.css', '.js', '.png', '.jpg', '.gif', '.pdf', 'wp-content', 'wp-admin']) and
                not any(skip in text.lower() for skip in ['read more', 'continue reading', 'menu', 'home', 'about', 'contact', 'privacy', 'terms', 'search', 'category', 'tag']) and
                not text.isupper() and  # Skip ALL CAPS text (often navigation)
                # Look for URL patterns that suggest articles
                ('/' in href or '-' in href) and
                # Skip obvious non-article pages
                not any(pattern in href.lower() for pattern in ['/page/', '/category/', '/tag/', '/author/', '/search/', '?p=', '?page='])):
                
                potential_articles.append(link)
        
        articles = potential_articles[:30]  # Limit to first 30 potential articles
        print(f"Found {len(articles)} potential article links after filtering")
        
        # Debug: show first few potential articles
        for i, link in enumerate(articles[:5]):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            print(f"Sample article {i}: '{text[:50]}...' -> {href}")

    print(f"Processing {len(articles)} articles...")
    
    for i, article in enumerate(articles):
        # Try different selectors for title and link
        title_selectors = [
            "h1 a", "h2 a", "h3 a", "h4 a",
            ".title a", ".entry-title a", ".post-title a",
            "a[rel='bookmark']", "a"
        ]
        
        title = ""
        href = ""
        
        # If article is already a link
        if hasattr(article, 'get') and article.get('href'):
            href = article.get('href')
            title = article.get_text(strip=True)
            
        else:
            # Look for title link within article
            for title_selector in title_selectors:
                title_element = article.select_one(title_selector)
                if title_element:
                    href = title_element.get("href", "")
                    title = title_element.get_text(strip=True)
                    break

        if href and title and len(title.strip()) > 15:
            # Clean up URL
            if href.startswith('/'):
                href = "https://breakingnewsaz.today" + href
            elif not href.startswith('http'):
                continue

            # Filter out non-article URLs
            if any(skip in href.lower() for skip in ['category', 'tag', 'author', 'page/', 'search', '?page=', '#']):
                continue
                
            links_data.append({
                "title": title.strip(),
                "link": href
            })

    # Remove duplicates
    seen_links = set()
    unique_links_data = []
    for item in links_data:
        if item["link"] not in seen_links:
            seen_links.add(item["link"])
            unique_links_data.append(item)

    print(f"Final result: {len(unique_links_data)} unique articles")
    return unique_links_data

# -------- main scraper --------
async def scrape():
    start_url = "https://breakingnewsaz.today/"
    batch_size = 3
    target_total = 500 # Increased target
    scraped_links = set()

    # resume
    already_scraped = 0
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                scraped_links.add(row["link"])
        already_scraped = len(scraped_links)
        print(f"Resuming... {already_scraped} already scraped.")

    if already_scraped >= target_total:
        print(f"Already have {already_scraped} articles (>= {target_total}). Nothing to do.")
        return

    to_scrape = target_total - already_scraped
    print(f"Will scrape {to_scrape} new articles (target total = {target_total})")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Set to False for debugging
        user_agent = random.choice(USER_AGENTS)
        context = await browser.new_context(user_agent=user_agent)
        main_page = await context.new_page()

        try:
            print(f"Loading main page: {start_url}")
            await main_page.goto(start_url, timeout=30000)
            await main_page.wait_for_timeout(5000)  # Wait for page to load
        except Exception as e:
            print(f"Failed to load main page: {e}")
            return

        count = already_scraped
        write_header = not os.path.exists(CSV_PATH)
        pages_without_new_articles = 0
        max_pages_without_new = 3
        page_number = 1

        while count < target_total:
            print(f"\n--- Processing page {page_number} (articles so far: {count}) ---")

            article_links_data = await extract_article_links(main_page)
            print(f"Found {len(article_links_data)} potential articles on this page")

            new_articles_this_page = 0

            for article_data in article_links_data:
                title = article_data["title"]
                link = article_data["link"]

                if link in scraped_links:
                    print(f"Skipping already scraped: {title[:30]}...")
                    continue

                print(f"Scraping: {title[:50]}...")
                content = await fetch_article_content(context, link)
                if not content:
                    print(f"  -> Failed to get content")
                    continue

                data = {
                    "source": "Breaking News AZ",
                    "title": title,
                    "content": content,
                    "link": link,
                    "label": "fake"
                }
                save_to_csv(data, write_header)
                write_header = False

                scraped_links.add(link)
                count += 1
                new_articles_this_page += 1
                print(f"  -> Scraped successfully ({count} total)")

                if count % batch_size == 0:
                    print(f"*** Milestone: {count} articles scraped ***")

                if count >= target_total:
                    break

            if new_articles_this_page == 0:
                pages_without_new_articles += 1
                print(f"No new articles on this page ({pages_without_new_articles}/{max_pages_without_new})")

                if pages_without_new_articles >= max_pages_without_new:
                    print("Too many pages without new articles. Stopping.")
                    break
            else:
                pages_without_new_articles = 0
                print(f"Got {new_articles_this_page} new articles from this page")

            if count >= target_total:
                break

            print("Attempting to navigate to next page...")
            success = await click_next_page(main_page, page_number)
            if not success:
                print("Could not find next page. Stopping.")
                break

            print("Successfully navigated to next page!")
            page_number += 1
            
            # Safety check - don't go beyond page 187
            if page_number > 187:
                print("Reached maximum page number (187). Stopping.")
                break

        await context.close()
        await browser.close()

    print(f"New articles scraped: {count - already_scraped}")
    print(f"Total articles in file: {count}")

if __name__ == "__main__":
    asyncio.run(scrape())