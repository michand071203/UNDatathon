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
        "Which crises have more than 1000000 people in need but less than 25% fund allocations? Order them by the lowest funding coverage.",
        "Are there countries outside of the Middle East with active HRPs where funding is absent or negligible?",
        "Show me acute natural disaster hotspots that have received less than 10% of their requested funding, excluding Sudan, and rank them by highest people in need."
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
