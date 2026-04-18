import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from anthropic import Anthropic

# Define the structured output schema using Pydantic
class QueryFilter(BaseModel):
    geographic_scope: Optional[List[str]] = Field(
        default=None, 
        description="List of regions, countries, or continents mentioned in the query. Example: ['Africa', 'Middle East', 'Yemen']"
    )
    min_people_in_need: Optional[int] = Field(
        default=None, 
        description="The minimum number of people in need (PIN) required to filter the crises."
    )
    max_funding_coverage_percentage: Optional[float] = Field(
        default=None, 
        description="The maximum funding coverage percentage (0.0 to 100.0) mentioned. Example: 10% would be 10.0"
    )
    target_sectors: Optional[List[str]] = Field(
        default=None, 
        description="Specific humanitarian sectors mentioned, e.g., ['Food Security', 'Health', 'Shelter']"
    )
    is_multi_year_query: bool = Field(
        default=False, 
        description="True if the query explicitly asks for multi-year trends or consistently underfunded crises."
    )

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
            "Always use the `apply_filters` tool to output the structured data."
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
            # Convert the raw dictionary back into our Pydantic model to ensure validation
            return QueryFilter(**tool_call.input)
        
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
