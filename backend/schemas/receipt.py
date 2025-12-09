from pydantic import BaseModel, Field
from datetime import date
from typing import Optional

class ReceiptBase(BaseModel):
    store_name: str = Field(..., min_length=2, max_length=50)
    amount: int = Field(..., gt=0)
    category: str = Field(..., pattern="^(Dining out|Groceries|Shopping|Entertainment|Transportation|Subscription|Others)$")
    receipt_date: date
    notes: Optional[str] = None

class ReceiptCreate(ReceiptBase):
    pass

class ReceiptResponse(ReceiptBase):
    id: int
    created_at: date
    
    class Config:
        from_attributes = True
