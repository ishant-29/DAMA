import joblib, pathlib
from sklearn.ensemble import RandomForestClassifier

MODEL_PATH = pathlib.Path("/data/model.joblib")

FEATURE_ORDER = [
    "avg_gpm",
    "avg_xpm",
    "kill_participation_avg",
    "first_blood_time",
    "tower_status_delta",
    "hero_diversity_delta",
    "meta_wr_delta",
    "meta_pk_delta",
    "duration"
]

def train_baseline(dfX, y):
    clf = RandomForestClassifier(n_estimators=300, max_depth=8, random_state=42, n_jobs=-1)
    clf.fit(dfX[FEATURE_ORDER], y)
    joblib.dump(clf, MODEL_PATH)
    return clf

def load_model():
    if MODEL_PATH.exists():
        return joblib.load(MODEL_PATH)
    return None

def predict_proba(model, X: dict):
    import numpy as np
    row = [[X.get(k, 0) for k in FEATURE_ORDER]]
    p = model.predict_proba(row)[0][1]
    return float(p)



