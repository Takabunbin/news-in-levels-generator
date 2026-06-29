import json
from datetime import datetime

from config_manager import PROJECT_DIR

ARTICLES_CACHE_FILE = PROJECT_DIR / "articles_cache.json"


def load_articles_cache():
    if not ARTICLES_CACHE_FILE.exists():
        return []

    try:
        with ARTICLES_CACHE_FILE.open("r", encoding="utf-8") as f:
            cached_items = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    articles = []
    for item in cached_items:
        try:
            publish_dt = datetime.fromisoformat(item["date"])
            articles.append({
                "publish_dt": publish_dt,
                "title": item["title"],
                "url": item["url"],
            })
        except (KeyError, TypeError, ValueError):
            continue

    articles.sort(key=lambda item: item["publish_dt"], reverse=True)
    return articles


def save_articles_cache(articles):
    cached_items = [
        {
            "date": article["publish_dt"].date().isoformat(),
            "title": article["title"],
            "url": article["url"],
        }
        for article in articles
    ]

    with ARTICLES_CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(cached_items, f, ensure_ascii=False, indent=2)
