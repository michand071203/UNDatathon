import json
from query_parser import QueryParser
from dotenv import load_dotenv

def main():
    # Load environment variables from .env if present
    load_dotenv()
    
    try:
        parser = QueryParser()
    except ValueError as e:
        print(f"Failed to initialize: {e}")
        print("Please ensure ANTHROPIC_API_KEY is set in your environment or .env file.")
        return

    example_queries = [
        "Which crises have the highest proportion of people in need but the lowest fund allocations?",
        "Are there countries in the Middle East with active HRPs where funding is absent or negligible?",
        "Which regions are consistently underfunded relative to need across multiple years?",
        "Show me acute food insecurity hotspots that have received less than 10% of their requested funding."
    ]

    print("=== Testing Humanitarian LLM Query Parser ===")
    
    for query in example_queries:
        print(f"\nQuery: '{query}'")
        try:
            result = parser.parse_query(query)
            # Output the resulting JSON clearly
            print(json.dumps(result.model_dump(), indent=2))
        except Exception as e:
            print(f"Error parsing query: {e}")

if __name__ == "__main__":
    main()
