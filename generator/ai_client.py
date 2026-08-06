"""
generator/ai_client.py
──────────────────────
Lean AI client used exclusively by the Generator Worker.
Never called by the Main Bot.

Two separate requests:
  • generate_hints()   – tiny prompt (~200 tokens) → fast
  • generate_solution() – compact prompt (~400 tokens)
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class AIClient:
    def __init__(self):
        self.base_url = os.getenv("AI_BASE_URL", "http://localhost:20128/v1")
        self.api_key  = os.getenv("AI_API_KEY", "")
        self.model    = os.getenv("AI_MODEL", "oc/deepseek-v4-flash-free")

    def _call(self, prompt: str, label: str) -> Optional[str]:
        t0 = time.perf_counter()
        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system",
                 "content": "You are a LeetCode AI tutor. Output ONLY raw valid JSON. No markdown. No extra text."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers, json=payload, timeout=90,
            )
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            raw = resp.text
            content = ""

            if raw.lstrip().startswith("data:"):
                for line in raw.splitlines():
                    if line.startswith("data: "):
                        chunk_str = line[6:].strip()
                        if chunk_str == "[DONE]":
                            break
                        try:
                            chunk   = json.loads(chunk_str)
                            delta   = chunk.get("choices", [{}])[0].get("delta", {})
                            content += delta.get("content", "")
                        except Exception:
                            pass
            else:
                data    = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            ms = (time.perf_counter() - t0) * 1000
            logger.info(f"[AI][{label}] {ms:.0f}ms")
            return content.strip()

        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            logger.error(f"[AI][{label}] FAILED {ms:.0f}ms – {e}")
            return None

    @staticmethod
    def _clean(raw: str) -> str:
        s = raw.strip()
        start = s.find('{')
        end = s.rfind('}')
        if start != -1 and end != -1 and end > start:
            return s[start:end+1]
        return s

    def generate_hints(self, slug: str, title: str, difficulty: str,
                       description: str, language: str) -> Optional[List[str]]:
        """Returns list of 3 progressive hints, or None on failure."""
        desc = description[:600] if len(description) > 600 else description
        prompt = (
            f"Problem: {title}\n"
            f"Difficulty: {difficulty}\n"
            f"Language: {language}\n"
            f"Description:\n{desc}\n\n"
            'Return ONLY this JSON:\n'
            '{"hints":["gentle nudge","core concept hint","near-complete logic hint"]}'
        )
        raw = self._call(prompt, f"hints/{slug}/{language}")
        if not raw:
            return None
        try:
            return json.loads(self._clean(raw)).get("hints")
        except Exception as e:
            logger.error(f"[AI] hints parse error: {e} | raw={raw[:200]}")
            return None

    def generate_solution(self, slug: str, title: str, difficulty: str,
                          description: str, language: str) -> Optional[Dict]:
        """Returns solution dict with approach/time/space/code, or None on failure."""
        desc = description[:800] if len(description) > 800 else description
        prompt = (
            f"Problem: {title}\n"
            f"Language: {language}\n"
            f"Difficulty: {difficulty}\n"
            f"Description:\n{desc}\n\n"
            "Return ONLY this JSON with clean formatting:\n"
            '{"intuition":"A short clear explanation using bullet points","key_idea":"The core mathematical or logical trick used, use bullet points","step_by_step":"A numbered list using 1️⃣ 2️⃣ emojis","time_complexity":"O(?)","space_complexity":"O(?)","code":"complete working code"}'
        )
        raw = self._call(prompt, f"solution/{slug}/{language}")
        if not raw:
            return None
        try:
            p = json.loads(self._clean(raw))
            return {
                "approach":     p.get("approach", ""),
                "intuition":    p.get("intuition", ""),
                "key_idea":     p.get("key_idea", ""),
                "step_by_step": p.get("step_by_step", ""),
                "time":         p.get("time_complexity", "O(?)"),
                "space":        p.get("space_complexity", "O(?)"),
                "code":         p.get("code", ""),
            }
        except Exception as e:
            logger.error(f"[AI] solution parse error: {e} | raw={raw[:200]}")
            return None
