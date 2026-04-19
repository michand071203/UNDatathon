import os
import json
import asyncio
import hashlib
from typing import Dict, List, Optional
from anthropic import Anthropic

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, "..", "crisis_summaries_cache_v2.json")


class CrisisSummarizer:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=key) if key else None
        self.model = "claude-sonnet-4-6"

    def _get_file_hash(self, file_path: str) -> Optional[str]:
        if not os.path.exists(file_path):
            return None

        digest = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def load_cache(self, source_file_path: str) -> Optional[Dict[str, str]]:
        source_hash = self._get_file_hash(source_file_path)
        if source_hash is None:
            return None
        if not os.path.exists(CACHE_FILE):
            return None

        try:
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

        if cache.get("source_hash") == source_hash and cache.get("model") == self.model:
            summaries = cache.get("summaries")
            if isinstance(summaries, dict):
                return summaries
        return None

    def save_cache(self, source_file_path: str, summaries: Dict[str, str]):
        source_hash = self._get_file_hash(source_file_path)
        if source_hash is None:
            return

        cache = {
            "source_file": source_file_path,
            "source_hash": source_hash,
            "model": self.model,
            "summaries": summaries,
        }
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)

    async def summarize_crisis(self, crisis: dict) -> str:
        if not self.client:
            return "No LLM API key provided. Summary unavailable."

        # Extract only the most relevant fields for the LLM to reduce noise
        relevant_data = {
            "name": crisis.get("name"),
            "locations": crisis.get("location_names_display"),
            "assessment": crisis.get("assessment"),
            "assessment_rank": crisis.get("assessment_rank"),
            "underfunding_drivers": crisis.get("underfunding_drivers"),
            "underfunding_driver_confidence": crisis.get("underfunding_driver_confidence"),
            "people_in_need": crisis.get("people_in_need"),
            "funding_requirements": crisis.get("requirements"),
            "funding_received": crisis.get("funding"),
            "percent_funded": crisis.get("percent_funded"),
        }

        prompt = f"""
        Analyze this humanitarian crisis data: {json.dumps(relevant_data)}

        Explain why this crisis has an assessment of "{crisis.get('assessment')}" and detail the main underfunding drivers.
        Keep it concise (2-3 sentences), professional, and informative. Focus on the most critical drivers.
        No need to output tables or lists, just a clear text summary.
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
