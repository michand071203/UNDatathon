import os
from dotenv import load_dotenv
from models import CrisisData
from briefing_generator import BriefingGenerator

import json

def main():
    # Load environment variables from .env if present
    load_dotenv()
    
    try:
        generator = BriefingGenerator()
    except ValueError as e:
        print(f"Failed to initialize: {e}")
        print("Please ensure ANTHROPIC_API_KEY is set in your environment or .env file.")
        return

    # Load mock data from the JSON file
    json_path = os.path.join(os.path.dirname(__file__), "example_crises.json")
    try:
        with open(json_path, 'r') as f:
            crises_data = json.load(f)
            # Parse into Pydantic models
            crises = [CrisisData(**item) for item in crises_data]
    except Exception as e:
        print(f"Error loading {json_path}: {e}")
        return

    print("=== Testing Humanitarian LLM Briefing Generator ===\n")
    
    for crisis in crises:
        print(f"Processing {crisis.country} (Rank #{crisis.overlooked_rank})...")
        try:
            briefing = generator.generate_briefing(crisis)
            print("\n--- Generated Briefing Note ---")
            print(briefing)
            print("-" * 31 + "\n")
        except Exception as e:
            print(f"Error generating briefing: {e}")

if __name__ == "__main__":
    main()
