"""
generator/graphql_client.py
────────────────────────────
Fetches LeetCode problem descriptions from their GraphQL API.
Used ONLY by the Generator Worker — never by the Main Bot.
"""

import logging
import re
import html
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin":       "https://leetcode.com",
    "Referer":      "https://leetcode.com/problemset/all/",
}
GRAPHQL_URL = "https://leetcode.com/graphql"

QUERY = """
query questionData($titleSlug: String!) {
    question(titleSlug: $titleSlug) {
        content
    }
}
"""


def fetch_description(slug: str, timeout: int = 15) -> Optional[str]:
    """
    Fetch and clean the problem description for a given titleSlug.
    Returns plain text, or None on failure.
    """
    t0 = time.perf_counter()
    try:
        resp = requests.post(
            GRAPHQL_URL,
            headers=HEADERS,
            json={"query": QUERY, "variables": {"titleSlug": slug}},
            timeout=timeout,
        )
        resp.raise_for_status()
        content = resp.json().get("data", {}).get("question", {}).get("content", "") or ""

        # Strip HTML tags, collapse whitespace, unescape entities
        text = re.sub(r"<[^>]+>", " ", content)
        text = re.sub(r"\s+", " ", text).strip()
        text = html.unescape(text)

        ms = (time.perf_counter() - t0) * 1000
        logger.info(f"[GraphQL] {slug} fetched in {ms:.0f}ms")
        return text
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        logger.error(f"[GraphQL] {slug} FAILED {ms:.0f}ms – {e}")
        return None
