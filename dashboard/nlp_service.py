import os
import json
import operator
from typing import List, Optional, Literal, TypeVar, Generic, Any
from pydantic import BaseModel, Field, ValidationError
from enum import Enum
from anthropic import Anthropic

# --- Models with Dynamic Evaluation Logic ---

T = TypeVar('T', bound=Enum)

class NumericCondition(BaseModel):
    value: float
    operator: Literal["eq", "gt", "lt", "gte", "lte"]

    def evaluate(self, data_value: Any) -> bool:
        if data_value is None: return False
        ops = {
            "eq": operator.eq,
            "gt": operator.gt,
            "lt": operator.lt,
            "gte": operator.ge,
            "lte": operator.le
        }
        return ops[self.operator](float(data_value), self.value)

class ListCondition(BaseModel):
    values: List[str]
    exclude: bool = False

    def evaluate(self, data_value: Any) -> bool:
        if data_value is None: return False
        # Normalize for comparison
        target = str(data_value).upper()
        check_list = [v.upper() for v in self.values]
        is_match = target in check_list
        return not is_match if self.exclude else is_match

class CrisisTypeEnum(str, Enum):
    CONFLICT = "conflict"
    NATURAL_DISASTER = "natural_disaster"
    COMPLEX_EMERGENCY = "complex_emergency"
    DISEASE_OUTBREAK = "disease_outbreak"

class EnumCondition(BaseModel, Generic[T]):
    values: List[T]
    exclude: bool = False

    def evaluate(self, data_value: Any) -> bool:
        if data_value is None: return False
        is_match = data_value in self.values
        return not is_match if self.exclude else is_match

class OrderDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"

class OrderCondition(BaseModel):
    field: Literal["people_in_need", "funding_coverage_percentage", "funding_required_usd", "funding_received_usd", "overlooked_rank"]
    direction: OrderDirection = OrderDirection.DESC

class QueryFilter(BaseModel):
    locations: Optional[ListCondition] = None
    people_in_need: Optional[NumericCondition] = None
    funding_coverage_percentage: Optional[NumericCondition] = None
    sectors: Optional[ListCondition] = None
    crisis_type: Optional[EnumCondition[CrisisTypeEnum]] = None
    order_by: Optional[OrderCondition] = None

# --- Parser ---

class QueryParser:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            self.client = None
            print("Warning: ANTHROPIC_API_KEY not found. NLP parsing will use mock response.")
        else:
            self.client = Anthropic(api_key=key)
        self.model = "claude-3-haiku-20240307"
        
        print(f"NLP Service initialized with model: {self.model}")

    def parse_query(self, query: str) -> QueryFilter:
        if not self.client or not query.strip():
            print("NLP error: No API key or empty query. Returning empty filter.")
            return QueryFilter()
        
        print(f"Querying LLM with: {query}")

        tool_schema = {
            "name": "apply_filters",
            "description": "Apply filters based on the user's natural language query.",
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

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                tools=[tool_schema], # type: ignore
                tool_choice={"type": "tool", "name": "apply_filters"},
                messages=[{"role": "user", "content": query}]
            )

            tool_call = response.content[0]
            print(f"LLM Tool Call: {tool_call}")
            if tool_call.type == "tool_use" and tool_call.name == "apply_filters":
                # Parse any string values in the input that should be objects
                parsed_input = {}
                for key, value in tool_call.input.items():
                    if isinstance(value, str):
                        try:
                            parsed_input[key] = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            parsed_input[key] = value
                    else:
                        parsed_input[key] = value
                
                # Handle list condition fields that the LLM might output as lists instead of dicts
                list_condition_fields = ['locations', 'sectors', 'crisis_type']
                for field in list_condition_fields:
                    if field in parsed_input and isinstance(parsed_input[field], list):
                        parsed_input[field] = {'values': parsed_input[field]}
                
                return QueryFilter(**parsed_input) # type: ignore
        except Exception as e:
            print(f"NLP Error: {e}")
            return QueryFilter()
        
        return QueryFilter()
