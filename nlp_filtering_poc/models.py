from typing import List, Optional, Literal, TypeVar, Generic
from pydantic import BaseModel, Field
from enum import Enum

T = TypeVar('T', bound=Enum)

class NumericCondition(BaseModel):
    value: float
    operator: Literal["eq", "gt", "lt", "gte", "lte"] = Field(description="Operator: equal (eq), greater than (gt), less than (lt), greater than or equal (gte), less than or equal (lte)")

class ListCondition(BaseModel):
    values: List[str] = Field(description="List of strings to filter by.")
    exclude: bool = Field(default=False, description="If true, EXCLUDE these values (negation).")

class CrisisTypeEnum(str, Enum):
    CONFLICT = "conflict"
    NATURAL_DISASTER = "natural_disaster"
    COMPLEX_EMERGENCY = "complex_emergency"
    DISEASE_OUTBREAK = "disease_outbreak"

class EnumCondition(BaseModel, Generic[T]):
    values: List[T] = Field(description="List of enum values to filter by.")
    exclude: bool = Field(default=False, description="If true, EXCLUDE these values (negation).")

class QueryFilter(BaseModel):
    locations: Optional[ListCondition] = Field(
        default=None, 
        description="Countries, regions, or continents. Output standard ISO-3 codes for specific countries (e.g., 'SDN', 'HTI'). If a broad region is mentioned, output the exact region name (e.g., 'Africa', 'Middle East')."
    )
    people_in_need: Optional[NumericCondition] = Field(default=None, description="Filter by People in Need (PIN).")
    funding_coverage_percentage: Optional[NumericCondition] = Field(default=None, description="Filter by funding coverage % (0-100).")
    sectors: Optional[ListCondition] = Field(default=None, description="Humanitarian sectors (e.g., 'Health', 'Food Security').")
    crisis_type: Optional[EnumCondition[CrisisTypeEnum]] = Field(default=None, description="Filter by the type of crisis.")
    is_multi_year_query: bool = Field(default=False)

class CrisisData(BaseModel):
    country: str
    total_people_in_need: int
    funding_required_usd: float
    funding_received_usd: float
    funding_coverage_percentage: float
    overlooked_rank: int
    summary: str
