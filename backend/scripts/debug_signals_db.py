
import sys
import os

# Add backend to path to allow imports from app
# Add path for module imports
if os.path.exists(os.path.join(os.getcwd(), 'app')):
    sys.path.append(os.getcwd())
else:
    sys.path.append(os.path.join(os.getcwd(), 'backend'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

def inspect_signals():
    # Inside docker, this should work
    db_url = settings.DATABASE_URL
    print(f"Connecting to {db_url}...")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        print("Inspecting Signal table...")
        # Get count
        count = db.execute(text("SELECT count(*) FROM signals")).scalar()
        print(f"Total signals: {count}")
        
        # Get latest signals
        result = db.execute(text("SELECT timestamp, symbol, signal_type, signal_date FROM signals ORDER BY timestamp DESC LIMIT 10"))
        print("\nTop 10 latest signals:")
        for row in result:
            print(row)
            
        # Check 'today' logic
        from datetime import datetime
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        print(f"\nServer 'today_start': {today_start}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    inspect_signals()
