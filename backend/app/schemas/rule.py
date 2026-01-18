
from pydantic import BaseModel
from typing import Optional

class RuleBase(BaseModel):
    pattern: str
    match_type: str = "contains"  # 'contains' or 'regex'
    source_column: str = "description"
    merchant: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    conditions: Optional[str] = None
    priority: int = 10

class RuleCreate(RuleBase):
    pass

class RuleUpdate(RuleBase):
    pass

class Rule(RuleBase):
    id: int
    category_id: Optional[int] = None
    
    class Config:
        from_attributes = True
