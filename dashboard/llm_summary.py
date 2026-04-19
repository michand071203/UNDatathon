import os
import json
import asyncio
from anthropic import Anthropic
from typing import Dict, Optional

class CrisisSummarizer:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=key) if key else None
        self.model = "claude-3-haiku-20240307"

    async def summarize_crisis(self, crisis: dict) -> str:
        if not self.client:
            return "No LLM API key provided. Summary unavailable."

        prompt = f"""
        Analyze this humanitarian crisis data: {json.dumps(crisis)}
        
        Explain why this crisis has an overall severity score of {crisis.get('assessment')}.
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
