
import sys
import os
from sqlalchemy import text
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db.session import SessionLocal

def main():
    try:
        db = SessionLocal()
        # Check distribution of confidence scores
        res = db.execute(text("SELECT floor(confidence*10)/10 as bin, COUNT(*) FROM signals GROUP BY 1 ORDER BY 1 DESC")).fetchall()
        print("\nConfidence Score Distribution:")
        print("Score Bin  | Count")
        print("------------------")
        for row in res:
            print(f"{row[0]} - {row[0]+0.1:.1f} | {row[1]}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
