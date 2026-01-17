from pydantic import BaseModel
from typing import Optional
from datetime import date

# Base schema (shared properties)
class TransactionBase(BaseModel):
    date: Optional[date] = None
    transaction_type: str
    amount: float
    currency: str = "PLN"
    description: str
    country: Optional[str] = None
    city: Optional[str] = None

# Schema for reading (includes database IDs)
class Transaction(TransactionBase):
    transaction_id: str
    # fields from classification could be added here later
    category: Optional[str] = None
    subcategory: Optional[str] = None
    
    class Config:
        from_attributes = True

# Schema for updating a transaction (e.g. manual categorization)
class TransactionUpdate(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    merchant: Optional[str] = None
