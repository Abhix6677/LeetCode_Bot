import os
import json
import time
import threading
import requests
import random
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional


class LeetCodeAPI:
    """LeetCode API wrapper that fetches all problems directly from LeetCode's
    REST endpoint every time it's needed. Questions are always fresh."""

    HEADERS = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://leetcode.com",
        "Referer": "https://leetcode.com/problemset/all/"
    }

    DIFFICULTY_MAP = {1: "Easy", 2: "Medium", 3: "Hard"}

    def __init__(self, cache_dir: str = "database"):
        self.base_url      = "https://leetcode.com"
        self.problems_url  = "https://leetcode.com/api/problems/all/"
        self.graphql_url   = "https://leetcode.com/graphql"
        print(f"Using LeetCode problems URL: {self.problems_url}")
        self._problems_cache: Optional[List[Dict]] = None
        self._description_cache: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="lc_api")

        # Persistent description cache
        self.cache_dir = cache_dir
        self._problem_cache_file = os.path.join(cache_dir, "problem_cache.json")
        os.makedirs(cache_dir, exist_ok=True)
        self._description_cache = self._load_desc_cache()
        print(f"[LeetCodeAPI] loaded {len(self._description_cache)} cached descriptions")

    def _fetch_all_problems(self) -> List[Dict]:
        """Fetch ALL problems from LeetCode REST API.
        Returns ~4000 problems with number, title, difficulty, and titleSlug.
        No topic tags from REST API — we use the title-based heuristic instead.
        """
        import json
        cache_path = os.path.join(self.cache_dir, "all_problems_cache.json")
        try:
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Failed to load problems from disk cache: {e}")
        try:
            resp = requests.get(self.problems_url, headers=self.HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"Error fetching problems from LeetCode REST API: {e}")
            return []

        problems = []
        for item in data.get("stat_status_pairs", []):
            if item.get("paid_only"):
                continue
                
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
            
        if problems:
            try:
                import json
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(problems, f)
            except Exception as e:
                print(f"Failed to save problems to disk cache: {e}")
                
        return problems

    def _get_problems(self) -> List[Dict]:
        """Return cached problems, or fetch fresh data if cache is empty."""
        if not self._problems_cache:
            self._problems_cache = self._fetch_all_problems()
            print(f"Loaded {len(self._problems_cache)} problems from LeetCode")
        return self._problems_cache

    def get_all_free_problems(self) -> List[Dict]:
        """Return all free problems (approx 3000-4000)."""
        return self._get_problems()

    def refresh_problems(self):
        """Force a fresh fetch from LeetCode (clears cache)."""
        self._problems_cache = None
        self._get_problems()

    def _infer_topic_from_title(self, title: str) -> str:
        """Infer a topic from the problem title using keyword heuristics."""
        t = title.lower()
        if any(w in t for w in ['array', 'list', 'sequence', 'subarray']):
            return "Array"
        if any(w in t for w in ['string', 'palindrome', 'word', 'char', 'anagram', 'parentheses', 'vowel']):
            return "String"
        if any(w in t for w in ['math', 'number', 'sum', 'power', 'multiply', 'divide', 'digit']):
            return "Math"
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
        if any(w in t for w in ['hash', 'map', 'set']):
            return "HashMap"
        if any(w in t for w in ['two pointer', 'two-sum', 'two number', 'container']):
            return "Two Pointer"
        if any(w in t for w in ['window', 'substring', 'subsequence']):
            return "Sliding Window"
        if any(w in t for w in ['binary search', 'search insert', 'search rotated']):
            return "Binary Search"
        if any(w in t for w in ['dp', 'dynamic', 'memo', 'climb', 'coin', 'knapsack']):
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

    def _load_desc_cache(self) -> Dict[str, str]:
        if os.path.exists(self._problem_cache_file):
            try:
                with open(self._problem_cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_desc_cache_async(self):
        def _write():
            try:
                with self._lock:
                    snapshot = dict(self._description_cache)
                with open(self._problem_cache_file, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[LeetCodeAPI] cache write error: {e}")
        self._executor.submit(_write)

    def get_problem_description(self, titleSlug: str) -> str:
        """Return problem description. Served from memory/disk cache if available."""
        # 1. In-memory hit (instant)
        with self._lock:
            if titleSlug in self._description_cache:
                return self._description_cache[titleSlug]

        # 2. Fetch from LeetCode
        t0 = time.perf_counter()
        query = '''
        query questionData($titleSlug: String!) {
            question(titleSlug: $titleSlug) {
                content
            }
        }
        '''
        try:
            resp = requests.post(
                self.graphql_url,
                headers=self.HEADERS,
                json={"query": query, "variables": {"titleSlug": titleSlug}},
                timeout=10,
            )
            resp.raise_for_status()
            data    = resp.json()
            content = data.get("data", {}).get("question", {}).get("content", "")

            import re, html as _html
            text = re.sub(r"<[^>]+>", " ", content)
            text = re.sub(r"\s+", " ", text).strip()
            text = _html.unescape(text)

            elapsed = (time.perf_counter() - t0) * 1000
            print(f"[GraphQL] fetched description for {titleSlug} in {elapsed:.0f}ms")

            # Store in memory + async persist to disk
            with self._lock:
                self._description_cache[titleSlug] = text
            self._save_desc_cache_async()
            return text
        except Exception as e:
            print(f"[GraphQL] error for {titleSlug}: {e}")
            return ""
