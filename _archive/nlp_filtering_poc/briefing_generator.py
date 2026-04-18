import os
from typing import Optional
from anthropic import Anthropic
from archive.nlp_filtering_poc.models import CrisisData

class BriefingGenerator:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initializes the BriefingGenerator with the Anthropic API.
        """
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable.")
        self.client = Anthropic(api_key=key)
        # Using Opus or Sonnet for writing tasks usually yields better prose than Haiku,
        # but Haiku is still very good and much faster/cheaper. We'll use Haiku for the POC.
        self.model = "claude-3-haiku-20240307"

    def generate_briefing(self, crisis: CrisisData) -> str:
        """
        Generates a short, professional briefing note explaining why the crisis is ranked as overlooked.
        """
        
        system_prompt = (
            "You are a highly analytical, matter-of-fact humanitarian data scientist. "
            "Your job is to write a strictly objective, concise briefing paragraph (2-3 sentences max) analyzing "
            "the context and implications of the funding gap for the provided crisis. "
            "Assume the reader already sees the exact numbers (funding received, people in need) in a table next to your text. "
            "Do NOT simply repeat the numbers or mention a 'rank'. Instead, synthesize the financial context "
            "with the qualitative summary to explain the practical realities of the shortfall. "
            "CRITICAL: Maintain a clinical, dry, and purely factual tone. Do NOT use dramatic adjectives."
        )

        user_prompt = (
            f"Please generate an analytical briefing note for this crisis:\n\n"
            f"Country: {crisis.country}\n"
            f"People in Need (PIN): {crisis.total_people_in_need:,}\n"
            f"Funding Required: ${crisis.funding_required_usd:,.2f}\n"
            f"Funding Received: ${crisis.funding_received_usd:,.2f}\n"
            f"Funding Coverage: {crisis.funding_coverage_percentage}%\n\n"
            f"Qualitative Summary: {crisis.summary}"
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=250,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        return response.content[0].text
