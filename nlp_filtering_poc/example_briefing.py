import os
from dotenv import load_dotenv
from models import CrisisData
from briefing_generator import BriefingGenerator

def main():
    # Load environment variables from .env if present
    load_dotenv()
    
    try:
        generator = BriefingGenerator()
    except ValueError as e:
        print(f"Failed to initialize: {e}")
        print("Please ensure ANTHROPIC_API_KEY is set in your environment or .env file.")
        return

    # Mock data representing the #1 ranked crisis after our gap-scoring pipeline runs
    sudan_crisis = CrisisData(
        country="Sudan",
        total_people_in_need=24800000,
        funding_required_usd=2700000000.00,
        funding_received_usd=405000000.00,
        funding_coverage_percentage=15.0,
        overlooked_rank=1,
        summary="Sudan is experiencing one of the fastest-growing displacement crises in the world due to widespread conflict between rival factions. The violence has devastated agricultural production and severely limited humanitarian access, pushing millions toward famine conditions, particularly in Darfur and Khartoum."
    )
    
    # A second mock example
    haiti_crisis = CrisisData(
        country="Haiti",
        total_people_in_need=5500000,
        funding_required_usd=674000000.00,
        funding_received_usd=40440000.00,
        funding_coverage_percentage=6.0,
        overlooked_rank=2,
        summary="Surging gang violence in Port-au-Prince has completely disrupted supply chains and forced hundreds of thousands from their homes. Health systems are collapsing, and there is a critical shortage of clean water, leading to localized cholera outbreaks amid soaring inflation."
    )

    print("=== Testing Humanitarian LLM Briefing Generator ===\n")
    
    for crisis in [sudan_crisis, haiti_crisis]:
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
