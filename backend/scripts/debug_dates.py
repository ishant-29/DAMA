
import sys
import os
from sqlalchemy import text
from datetime import datetime

# Fix path to include backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal

def main():
    try:
        db = SessionLocal()
        print(f"Current System Time: {datetime.utcnow()}")
        
        # Check Distribution of Dates
        res = db.execute(text("SELECT timestamp::date, COUNT(*) FROM signals GROUP BY timestamp::date ORDER BY timestamp::date DESC")).fetchall()
        print("\nSignal Date Distribution:")
        print("Date       | Count")
        print("------------------")
        for row in res:
            print(row)
            
        # Check a sample signal
        sample = db.execute(text("SELECT * FROM signals LIMIT 1")).fetchone()
        print(f"\nSample Signal: {sample}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
