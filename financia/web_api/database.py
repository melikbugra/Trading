from sqlalchemy import create_engine, Column, String, Float, JSON
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = "sqlite:///./portfolio.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ============= BIST100 Tables =============
class BIST100PortfolioItem(Base):
    __tablename__ = "bist100_portfolio"
    
    ticker = Column(String, primary_key=True, index=True)
    last_decision = Column(String, default="PENDING")
    last_price = Column(Float, default=0.0)
    last_volume = Column(Float, default=0.0)
    last_volume_ratio = Column(Float, default=0.0)
    last_updated = Column(String, default="-")
    final_score = Column(Float, default=0.0)
    category_scores = Column(JSON, default={})
    indicator_details = Column(JSON, default=[])

class BIST100Recommendation(Base):
    __tablename__ = "bist100_recommendations"
    
    ticker = Column(String, primary_key=True, index=True)
    score = Column(Float, default=0.0)
    decision = Column(String, default="HOLD")
    price = Column(Float, default=0.0)
    divergence_count = Column(Float, default=0.0)
    last_updated = Column(String, default="-")

# ============= Binance Tables =============
class BinancePortfolioItem(Base):
    __tablename__ = "binance_portfolio"
    
    ticker = Column(String, primary_key=True, index=True)  # e.g., BTCUSDT
    last_decision = Column(String, default="PENDING")
    last_price = Column(Float, default=0.0)
    last_volume = Column(Float, default=0.0)
    last_volume_ratio = Column(Float, default=0.0)
    last_updated = Column(String, default="-")
    final_score = Column(Float, default=0.0)
    category_scores = Column(JSON, default={})
    indicator_details = Column(JSON, default=[])

class BinanceRecommendation(Base):
    __tablename__ = "binance_recommendations"
    
    ticker = Column(String, primary_key=True, index=True)
    score = Column(Float, default=0.0)
    decision = Column(String, default="HOLD")
    price = Column(Float, default=0.0)
    divergence_count = Column(Float, default=0.0)
    last_updated = Column(String, default="-")

# Legacy aliases for backward compatibility during migration
PortfolioItemDB = BIST100PortfolioItem
RecommendationDB = BIST100Recommendation

def init_db():
    Base.metadata.create_all(bind=engine)
    
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

