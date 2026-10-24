from datetime import datetime, timedelta, timezone


import feedparser
import httpx
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("AI Brew")
NEWS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://arstechnica.com/ai/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
]

def fetch_feed(url: str) -> list[dict]:
    """Download one RSS feed and return its items as clean dicts."""
    response = httpx.get(url, timeout=10, follow_redirects=True)
    response.raise_for_status()
    feed = feedparser.parse(response.text)

    items = []
    for entry in feed.entries:
        if not entry.get("published_parsed"):
            continue  # no date means we can't tell if it's recent
        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        items.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "source": feed.feed.get("title", url),
            "published": published,
            "summary": entry.get("summary", ""),
        })
    return items

@mcp.tool()
def get_ai_news(days: int = 1, limit: int = 20) -> dict:
    """Get recent AI news stories from trusted tech news sites
    (TechCrunch, Ars Technica, The Verge).

    Use this for the latest AI headlines: model launches, funding, policy.
    Returns each story's title, source, link, published date, and short summary.

    Args:
        days: How many days back to look (1-7).
        limit: Max number of stories to return (1-30).
    """
    days = max(1, min(days, 7))
    limit = max(1, min(limit, 30))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    stories = []
    failed_feeds = []
    for url in NEWS_FEEDS:
        try:
            stories.extend(fetch_feed(url))
        except Exception as error:
            failed_feeds.append(f"{url}: {error}")

    recent = [s for s in stories if s["published"] >= cutoff]
    recent.sort(key=lambda s: s["published"], reverse=True)

    for story in recent:
        story["published"] = story["published"].isoformat()

    return {"stories": recent[:limit], "failed_feeds": failed_feeds}



if __name__ == "__main__":
    mcp.run()