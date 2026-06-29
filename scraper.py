import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HOME_URL = "https://newsinlevels.com/"
REQUEST_TIMEOUT = 10
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0"})


def get_html(url):
    r = SESSION.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.text


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def parse_publish_datetime(soup):
    text = clean_text(soup.get_text(" "))
    match = re.search(r"\b(\d{2})-(\d{2})-(\d{4})\s+(\d{2}):(\d{2})\b", text)
    if not match:
        raise RuntimeError("Publish date was not found.")

    day, month, year, hour, minute = match.groups()
    return datetime(int(year), int(month), int(day), int(hour), int(minute))


def real_title_from_page(soup):
    title_tag = soup.find("h2") or soup.find("h1")
    title = clean_text(title_tag.get_text(" ")) if title_tag else "News in Levels"
    title = re.sub(r"\s*[–-]\s*level\s*\d+\s*$", "", title, flags=re.I)
    return title


def get_article_list_url(page_number):
    if page_number == 1:
        return HOME_URL
    return urljoin(HOME_URL, f"page/{page_number}/")


def get_recent_articles(page_count=1):
    urls = []
    seen = set()

    for page_number in range(1, page_count + 1):
        soup = BeautifulSoup(get_html(get_article_list_url(page_number)), "html.parser")

        for a in soup.select("a[href]"):
            text = clean_text(a.get_text(" "))
            url = urljoin(HOME_URL, a["href"])

            if "newsinlevels.com" not in urlparse(url).netloc:
                continue
            if text != "Level 1":
                continue
            if "/products/" not in url:
                continue
            if url in seen:
                continue

            seen.add(url)
            urls.append(url)

    articles = []
    for url in urls:
        article_soup = BeautifulSoup(get_html(url), "html.parser")
        publish_dt = parse_publish_datetime(article_soup)
        title = real_title_from_page(article_soup)
        articles.append({"url": url, "title": title, "publish_dt": publish_dt})

    articles.sort(key=lambda item: item["publish_dt"], reverse=True)
    return articles


def make_level_url(level1_url, level):
    if level == 1:
        return level1_url

    base = level1_url.rstrip("/")
    base = re.sub(r"-level-1$", "", base)
    return f"{base}-level-{level}/"


def is_useless_text(text):
    low = text.lower()
    useless_phrases = [
        "news in levels is designed to teach you 3000 words in english",
        "please follow the instructions below",
        "you can watch the video news lower on this page",
        "you can watch the original video",
        "watch the video news",
        "stock images by",
        "image by",
        "photo by",
        "soundcloud",
        "advertisement",
        "how to improve your english",
    ]
    return any(phrase in low for phrase in useless_phrases)


def extract_article(url):
    soup = BeautifulSoup(get_html(url), "html.parser")

    for tag in soup(["script", "style", "noscript", "iframe", "form", "img"]):
        tag.decompose()

    title = real_title_from_page(soup)
    publish_dt = parse_publish_datetime(soup)
    article = soup.find("article") or soup.find("main") or soup.body

    body_paragraphs = []
    difficult_words = []

    for p in article.find_all("p"):
        text = clean_text(p.get_text(" "))
        low = text.lower()

        if not text:
            continue
        if re.fullmatch(r"\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}", text):
            continue
        if is_useless_text(text):
            continue

        if low.startswith("difficult words:"):
            difficult_words.append(text)
            continue

        if len(text) >= 25:
            body_paragraphs.append(text)

    if not body_paragraphs:
        raise RuntimeError(f"Article text was not found: {url}")

    return title, publish_dt, body_paragraphs, difficult_words
