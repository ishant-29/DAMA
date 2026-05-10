
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
        print(f"Current System Time: {datetime.now()}")
        
        # Check explicit dates
        res = db.execute(text("SELECT to_char(timestamp, 'YYYY-MM-DD'), COUNT(*) FROM signals GROUP BY 1 ORDER BY 1 DESC")).fetchall()
        print("\nSignal Date Distribution:")
        print("Date       | Count")
        print("------------------")
        for row in res:
            print(f"{row[0]} | {row[1]}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
