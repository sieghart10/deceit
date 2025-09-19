import asyncio
import random
import csv
import os
from playwright.async_api import async_playwright, TimeoutError
from bs4 import BeautifulSoup
import re
# user agents
USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone17,1; CPU iPhone OS 18_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:15.0) Gecko/20100101 Firefox/15.0.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

CSV_PATH = "data/rappler_articles.csv"

# -------- save data to CSV --------
def save_to_csv(data):
    file_exists = os.path.exists(CSV_PATH)

    if file_exists:
        with open(CSV_PATH, "rb+") as f:
            f.seek(-1, os.SEEK_END)
            last_char = f.read(1)
            if last_char != b"\n":
                f.write(b"\n")

    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["source", "title", "content", "link", "label"]
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)

# -------- fetch content and source --------
async def fetch_article_content(context, url, retries=3, delay=2):
    possible_sources = ["Tiktok", "Facebook", "Twitter", "YouTube", "Instagram"]

    for attempt in range(1, retries + 1):
        page = None
        try:
            page = await context.new_page()
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")

            await page.wait_for_selector(
                "div.article-main-section, div.post-single__content.entry-content, div.post-single__summary",
                timeout=8000,
            )

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            paragraphs = soup.find_all(["p", "li"])
            claim_paragraph = None
            source_paragraph = None
            source = None

            for p in paragraphs:
                strong_tag = p.find("strong")
                if not strong_tag:
                    continue

                strong_text = strong_tag.get_text(strip=True)

                # Claim paragraph
                if (
                    ("Claim" in strong_text or 
                     "Ang sabi-sabi" in strong_text or 
                     "An sabi-sabi" in strong_text)
                    and not claim_paragraph
                ):
                    strong_tag.decompose()
                    claim_paragraph = p

                # Source paragraph
                if (
                    "Why we fact-checked this" in strong_text
                    or "Bakit kailangang i-fact-check" in strong_text
                    or "Hadaw ta pig-tama mi ini" in strong_text
                ):
                    strong_tag.decompose()
                    source_paragraph = p

            if not source_paragraph:
                summary_div = soup.find("div", class_="post-single__summary")
                if summary_div:
                    source_paragraph = summary_div
                else:
                    buod_heading = soup.find("h5", string=lambda t: t and "Buod" in t)
                    if buod_heading:
                        ul = buod_heading.find_next("ul")
                        if ul:
                            for li in ul.find_all("li"):
                                if "Bakit" in li.get_text():
                                    source_paragraph = li
                                    break

            content = claim_paragraph.get_text(strip=True) if claim_paragraph else None

            if source_paragraph:
                full_text = source_paragraph.get_text(strip=True)
                for platform in possible_sources:
                    if platform.lower() in full_text.lower():
                        source = platform
                        break

            return {
                "content": content if content else None,
                "source": source if source else None,
            }

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

    return {"content": None, "source": None}

# -------- older posts  --------
async def click_older_posts_button(page, max_retries=3):
    selectors = ['a.pagination__link.pagination__load-more.button.button__bg-secondary']

    for attempt in range(max_retries):
        try:
            await page.wait_for_timeout(2000)

            for selector in selectors:
                try:
                    # print(f"Trying selector: {selector}")

                    element = await page.wait_for_selector(selector, timeout=5000)

                    if element:
                        is_visible = await element.is_visible()
                        is_enabled = await element.is_enabled()

                        if is_visible and is_enabled:
                            print(f"Found button: {selector}")
                            await element.scroll_into_view_if_needed()
                            await page.wait_for_timeout(1000)
                            await element.click()
                            await page.wait_for_timeout(4000)
                            return True
                        else:
                            print(f"Button found but not visible/enabled: visible={is_visible}, enabled={is_enabled}")

                except Exception as e:
                    print(f"Selector {selector} failed: {e}")
                    continue
            print("No older posts button found - might have reached end of articles")
            return False

        except Exception as e:
            print(f"Attempt {attempt + 1} failed to click older posts: {e}")
            await page.wait_for_timeout(2000)

    return False

# -------- extract links --------
async def extract_article_links(page):
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    links_data = []
    articles = soup.find_all("article", id=lambda x: x and x.startswith("post-"))
    # print(articles)

    for article in articles:
        title_element = article.select_one("h2 > a")

        if title_element:
            href = title_element.get("href")
            title = title_element.get_text(strip=True)

            if href and title and len(title.strip()) > 10:
                if href.startswith('/'):
                    href = "https://www.rappler.com/" + href
                elif not href.startswith('http'):
                    continue

                links_data.append({
                    "title": title.strip(),
                    "link": href
                })
        else:
            print("Error finding article title")

    seen_links = set()
    unique_links_data = []
    for item in links_data:
        if item["link"] not in seen_links:
            seen_links.add(item["link"])
            unique_links_data.append(item)

    return unique_links_data

# -------- main scraper --------
async def scrape():
    start_url = "https://www.rappler.com/newsbreak/fact-check/page/406/"
    batch_size = 5
    target_total = 1633
    scraped_links = set()
    failed_links = set()

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
        browser = await p.chromium.launch(headless=True)
        user_agent = random.choice(USER_AGENTS)
        context = await browser.new_context(user_agent=user_agent)
        main_page = await context.new_page()

        try:
            await main_page.goto(start_url, timeout=20000)
            await main_page.wait_for_timeout(3000)
        except Exception as e:
            print(f"Failed to load main page: {e}")
            return

        count = already_scraped
        write_header = not os.path.exists(CSV_PATH)
        pages_without_new_articles = 0
        max_pages_without_new = float('inf')

        while count < target_total:
            print(f"\n--- Processing page (articles so far: {count}) ---")

            article_links_data = await extract_article_links(main_page)
            print(f"Found {len(article_links_data)} potential articles on this page")

            new_articles_this_page = 0

            for article_data in article_links_data:
                title = article_data["title"]
                link = article_data["link"]

                if link in scraped_links or link in failed_links:
                    continue 

                print(f"Scraping: {title[:50]}...")
                content_data = await fetch_article_content(context, link)

                if not content_data["content"]:
                    print(f"  -> Failed to get content")
                    failed_links.add(link)
                    continue

                data = {
                    "source": content_data["source"] or "Unkown",
                    "title": title,
                    "content": content_data["content"],
                    "link": link,
                    "label": "fake"
                }
                save_to_csv(data)

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

            print("Attempting to load older posts...")
            success = await click_older_posts_button(main_page)
            if not success:
                print("Could not load older posts. Stopping.")
                break

            print("Loaded older posts, continuing...")

        await context.close()
        await browser.close()

    print(f"New articles scraped: {count - already_scraped}")
    print(f"Total articles in file: {count}")

if __name__ == '__main__':
    asyncio.run(scrape())