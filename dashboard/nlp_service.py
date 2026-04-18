import os
import json
import re
import operator
from typing import List, Optional, Literal, TypeVar, Generic, Any, Dict, cast, ClassVar
from pydantic import BaseModel, Field, ValidationError, model_validator
from enum import Enum
from anthropic import Anthropic
from regions import REGION_NAMES

try:
    from fastembed import TextEmbedding
except ImportError:
    TextEmbedding = None


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


class StringCondition(BaseModel):
    value: str

    _EMBEDDING_THRESHOLD: ClassVar[float] = 0.72
    _embedder: ClassVar[Any] = None
    _embedder_init_failed: ClassVar[bool] = False
    _embedding_cache: ClassVar[Dict[str, List[float]]] = {}
    _TOKEN_SYNONYMS: ClassVar[Dict[str, str]] = {
        "migrant": "displacement",
        "migrants": "displacement",
        "migration": "displacement",
        "refugee": "displacement",
        "refugees": "displacement",
        "displaced": "displacement",
        "idp": "displacement",
        "idps": "displacement",
        "crisis": "emergency",
        "humanitarian": "emergency",
        "response": "response",
        "plan": "response",
    }
    _STOPWORDS: ClassVar[set[str]] = {
        "the",
        "a",
        "an",
        "and",
        "for",
        "of",
        "to",
        "in",
        "regional",
        "region",
        "needs",
        "year",
    }

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = re.sub(r"[^\w\s]", " ", value.lower())
        return re.sub(r"\s+", " ", normalized).strip()

    @classmethod
    def _project_text(cls, value: str) -> str:
        normalized = cls._normalize_text(value)
        tokens = normalized.split()
        projected_tokens: List[str] = []
        for token in tokens:
            if token.isdigit():
                continue
            if len(token) == 4 and token.startswith("20"):
                continue
            canonical = cls._TOKEN_SYNONYMS.get(token, token)
            if canonical in cls._STOPWORDS:
                continue
            projected_tokens.append(canonical)
        return " ".join(projected_tokens)

    @classmethod
    def _get_embedder(cls) -> Any:
        if cls._embedder is not None:
            return cls._embedder
        if cls._embedder_init_failed or TextEmbedding is None:
            return None
        try:
            cls._embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            return cls._embedder
        except Exception:
            cls._embedder_init_failed = True
            return None

    @classmethod
    def _embedding_for_text(cls, text: str) -> Optional[List[float]]:
        if text in cls._embedding_cache:
            return cls._embedding_cache[text]

        embedder = cls._get_embedder()
        if embedder is None:
            return None

        try:
            vectors = list(embedder.embed([text]))
            if not vectors:
                return None
            vector = [float(value) for value in vectors[0]]
            cls._embedding_cache[text] = vector
            return vector
        except Exception:
            return None

    @staticmethod
    def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _token_overlap_ratio(text_a: str, text_b: str) -> float:
        tokens_a = set(text_a.split())
        tokens_b = set(text_b.split())
        if not tokens_a or not tokens_b:
            return 0.0
        overlap = len(tokens_a.intersection(tokens_b))
        return overlap / min(len(tokens_a), len(tokens_b))

    @model_validator(mode='before')
    @classmethod
    def wrap_string(cls, data: Any) -> Any:
        """Handle raw strings from LLM tool calls."""
        if isinstance(data, str):
            return {"value": data}
        return data

    def evaluate(self, data_value: Any) -> bool:
        if data_value is None:
            return False

        target = self._normalize_text(str(data_value))
        candidate = self._normalize_text(self.value)
        target_projected = self._project_text(str(data_value))
        candidate_projected = self._project_text(self.value)
        if not target or not candidate:
            return False

        if target == candidate:
            return True

        if len(target) >= 4 and len(candidate) >= 4:
            if candidate in target or target in candidate:
                return True

            if candidate_projected and target_projected:
                if (
                    candidate_projected in target_projected
                    or target_projected in candidate_projected
                ):
                    return True

                if self._token_overlap_ratio(target_projected, candidate_projected) >= 0.5:
                    return True

            target_embedding = self._embedding_for_text(target)
            candidate_embedding = self._embedding_for_text(candidate)
            if target_embedding is not None and candidate_embedding is not None:
                similarity = self._cosine_similarity(target_embedding, candidate_embedding)
                return similarity >= self._EMBEDDING_THRESHOLD

        return False

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
    crisis_name: Optional[StringCondition] = None
    locations: Optional[ListCondition] = None
    people_in_need: Optional[NumericCondition] = None
    funding_coverage_percentage: Optional[NumericCondition] = None
    severity_score: Optional[NumericCondition] = None
    sectors: Optional[ListCondition] = None
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

    def _normalize_percentage_conditions(self, query: str, parsed_filter: QueryFilter) -> QueryFilter:
        """Ensure percentage fields use percent units (e.g. 10 for 10%), not ratios (0.1)."""
        percent_matches = re.findall(r"(\d+(?:\.\d+)?)\s*%", query)
        if not percent_matches:
            return parsed_filter

        query_percents = [float(match) for match in percent_matches]
        percentage_fields = ["funding_coverage_percentage"]

        for field_name in percentage_fields:
            condition = getattr(parsed_filter, field_name, None)
            if not isinstance(condition, NumericCondition):
                continue

            value = float(condition.value)

            # If the model returned a ratio for an explicit percentage query
            # (e.g. query 10% -> value 0.1), convert it to percent units.
            for q_percent in query_percents:
                if q_percent > 1 and abs(value - (q_percent / 100.0)) < 1e-9:
                    condition.value = q_percent
                    break

        return parsed_filter

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
            "8. Map ranking terms carefully: 'ranked by severity' or 'most severe' -> order_by.field='severity_score'; 'most underfunded' -> order_by.field='funding_coverage_percentage' and direction='asc'.\n"
            "9. If the user references one or more specific crisis names, use 'crisis_name' with those names.\n"
            "10. If a phrase looks like a crisis name, use the user's wording for 'crisis_name' and keep it close to the original phrase; light normalization is allowed (e.g., case/punctuation), but do not expand or paraphrase it, e.g. 'Sudan migrant crisis'."
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

                parsed_filter = QueryFilter.model_validate(processed_input)
                return self._normalize_percentage_conditions(query, parsed_filter)
        except Exception as e:
            print(f"NLP Error: {e}")
            return QueryFilter()
        
        return QueryFilter()
