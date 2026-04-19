import os
import json
import asyncio
import hashlib
from typing import Dict, List, Optional
from anthropic import Anthropic

CACHE_FILE = "crisis_summaries_cache.json"

class CrisisSummarizer:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=key) if key else None
        self.model = "claude-3-haiku-20240307"

    def _get_data_hash(self, data: List[dict]) -> str:
        data_string = json.dumps(data, sort_keys=True)
        return hashlib.md5(data_string.encode()).hexdigest()

    def load_cache(self, current_data: List[dict]) -> Optional[Dict[str, str]]:
        if not os.path.exists(CACHE_FILE):
            return None
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
        if cache.get("hash") == self._get_data_hash(current_data):
            return cache.get("summaries")
        return None

    def save_cache(self, data: List[dict], summaries: Dict[str, str]):
        cache = {"hash": self._get_data_hash(data), "summaries": summaries}
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)

    async def summarize_crisis(self, crisis: dict) -> str:
        if not self.client:
            return "No LLM API key provided. Summary unavailable."

        prompt = f"""
        Analyze this humanitarian crisis data: {json.dumps(crisis)}

        Explain why this crisis has an overall severity score of {crisis.get('overall_severity_score')}.
        Keep it concise (2-3 sentences), professional, and informative. Focus on the most critical drivers.
        """

        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=300,
                system="You are an expert humanitarian crisis analyst.",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text # type: ignore
        except Exception as e:
            return f"Summary could not be generated: {e}"

summaries: Dict[str, str] = {}
