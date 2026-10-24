import re
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


AI_PATTERN = re.compile(
    r"\b(AI|artificial intelligence|machine learning|LLMs?|GenAI|generative|agents?|agentic|chatbots?)\b",
    re.IGNORECASE,
)


def mentions_ai(item: dict) -> bool:
    """True if the item's title, summary, or categories mention AI."""
    text = " ".join([item["title"], item["summary"], *item["categories"]])
    return bool(AI_PATTERN.search(text))


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


def collect_stories(section: str, days: int) -> tuple[list[dict], list[str]]:
    """Fetch every feed in a section and return (recent stories newest first, failed feeds)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stories = []
    failed_feeds = []
    for feed in load_feeds(section):
        try:
            items = fetch_feed(feed["url"], feed["name"])
        except Exception as error:
            failed_feeds.append(f"{feed['name']}: {error}")
            continue
        if feed.get("ai_filter"):
            items = [item for item in items if mentions_ai(item)]
        stories.extend(item for item in items if item["published"] >= cutoff)

    stories.sort(key=lambda s: s["published"], reverse=True)
    for story in stories:
        story["published"] = story["published"].isoformat()
    return stories, failed_feeds


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
    stories, failed_feeds = collect_stories("news", days)
    return {"stories": stories[:limit], "failed_feeds": failed_feeds}


@mcp.tool()
def get_company_ai_updates(days: int = 3, company: str | None = None, limit: int = 20) -> dict:
    """Get stories about real companies adopting or building with AI
    (AWS Machine Learning Blog, CIO.com, Salesforce News).

    Use this for "AI at work": customer case studies, enterprise AI rollouts,
    and how businesses use AI tools.

    Args:
        days: How many days back to look (1-14).
        company: Optional company name to filter by, e.g. "Walmart".
        limit: Max number of stories to return (1-30).
    """
    days = max(1, min(days, 14))
    limit = max(1, min(limit, 30))
    stories, failed_feeds = collect_stories("work", days)
    if company:
        name = company.lower()
        stories = [s for s in stories if name in (s["title"] + " " + s["summary"]).lower()]
    return {"stories": stories[:limit], "failed_feeds": failed_feeds}


if __name__ == "__main__":
    mcp.run()
