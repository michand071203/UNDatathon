import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from anthropic import Anthropic

from archive.nlp_filtering_poc.models import QueryFilter

from pydantic import ValidationError

class QueryParser:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initializes the QueryParser with the Anthropic API.
        If api_key is not provided, it will look for ANTHROPIC_API_KEY in the environment.
        """
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable.")
        self.client = Anthropic(api_key=key)
        self.model = "claude-3-haiku-20240307" # Haiku is fast and good enough for this parsing task

    def parse_query(self, query: str) -> QueryFilter:
        """
        Takes a natural language query and returns a structured QueryFilter object.
        """
        
        # We use Claude's tool use feature to force it to return data matching our schema.
        # We define a tool that takes the exact arguments of our Pydantic model.
        tool_schema = {
            "name": "apply_filters",
            "description": "Apply filters based on the user's natural language query about humanitarian crises.",
            "input_schema": QueryFilter.model_json_schema()
        }

        system_prompt = (
            "You are an expert humanitarian data analyst. "
            "Your task is to take a natural language query about humanitarian crises, funding gaps, "
            "and needs, and extract the precise filtering parameters. "
            "Always use the `apply_filters` tool to output the structured data. "
            "IMPORTANT RULES:\n"
            "1. Pay strict attention to the data types. If a value is missing or unknown, omit the field or return a literal JSON null.\n"
            "2. For numeric filters, infer the correct operator ('eq', 'gt', 'lt', 'gte', 'lte'). E.g., 'more than 10%' -> 'gt', 'less than 5' -> 'lt'.\n"
            "3. For list/enum filters, if the query implies negation (e.g., 'outside of the Middle East', 'excluding Sudan'), use the EXACT location/item mentioned and set the 'exclude' field to true. Do NOT try to list all the other alternatives.\n"
            "4. For geographic locations, output standard ISO-3 codes for specific countries (e.g. 'SDN', 'HTI'). If a broad region is mentioned, output the exact region name (e.g. 'Africa', 'Middle East').\n"
            "5. If the query asks to sort or rank results (e.g., 'highest', 'lowest', 'most underfunded'), set the 'order_by' field with the correct 'field' and 'direction' ('asc' or 'desc')."
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            tools=[tool_schema],
            tool_choice={"type": "tool", "name": "apply_filters"},
            messages=[
                {"role": "user", "content": query}
            ]
        )

        # Extract the tool use arguments
        tool_call = response.content[0]
        if tool_call.type == "tool_use" and tool_call.name == "apply_filters":
            try:
                # Convert the raw dictionary back into our Pydantic model to ensure validation
                return QueryFilter(**tool_call.input)
            except ValidationError as e:
                # Descriptive error formatting
                error_msg = "The NLP engine generated an invalid filter format.\nDetails:\n"
                for err in e.errors():
                    loc = " -> ".join([str(l) for l in err["loc"]])
                    error_msg += f" - Field '{loc}': {err['msg']} (Got: {err.get('input')})\n"
                
                print(f"\n[Warning] {error_msg}")
                print("[Fallback] Returning an empty QueryFilter to prevent crash.\n")
                return QueryFilter()
        
        raise RuntimeError(f"Unexpected response format from Claude: {response.content}")

if __name__ == "__main__":
    # A quick test if run directly (requires API key in env)
    from dotenv import load_dotenv
    load_dotenv()
    
    try:
        parser = QueryParser()
        test_query = "Show me acute food insecurity hotspots in Africa that have received less than 10% of their requested funding."
        print(f"Query: {test_query}")
        print("-" * 20)
        result = parser.parse_query(test_query)
        print(json.dumps(result.model_dump(), indent=2))
    except Exception as e:
        print(f"Error during quick test: {e}")
