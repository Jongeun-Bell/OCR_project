from sqlalchemy import Column, Integer, String, Date, Text, DateTime, CheckConstraint
from sqlalchemy.sql import func
from .database import Base

class Receipt(Base):
    __tablename__ = "receipts"
    
    id = Column(Integer, primary_key=True, index=True)
    image_path = Column(Text, nullable=True)  # ← 추가됨!
    store_name = Column(String(50), nullable=False)
    amount = Column(Integer, CheckConstraint('amount > 0'), nullable=False)
    category = Column(
        String(20), 
        CheckConstraint("category IN ('Dining out','Groceries','Shopping','Entertainment','Transportation','Subscription','Others')"),
        nullable=False
    )
    receipt_date = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
