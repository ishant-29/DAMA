
import sys
import os
from sqlalchemy import text

# Fix path to include backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import SessionLocal

def main():
    try:
        db = SessionLocal()
        print("Connected to DB")
        # Query extracting is_high_risk from reason JSON column
        # Note: 'reason' is the column name. in Postgres ->> returns text.
        res = db.execute(text("SELECT signal_type, reason ->> 'is_high_risk' as high_risk, COUNT(*) FROM signals GROUP BY signal_type, high_risk")).fetchall()
        print("Signal Type | High Risk | Count")
        print("-------------------------------")
        for row in res:
            print(row)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
