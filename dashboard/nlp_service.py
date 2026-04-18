import os
import json
import operator
from typing import List, Optional, Literal, TypeVar, Generic, Any, Dict, cast
from pydantic import BaseModel, Field, ValidationError, model_validator
from enum import Enum
from anthropic import Anthropic
from regions import REGION_NAMES


def _format_region_name_for_prompt(name: str) -> str:
    if name == "mena":
        return "MENA"
    return " ".join(part.capitalize() for part in name.split())

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
        try:
            return ops[self.operator](float(data_value), self.value)
        except (ValueError, TypeError):
            return False

class ListCondition(BaseModel):
    values: List[str]
    exclude: bool = False

    @model_validator(mode='before')
    @classmethod
    def wrap_list(cls, data: Any) -> Any:
        """Handle raw lists or stringified JSON lists from LLM."""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                pass
        if isinstance(data, list):
            return {"values": data}
        return data

    def evaluate(self, data_value: Any) -> bool:
        if data_value is None: return False
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

    @model_validator(mode='before')
    @classmethod
    def wrap_list(cls, data: Any) -> Any:
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                pass
        if isinstance(data, list):
            return {"values": data}
        return data

    def evaluate(self, data_value: Any) -> bool:
        if data_value is None: return False
        is_match = data_value in self.values
        return not is_match if self.exclude else is_match

class OrderDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"

class OrderCondition(BaseModel):
    field: str # Flexible field name for mapping
    direction: OrderDirection = OrderDirection.DESC
    
    @model_validator(mode='before')
    @classmethod
    def repair_order(cls, data: Any) -> Any:
        if isinstance(data, str):
            try: return json.loads(data)
            except: pass
        return data

class QueryFilter(BaseModel):
    locations: Optional[ListCondition] = None
    people_in_need: Optional[NumericCondition] = None
    funding_coverage_percentage: Optional[NumericCondition] = None
    severity_score: Optional[NumericCondition] = None
    sectors: Optional[ListCondition] = None
    crisis_type: Optional[EnumCondition[CrisisTypeEnum]] = None
    order_by: Optional[OrderCondition] = None
    limit: Optional[int] = Field(default=None, ge=1)

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
        self.region_names_text = ", ".join(
            _format_region_name_for_prompt(name) for name in REGION_NAMES
        )

    def parse_query(self, query: str) -> QueryFilter:
        if not self.client or not query.strip():
            return QueryFilter()

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
            "2. For numeric filters, infer the correct operator ('eq', 'gt', 'lt', 'gte', 'lte'). Use your judgment on when equality is actually desired. E.g., 'more than 10%' -> 'gte', 'less than 5' -> 'lt'.\n"
            "3. For list/enum filters, if the query implies negation (e.g., 'outside of the Middle East', 'excluding Sudan'), use the EXACT location/item mentioned and set the 'exclude' field to true. Do NOT try to list all the other alternatives.\n"
            f"4. Supported broad region labels are exactly: {self.region_names_text}. If the user requests one of these, output the exact region label text and do NOT expand it into countries.\n"
            "5. If the user names a geographic area that is not in the supported broad-region list, output your best-guess list of ISO-3 country codes for that area.\n"
            "6. If the query asks to sort or rank results (e.g., 'highest', 'lowest', 'most underfunded', 'ranked by severity'), set the 'order_by' field with the correct 'field' and 'direction' ('asc' or 'desc').\n"
            "7. If the query requests a top/bottom N subset (e.g., 'top 10', 'bottom 5'), set 'limit' to N.\n"
            "8. Map ranking terms carefully: 'ranked by severity' or 'most severe' -> order_by.field='severity_score'; 'most underfunded' -> order_by.field='funding_coverage_percentage' and direction='asc'."
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
            if tool_call.type == "tool_use" and tool_call.name == "apply_filters":
                # 1. Cast to dict to solve Pylance "object" error
                # 2. Use model_validate which handles nested validation more robustly
                raw_input = cast(Dict[str, Any], tool_call.input)
                
                # Pre-process top-level stringified JSON (common in LLM tool calls)
                processed_input = {}
                for k, v in raw_input.items():
                    if isinstance(v, str) and (v.startswith('[') or v.startswith('{')):
                        try:
                            processed_input[k] = json.loads(v)
                        except:
                            processed_input[k] = v
                    else:
                        processed_input[k] = v

                return QueryFilter.model_validate(processed_input)
        except Exception as e:
            print(f"NLP Error: {e}")
            return QueryFilter()
        
        return QueryFilter()
