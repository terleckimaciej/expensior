
from pydantic import BaseModel
from typing import List, Optional

class CategoryBase(BaseModel):
    name: str

class SubCategory(CategoryBase):
    id: int
    parent_id: int

    class Config:
        from_attributes = True

class Category(CategoryBase):
    id: int
    subcategories: List[SubCategory] = []

    class Config:
        from_attributes = True
