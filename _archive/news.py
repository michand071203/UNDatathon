import os
import json
import time
from typing import List, Dict, Any, cast
from pydantic import BaseModel, Field
from anthropic import Anthropic
from newsapi import NewsApiClient
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Structured Output Models ---

class KeywordList(BaseModel):
    keywords: List[str] = Field(..., description="A short list of keywords to filter for news stories directly about this particular crisis.")

# --- Functions ---

def get_crisis_keywords(crisis_name: str, location: str, un_code: str) -> List[str]:
    """
    Uses Anthropic LLM to get a list of relevant keywords for a crisis.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Warning: ANTHROPIC_API_KEY not found. Using crisis name as keyword.")
        return [crisis_name]
    
    client = Anthropic(api_key=api_key)
    model = "claude-3-haiku-20240307"

    tool_schema = {
        "name": "provide_keywords",
        "description": "Provide a list of keywords for news search.",
        "input_schema": KeywordList.model_json_schema()
    }

    system_prompt = (
        "You are an expert in humanitarian crises. "
        "Your task is to provide a short list of 3-5 precise keywords or phrases that can be used "
        "to search for news articles directly about the specified humanitarian crisis. "
        "The keywords should be specific enough to avoid unrelated news but broad enough to capture relevant updates."
        "The UN code is the UN 'Funding Base Key' used by the FTS database to track humanitarian crisis funding projects."
        "Use the crisis name, location, and UN code to identify the relevant humanitarian crisis and generate the news search keywords."
    )

    user_prompt = f"Crisis Name: {crisis_name}\nLocation: {location}\nUN Code: {un_code}\n\nPlease provide the keywords in a JSON format according to the tool schema."

    try:
        response = client.messages.create(
            model=model,
            max_tokens=512,
            system=system_prompt,
            tools=[tool_schema], # type: ignore
            tool_choice={"type": "tool", "name": "provide_keywords"},
            messages=[{"role": "user", "content": user_prompt}]
        )

        tool_call = response.content[0]
        if tool_call.type == "tool_use" and tool_call.name == "provide_keywords":
            raw_input = cast(Dict[str, Any], tool_call.input)
            validated = KeywordList.model_validate(raw_input)
            return validated.keywords
    except Exception as e:
        print(f"Error getting keywords for {crisis_name}: {e}")
    
    return [crisis_name]

def collect_news_data():
    """
    Iterates through crises, fetches news stories, and saves to news.json.
    """
    news_api_key = os.getenv("NEWS_API_KEY")
    if not news_api_key:
        raise ValueError("NEWS_API_KEY not found in environment variables")
    
    newsapi = NewsApiClient(api_key=news_api_key)
    
    # Load crises
    data_path = os.path.join(BASE_DIR, "..", "data_pipeline", "crisis_summary_all_years.json")
    if not os.path.exists(data_path):
        # Fallback if the path is relative to the project root vs script location
        return print(f"Data file not found at {data_path}. Please ensure the path is correct.")

    with open(data_path, "r") as f:
        crises = json.load(f)

    all_news_data = {}

    print(f"Processing {len(crises)} crises...")

    for crisis in crises:
        if "2026" not in crisis.get("years", {}):
            continue
        code = crisis.get("funding_base_key")
        name = crisis.get("years", {}).get("2026", {}).get("names", [None])[0]
        location = crisis.get("primary_location_name", "Unknown Location")

        if not name or not code:
            continue

        print(f"Fetching news for: {name} ({code})")
        
        # 1. Get keywords
        keywords = get_crisis_keywords(name, location, code)
        query = " OR ".join([f'({kw})' for kw in keywords])
        
        try:
            # 2. Fetch news (Everything endpoint, restricted to 1 month back due to plan)
            # Fetching 100 articles (max for one request)
            articles_response = newsapi.get_everything(
                q=query,
                language='en',
                sort_by='popularity',
                page_size=100
            )
            
            if articles_response.get("status") == "ok":
                all_news_data[code] = {
                    "crisis_name": name,
                    "keywords": keywords,
                    "total_results": articles_response.get("totalResults", 0),
                    "articles": articles_response.get("articles", [])
                }
            else:
                print(f"NewsAPI error for {code}: {articles_response.get('message')}")
                all_news_data[code] = {"error": articles_response.get("message")}
        except Exception as e:
            print(f"Error fetching news for {code}: {e}")
            all_news_data[code] = {"error": str(e)}
        
        # Small delay to avoid hitting rate limits too fast (though 30 requests is fine)
        time.sleep(0.5)

    # Save to news.json
    output_path = "news.json"
    with open(output_path, "w") as f:
        json.dump(all_news_data, f, indent=2)
    
    print(f"Done! Saved news data for {len(all_news_data)} crises to {output_path}")

if __name__ == "__main__":
    collect_news_data()
    # print(get_crisis_keywords("Afghanistan Humanitarian Needs and Responses Plan 2026", "Afghanistan", "CAFG"))
