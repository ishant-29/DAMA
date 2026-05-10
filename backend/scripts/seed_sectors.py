"""
One-time seed script: reads nse500_list.csv and bulk-inserts into the
sector_mappings table.  Re-running is safe (upserts).

Usage:
    docker compose exec backend python scripts/seed_sectors.py
"""
import os
import sys

# Ensure the project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import SectorMapping, Base
from app.db.session import engine


def seed():
    # Create table if it doesn't exist
    Base.metadata.create_all(bind=engine)

    csv_path = os.path.join(
        os.path.dirname(__file__), "..", "app", "data", "nse500_list.csv"
    )
    if not os.path.exists(csv_path):
        print(f"ERROR: CSV not found at {csv_path}")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    df.columns = [c.lower().strip() for c in df.columns]

    db: Session = SessionLocal()
    inserted = 0
    updated = 0

    try:
        for _, row in df.iterrows():
            sym = str(row.get("symbol", "")).strip()
            sec = str(row.get("sector", "")).strip()
            ind = str(row.get("industry", "")).strip() if "industry" in row else None

            if not sym or not sec:
                continue

            existing = db.query(SectorMapping).filter(SectorMapping.symbol == sym).first()
            if existing:
                existing.sector = sec
                if ind:
                    existing.industry = ind
                updated += 1
            else:
                db.add(SectorMapping(symbol=sym, sector=sec, industry=ind))
                inserted += 1

        db.commit()
        print(f"Seed complete: {inserted} inserted, {updated} updated.")
    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
