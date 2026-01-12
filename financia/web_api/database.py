from sqlalchemy import create_engine, Column, String, Float, JSON
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = "sqlite:///./portfolio.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class PortfolioItemDB(Base):
    __tablename__ = "portfolio_items"
    
    ticker = Column(String, primary_key=True, index=True)
    last_decision = Column(String, default="PENDING")
    last_price = Column(Float, default=0.0)
    last_volume = Column(Float, default=0.0)
    last_volume_ratio = Column(Float, default=0.0)
    last_updated = Column(String, default="-")
    final_score = Column(Float, default=0.0)
    
    # Store complex nested data as JSON strings or JSON type if supported
    # SQLite supports JSON type in modern versions, SQLAlchemy handles it
    category_scores = Column(JSON, default={})
    indicator_details = Column(JSON, default=[])

class RecommendationDB(Base):
    __tablename__ = "recommendations"
    
    ticker = Column(String, primary_key=True, index=True)
    score = Column(Float, default=0.0)
    decision = Column(String, default="HOLD")
    price = Column(Float, default=0.0)
    divergence_count = Column(Float, default=0.0) # Using float for simplicity, but int logic applies
    last_updated = Column(String, default="-")

def init_db():
    Base.metadata.create_all(bind=engine)
    
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
