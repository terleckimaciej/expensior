
from pydantic import BaseModel, Field
from typing import List, Optional

class CategoryBase(BaseModel):
    category: str

class SubCategory(CategoryBase):
    category_id: int
    parent_id: int

    class Config:
        from_attributes = True

class Category(CategoryBase):
    category_id: int
    subcategories: List[SubCategory] = []

    class Config:
        from_attributes = True
