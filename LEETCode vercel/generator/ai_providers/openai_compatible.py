import json
import logging
import time
from typing import Dict, Optional
import requests

from generator.ai_providers.base import BaseAIProvider

logger = logging.getLogger(__name__)

class OpenAICompatibleProvider(BaseAIProvider):
    def __init__(self, base_url: str, api_key: str, model: str, name: str = "openai"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.name = name
        
    def _clean(self, raw: str) -> str:
        s = raw.strip()
        start = s.find('{')
        end = s.rfind('}')
        if start != -1 and end != -1 and end > start:
            return s[start:end+1]
        return s

    def generate_solution(self, slug: str, title: str, difficulty: str, description: str) -> Optional[Dict]:
        desc = description[:1500] if len(description) > 1500 else description
        
        prompt = (
            f"Problem: {title}\n"
            f"Difficulty: {difficulty}\n"
            f"Description:\n{desc}\n\n"
            "Return ONLY a single valid JSON object containing the complete solution for all 5 languages (Java, Python, C++, C, JavaScript). No markdown, no extra text.\n"
            "The JSON schema must exactly match the following structure:\n"
            "{\n"
            '  "problem_summary": "A short summary",\n'
            '  "intuition": "A short clear explanation using bullet points",\n'
            '  "key_idea": "The core mathematical or logical trick used, use bullet points",\n'
            '  "step_by_step": "A numbered list using 1️⃣ 2️⃣ emojis",\n'
            '  "time_complexity": "O(?)",\n'
            '  "space_complexity": "O(?)",\n'
            '  "hints": ["hint 1", "hint 2", "hint 3"],\n'
            '  "java": "complete working code",\n'
            '  "python": "complete working code",\n'
            '  "cpp": "complete working code",\n'
            '  "c": "complete working code",\n'
            '  "javascript": "complete working code"\n'
            "}"
        )
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a LeetCode AI tutor. Output ONLY raw valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }

        t0 = time.perf_counter()
        try:
            # Note: We omit response_format for models that don't support it strictly, 
            # but deepseek/openai/openrouter generally support it.
            # To be safe across all compatible APIs, we try without response_format if it fails,
            # or we just let it generate regular JSON since the prompt is strong.
            if "deepseek" in self.model.lower() or "gemini" in self.model.lower():
                payload.pop("response_format", None)

            resp = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=payload, timeout=120)
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
                            chunk = json.loads(chunk_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content += delta.get("content", "")
                        except Exception:
                            pass
            else:
                try:
                    data = resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                except Exception as e:
                    logger.error(f"Failed to parse JSON response. Raw: {raw[:200]}")
                    raise e
            
            ms = (time.perf_counter() - t0) * 1000
            logger.info(f"[AI][{self.name}] {ms:.0f}ms - {slug}")
            
            cleaned = self._clean(content)
            return json.loads(cleaned)
            
        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            logger.error(f"[AI][{self.name}] FAILED {ms:.0f}ms - {slug} - {e}")
            return None
