import requests
import random
from typing import List, Dict, Optional


class LeetCodeAPI:
    """LeetCode API wrapper that fetches all problems directly from LeetCode's
    REST endpoint every time it's needed. Questions are always fresh."""

    PROBLEMS_URL = "https://leetcode.com/api/problems/all/"
    GRAPHQL_URL = "https://leetcode.com/graphql"

    HEADERS = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://leetcode.com",
        "Referer": "https://leetcode.com/problemset/all/"
    }

    DIFFICULTY_MAP = {1: "Easy", 2: "Medium", 3: "Hard"}

    def __init__(self):
        self.base_url = "https://leetcode.com"
        self._problems_cache: Optional[List[Dict]] = None

    def _fetch_all_problems(self) -> List[Dict]:
        """Fetch ALL problems from LeetCode REST API.
        Returns ~4000 problems with number, title, difficulty, and titleSlug.
        No topic tags from REST API — we use the title-based heuristic instead.
        """
        try:
            resp = requests.get(self.PROBLEMS_URL, headers=self.HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"Error fetching problems from LeetCode REST API: {e}")
            return []

        problems = []
        for item in data.get("stat_status_pairs", []):
            stat = item["stat"]
            diff_level = item["difficulty"]["level"]
            difficulty = self.DIFFICULTY_MAP.get(diff_level, "Unknown")

            problems.append({
                "number": stat["frontend_question_id"],
                "title": stat["question__title"],
                "difficulty": difficulty,
                "topic": self._infer_topic_from_title(stat["question__title"]),
                "url": f"{self.base_url}/problems/{stat['question__title_slug']}",
                "titleSlug": stat["question__title_slug"]
            })
        return problems

    def _get_problems(self) -> List[Dict]:
        """Return cached problems, or fetch fresh data if cache is empty."""
        if not self._problems_cache:
            self._problems_cache = self._fetch_all_problems()
            print(f"Loaded {len(self._problems_cache)} problems from LeetCode")
        return self._problems_cache

    def refresh_problems(self):
        """Force a fresh fetch from LeetCode (clears cache)."""
        self._problems_cache = None
        self._get_problems()

    def _infer_topic_from_title(self, title: str) -> str:
        """Infer a topic from the problem title using keyword heuristics."""
        t = title.lower()
        if any(w in t for w in ['array', 'list', 'sequence', 'subarray']):
            return "Array"
        if any(w in t for w in ['linked', 'node']):
            return "Linked List"
        if any(w in t for w in ['tree', 'binary', 'bst', 'n-ary']):
            return "Tree"
        if any(w in t for w in ['graph', 'edge', 'island']):
            return "Graph"
        if 'stack' in t:
            return "Stack"
        if 'queue' in t:
            return "Queue"
        if any(w in t for w in ['hash', 'map', 'set', 'anagram']):
            return "HashMap"
        if any(w in t for w in ['two pointer', 'two-sum', 'two number', 'container']):
            return "Two Pointer"
        if any(w in t for w in ['window', 'substring', 'subsequence']):
            return "Sliding Window"
        if any(w in t for w in ['binary search', 'search insert', 'search rotated']):
            return "Binary Search"
        if any(w in t for w in ['dp', 'dynamic', 'memo', 'climb', 'coin', 'knapsack',
                                  'subsequence', 'palindrome']):
            return "Dynamic Programming"
        if any(w in t for w in ['trie', 'prefix', 'lru', 'cache']):
            return "Design"
        return "General"

    def get_random_problems(self, difficulty: str, topic: Optional[str] = None, exclude: List[int] = None) -> List[Dict]:
        """Fetch problems from LeetCode, filter by difficulty and topic, return up to 2 random."""
        if exclude is None:
            exclude = []
        problems = self._get_problems()
        filtered = [p for p in problems if p["difficulty"].lower() == difficulty.lower() and p["number"] not in exclude]
        if topic:
            filtered = [p for p in filtered if p["topic"].lower() == topic.lower()]
        return random.sample(filtered, min(2, len(filtered))) if filtered else []

    def get_random_problem_from_leetcode(self, difficulty: str, topic: Optional[str] = None, exclude: List[int] = None) -> Optional[Dict]:
        """Return a single random problem matching the criteria."""
        problems = self.get_random_problems(difficulty, topic, exclude)
        return problems[0] if problems else None

    def get_problem_by_number(self, number: int) -> Optional[Dict]:
        """Look up a problem by its LeetCode frontend number."""
        problems = self._get_problems()
        for p in problems:
            if p["number"] == number:
                return p
        return None
