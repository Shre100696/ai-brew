from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import httpx
import yaml
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("AI Brew")

SOURCES_FILE = Path(__file__).parent / "sources.yaml"


def load_feeds(section: str) -> list[dict]:
    """Return the feeds from sources.yaml that belong to one newsletter section."""
    config = yaml.safe_load(SOURCES_FILE.read_text())
    return [feed for feed in config["feeds"] if feed["section"] == section]


SPONSORED_MARKERS = ["presented by", "sponsored", "partner content", "insights"]


def is_sponsored(item: dict) -> bool:
    """True if the item looks like paid content rather than journalism."""
    text = " ".join([item["title"], item["summary"], *item["categories"]]).lower()
    return any(marker in text for marker in SPONSORED_MARKERS)


def fetch_feed(url: str, name: str) -> list[dict]:
    """Download one RSS feed and return its items as clean dicts."""
    response = httpx.get(url, timeout=10, follow_redirects=True)
    response.raise_for_status()
    feed = feedparser.parse(response.text)

    items = []
    for entry in feed.entries:
        if not entry.get("published_parsed"):
            continue  # no date means we can't tell if it's recent
        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        item = {
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "source": name,
            "published": published,
            "summary": entry.get("summary", ""),
            "categories": [tag.get("term", "") for tag in entry.get("tags", [])],
        }
        if not is_sponsored(item):
            items.append(item)
    return items


@mcp.tool()
def get_ai_news(days: int = 1, limit: int = 20) -> dict:
    """Get recent AI news stories from trusted tech news sites
    (TechCrunch, Ars Technica, The Verge, MIT Technology Review).
    Sponsored posts are filtered out.

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
    for feed in load_feeds("news"):
        try:
            stories.extend(fetch_feed(feed["url"], feed["name"]))
        except Exception as error:
            failed_feeds.append(f"{feed['name']}: {error}")

    recent = [s for s in stories if s["published"] >= cutoff]
    recent.sort(key=lambda s: s["published"], reverse=True)

    for story in recent:
        story["published"] = story["published"].isoformat()

    return {"stories": recent[:limit], "failed_feeds": failed_feeds}


if __name__ == "__main__":
    mcp.run()
