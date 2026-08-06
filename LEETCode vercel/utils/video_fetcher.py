import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional
import yt_dlp

logger = logging.getLogger(__name__)

class VideoFetcher:
    def __init__(self, cache_file: str = "database/video_cache.json"):
        self.cache_file = cache_file
        self.cache = self._load_cache()
        # Ensure database directory exists
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        
        # Priority order for creators as requested
        self.priority_creators = [
            "NeetCode",
            "take U forward",
            "Nick White",
            "CodeHelp"
        ]

    def _load_cache(self) -> Dict:
        """Load video cache from JSON file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading video cache: {e}")
                return {}
        return {}

    def _save_cache(self):
        """Save video cache to JSON file."""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f, indent=4)
        except IOError as e:
            logger.error(f"Error saving video cache: {e}")

    def _search_youtube(self, query: str) -> Optional[Dict]:
        """Search YouTube using yt-dlp and return the first result."""
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_generic_extractor': False,
            'default_search': 'ytsearch1',
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # ytsearch1: searches and returns only the first result
                result = ydl.extract_info(f"ytsearch1:{query}", download=False)
                
                if 'entries' in result and result['entries']:
                    entry = result['entries'][0]
                    return {
                        "url": entry.get("url"),
                        "title": entry.get("title", "Unknown Title"),
                        "channel": entry.get("uploader", "Unknown Channel")
                    }
        except Exception as e:
            logger.error(f"YouTube search failed for query '{query}': {e}")
            
        return None

    def get_video_solution(self, problem_slug: str, problem_title: str) -> Optional[Dict]:
        """
        Get the best video solution for a LeetCode problem.
        Checks cache first, otherwise searches YouTube.
        """
        # 1. Check Cache
        if problem_slug in self.cache:
            logger.info(f"Cache hit for video solution: {problem_slug}")
            return self.cache[problem_slug]
            
        logger.info(f"Cache miss for video solution: {problem_slug}. Searching YouTube...")
        
        # 2. Search YouTube with an optimized query to find the best solution in one shot
        # We include common creator names in the search to help YouTube rank them higher
        query = f"LeetCode {problem_title} solution NeetCode OR CodeHelp OR take U forward"
        best_result = self._search_youtube(query)
            
            
        # 4. Save to cache and return
        if best_result and best_result.get('url'):
            cache_entry = {
                "url": best_result["url"],
                "title": best_result["title"],
                "channel": best_result["channel"],
                "cached_at": datetime.utcnow().isoformat() + "Z"
            }
            
            self.cache[problem_slug] = cache_entry
            self._save_cache()
            return cache_entry
            
        return None
