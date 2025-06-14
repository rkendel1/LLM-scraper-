from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Connect to your scraper's PostgreSQL
SQLALCHEMY_DATABASE_URL = "postgresql://scraper:scraperpass@postgres:5432/scraperdb"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
