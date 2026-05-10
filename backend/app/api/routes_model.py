from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import ModelRun
from app.auth import get_current_user, User

router = APIRouter()

@router.post("/train")
def train_model(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # In real app, trigger evaluator
    return {"status": "training_started", "config": payload}

@router.get("/status")
def model_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    active = db.query(ModelRun).filter(ModelRun.is_active == True).first()
    return {
        "status": "idle",
        "active_model": active.model_name if active else "xgboost_v1",
        "version": active.version if active else "default",
    }

@router.get("/versions")
def list_model_versions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):  # FIXED: S3-04
    """List all registered ML model runs with their metrics."""
    models = db.query(ModelRun).order_by(ModelRun.timestamp.desc()).all()
    return [
        {
            "id": m.id,
            "model_name": m.model_name,
            "version": m.version,
            "algorithm": m.algorithm,
            "accuracy": m.accuracy,
            "f1_score": m.f1_score,
            "is_active": m.is_active,
            "file_path": m.file_path,
            "training_date": str(m.training_date) if m.training_date else None,
            "metrics": m.metrics,
        }
        for m in models
    ]

@router.post("/{version}/activate")
def activate_model(
    version: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set a specific model version as the active one."""
    target = db.query(ModelRun).filter(ModelRun.version == version).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"Model version '{version}' not found")

    # Deactivate all models
    db.query(ModelRun).update({ModelRun.is_active: False})
    # Activate target
    target.is_active = True
    db.commit()

    return {"status": "activated", "version": version, "model_name": target.model_name}
