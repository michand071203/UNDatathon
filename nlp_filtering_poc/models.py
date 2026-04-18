from typing import List, Optional
from pydantic import BaseModel, Field

class QueryFilter(BaseModel):
    geographic_scope: Optional[List[str]] = Field(
        default=None, 
        description="List of regions, countries, or continents mentioned in the query. Example: ['Africa', 'Middle East', 'Yemen']. Must be an array of strings. If not specified, return null."
    )
    min_people_in_need: Optional[int] = Field(
        default=None, 
        description="The minimum number of people in need (PIN) required to filter the crises. If not specified, return null."
    )
    max_funding_coverage_percentage: Optional[float] = Field(
        default=None, 
        description="The maximum funding coverage percentage (0.0 to 100.0) mentioned. Example: 10% would be 10.0. If not specified, return null."
    )
    target_sectors: Optional[List[str]] = Field(
        default=None, 
        description="Specific humanitarian sectors mentioned, e.g., ['Food Security', 'Health', 'Shelter']. Must be an array of strings. If not specified, return null."
    )
    is_multi_year_query: bool = Field(
        default=False, 
        description="True if the query explicitly asks for multi-year trends or consistently underfunded crises."
    )

class CrisisData(BaseModel):
    country: str
    total_people_in_need: int
    funding_required_usd: float
    funding_received_usd: float
    funding_coverage_percentage: float
    overlooked_rank: int
    summary: str
