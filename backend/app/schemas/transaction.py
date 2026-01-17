from pydantic import BaseModel, Field
from typing import Optional, Union
from datetime import date, datetime

# Base schema (shared properties)
class TransactionBase(BaseModel):
    # SQLite returns dates as strings. We allow both str and date object.
    date: Optional[Union[date, str]] = None 
    transaction_type: str
    amount: float
    currency: str = "PLN"
    description: str
    country: Optional[str] = None
    city: Optional[str] = None

# Schema for reading (includes database IDs)
class Transaction(TransactionBase):
    transaction_id: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    merchant: Optional[str] = None
    
    class Config:
        from_attributes = True

# Schema for updating a transaction (e.g. manual categorization)
class TransactionUpdate(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    merchant: Optional[str] = None
