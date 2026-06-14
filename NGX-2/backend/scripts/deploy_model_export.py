"""Deploy a Colab-exported model zip to the NGX-2 backend.

Usage:
    python scripts/deploy_model_export.py <path-to-zip>

Example:
    python scripts/deploy_model_export.py ~/Downloads/ngx_backend_models_export.zip

What this script does:
1. Unpacks the zip
2. Validates all required files are present
3. Loads and smoke-tests the new XGBoost model
4. Compares new model metrics against the currently deployed model
5. Backs up the current model artifacts (timestamped)
6. Installs new artifacts to the correct backend paths
7. Prints a deployment summary

If any validation step fails the script exits without touching the
currently running model.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import joblib

# ── paths ───────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent

MODELS_DIR   = BACKEND_DIR / "models"
CONFIGS_DIR  = BACKEND_DIR / "configs"
SCALERS_DIR  = BACKEND_DIR / "scalers"
ENCODERS_DIR = BACKEND_DIR / "encoders"
REPORTS_DIR  = BACKEND_DIR / "reports"
BACKUPS_DIR  = BACKEND_DIR / "model_backups"


# ── required files inside the zip ───────────────────────────────────────────
REQUIRED_FILES = [
    "models/xgboost/xgboost_model.pkl",
    "configs/backend_model_config.json",
    "configs/xgb_feature_list.json",
]

# These are copied if present; absence is logged but not fatal
OPTIONAL_FILES = [
    "models/lstm/lstm_model.keras",
    "models/lstm/lstm_model.h5",
    "scalers/lstm_scaler.pkl",
    "encoders/ticker_encoder.pkl",
    "configs/lstm_feature_list.json",
    "configs/config.json",
    "reports/xgb_metrics.json",
    "reports/lstm_metrics.json",
    "reports/xgb_feature_importance.csv",
    "reports/xgb_threshold_report.csv",
    "reports/lstm_threshold_report.csv",
    "reports/model_metrics.json",
    "reports/model_comparison.csv",
    "reports/lstm_sequence_meta.json",
    "reports/recommendation_distribution.csv",
    "models/feature_list.json",
    "models/ticker_encoder.pkl",
    "models/lstm_scaler.pkl",
]

# ── destination map: zip-relative path → backend-absolute path ───────────────
def _build_dest_map(root: Path) -> dict[Path, Path]:
    """Map every file we want from the zip to where it goes in the backend."""
    m: dict[Path, Path] = {}

    def add(src_rel: str, *dest_paths: Path) -> None:
        src = root / src_rel
        if src.exists():
            for dest in dest_paths:
                m[src] = dest   # last dest wins per src; we copy to all manually

    # XGBoost model — install to both the primary (notebook) path and legacy path
    add("models/xgboost/xgboost_model.pkl",
        MODELS_DIR / "xgboost" / "xgboost_model.pkl")

    add("models/lstm/lstm_model.keras",  MODELS_DIR / "lstm" / "lstm_model.keras")
    add("models/lstm/lstm_model.h5",     MODELS_DIR / "lstm" / "lstm_model.h5")
    add("scalers/lstm_scaler.pkl",       SCALERS_DIR / "lstm_scaler.pkl")
    add("encoders/ticker_encoder.pkl",   ENCODERS_DIR / "ticker_encoder.pkl")
    add("configs/xgb_feature_list.json", CONFIGS_DIR / "xgb_feature_list.json")
    add("configs/lstm_feature_list.json",CONFIGS_DIR / "lstm_feature_list.json")
    add("configs/backend_model_config.json", CONFIGS_DIR / "backend_model_config.json")
    add("configs/config.json",           CONFIGS_DIR / "config.json")
    add("reports/xgb_metrics.json",      REPORTS_DIR / "xgb_metrics.json")
    add("reports/lstm_metrics.json",     REPORTS_DIR / "lstm_metrics.json")
    add("reports/xgb_feature_importance.csv",  REPORTS_DIR / "xgb_feature_importance.csv")
    add("reports/xgb_threshold_report.csv",    REPORTS_DIR / "xgb_threshold_report.csv")
    add("reports/lstm_threshold_report.csv",   REPORTS_DIR / "lstm_threshold_report.csv")
    add("reports/model_metrics.json",    REPORTS_DIR / "model_metrics.json")
    add("reports/model_comparison.csv",  REPORTS_DIR / "model_comparison.csv")
    add("reports/lstm_sequence_meta.json",     REPORTS_DIR / "lstm_sequence_meta.json")

    # Also keep legacy flat-model paths so old inference code keeps working
    add("models/feature_list.json",      MODELS_DIR / "feature_list.json")

    return m


def _extra_copies(root: Path) -> list[tuple[Path, Path]]:
    """Return extra (src, dest) pairs that are in addition to the main map."""
    extras = []

    # ticker_encoder: feature_engineer.py reads from models/ticker_encoder.pkl
    for src_rel in ("encoders/ticker_encoder.pkl", "models/ticker_encoder.pkl"):
        src = root / src_rel
        if src.exists():
            extras.append((src, MODELS_DIR / "ticker_encoder.pkl"))
            break

    # lstm_scaler: some paths also read from models/lstm_scaler.pkl
    src = root / "scalers/lstm_scaler.pkl"
    if src.exists():
        extras.append((src, MODELS_DIR / "lstm_scaler.pkl"))

    # xgboost_model legacy flat path (engine.py falls back to models/xgboost_model.pkl)
    src = root / "models/xgboost/xgboost_model.pkl"
    if src.exists():
        extras.append((src, MODELS_DIR / "xgboost_model.pkl"))

    # xgb_feature_list legacy path (loader falls back to models/xgb_feature_list.json)
    src = root / "configs/xgb_feature_list.json"
    if src.exists():
        extras.append((src, MODELS_DIR / "xgb_feature_list.json"))

    return extras


# ── helpers ──────────────────────────────────────────────────────────────────
def _ok(msg: str) -> None:  print(f"  ✓  {msg}")
def _warn(msg: str) -> None: print(f"  ⚠  {msg}")
def _err(msg: str) -> None:  print(f"  ✗  {msg}")
def _head(msg: str) -> None: print(f"\n{'═'*64}\n  {msg}\n{'═'*64}")


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _metric(d: dict, key: str, default: float = 0.0) -> float:
    val = d.get(key, default)
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ── validation ───────────────────────────────────────────────────────────────
def validate_zip_contents(root: Path) -> list[str]:
    """Return list of error messages; empty = all good."""
    errors = []
    for rel in REQUIRED_FILES:
        if not (root / rel).exists():
            errors.append(f"Required file missing from zip: {rel}")
    return errors


def validate_xgboost_model(root: Path) -> tuple[bool, str]:
    """Load and smoke-test the new XGBoost model."""
    model_path = root / "models/xgboost/xgboost_model.pkl"
    try:
        model = joblib.load(model_path)
        if not hasattr(model, "predict_proba"):
            return False, "artifact does not have predict_proba"
        feat_path = root / "configs/xgb_feature_list.json"
        if not feat_path.exists():
            feat_path = root / "models/xgb_feature_list.json"
        if feat_path.exists():
            features = json.loads(feat_path.read_text())
            if len(features) == 0:
                return False, "feature list is empty"
            import numpy as np
            dummy = np.zeros((1, len(features)), dtype="float32")
            prob = model.predict_proba(dummy)[0][1]
            if not (0.0 <= prob <= 1.0):
                return False, f"model returned invalid probability: {prob}"
        return True, f"model loaded OK ({getattr(model, 'n_features_in_', '?')} features)"
    except Exception as exc:
        return False, str(exc)


def compare_metrics(new_root: Path) -> None:
    """Print a side-by-side comparison of new vs current model metrics."""
    new_metrics  = _load_json(new_root / "reports/xgb_metrics.json")
    curr_metrics = _load_json(REPORTS_DIR / "xgb_metrics.json")

    if not new_metrics:
        _warn("No xgb_metrics.json found in export — skipping metric comparison")
        return

    print("\n  Metric comparison (current → new):")
    for key in ["roc_auc", "balanced_accuracy", "mcc", "f1", "threshold_used"]:
        curr = _metric(curr_metrics, key)
        new  = _metric(new_metrics,  key)
        if curr == 0.0 and new == 0.0:
            continue
        arrow = "↑" if new > curr else ("↓" if new < curr else "=")
        print(f"    {key:<26}  {curr:.4f}  →  {new:.4f}  {arrow}")


# ── backup ───────────────────────────────────────────────────────────────────
def backup_current_models() -> Path:
    """Copy current model artifacts to a timestamped backup folder."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS_DIR / ts
    backup.mkdir(parents=True, exist_ok=True)

    for src in [
        MODELS_DIR / "xgboost" / "xgboost_model.pkl",
        MODELS_DIR / "xgboost_model.pkl",
        CONFIGS_DIR / "xgb_feature_list.json",
        CONFIGS_DIR / "backend_model_config.json",
        REPORTS_DIR / "xgb_metrics.json",
    ]:
        if src.exists():
            dest = backup / src.name
            shutil.copy2(src, dest)

    return backup


# ── install ───────────────────────────────────────────────────────────────────
def install_artifacts(root: Path) -> tuple[list[str], list[str]]:
    """Copy validated artifacts to backend paths. Returns (installed, skipped)."""
    installed: list[str] = []
    skipped:   list[str] = []

    dest_map = _build_dest_map(root)
    all_copies: list[tuple[Path, Path]] = list(dest_map.items()) + _extra_copies(root)

    for src, dest in all_copies:
        if not src.exists():
            skipped.append(str(src.relative_to(root)))
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        installed.append(str(dest.relative_to(BACKEND_DIR)))

    return installed, skipped


# ── cache invalidation ────────────────────────────────────────────────────────
def invalidate_backend_caches() -> bool:
    """Try to clear lru_cache on running backend via /cache/invalidate."""
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://localhost:8000/cache/invalidate",
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
            return result.get("cleared", False)
    except Exception:
        return False


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    zip_path = Path(sys.argv[1]).expanduser().resolve()
    if not zip_path.exists():
        _err(f"Zip file not found: {zip_path}")
        sys.exit(1)

    _head("NGX MODEL DEPLOYMENT")
    print(f"  Source: {zip_path}")
    print(f"  Target: {BACKEND_DIR}")

    with tempfile.TemporaryDirectory(prefix="ngx_deploy_") as tmp:
        root = Path(tmp) / "export"

        # ── 1. unpack ─────────────────────────────────────────────────────
        _head("STEP 1 — Unpacking zip")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(root)
            _ok(f"Extracted to temp directory")
        except Exception as exc:
            _err(f"Failed to unpack zip: {exc}")
            sys.exit(1)

        # Check if files are nested inside an extra subfolder
        subdirs = [d for d in root.iterdir() if d.is_dir()]
        if subdirs and not (root / "models").exists():
            root = subdirs[0]
            _ok(f"Found files inside subfolder: {root.name}")

        # ── 2. validate contents ──────────────────────────────────────────
        _head("STEP 2 — Validating zip contents")
        errors = validate_zip_contents(root)
        if errors:
            for e in errors:
                _err(e)
            _err("Deployment aborted — required files are missing.")
            sys.exit(1)
        _ok("All required files present")

        # Check optional files
        for rel in OPTIONAL_FILES:
            if (root / rel).exists():
                _ok(f"Optional file found: {rel}")
            else:
                _warn(f"Optional file missing (non-fatal): {rel}")

        # ── 3. validate model ──────────────────────────────────────────────
        _head("STEP 3 — Validating XGBoost model")
        ok, msg = validate_xgboost_model(root)
        if not ok:
            _err(f"Model validation failed: {msg}")
            _err("Deployment aborted — current model unchanged.")
            sys.exit(1)
        _ok(msg)

        # ── 4. compare metrics ─────────────────────────────────────────────
        _head("STEP 4 — Comparing metrics")
        compare_metrics(root)

        # ── 5. backup current ──────────────────────────────────────────────
        _head("STEP 5 — Backing up current model")
        backup_path = backup_current_models()
        _ok(f"Current model backed up to: {backup_path.relative_to(BACKEND_DIR)}")

        # ── 6. install ─────────────────────────────────────────────────────
        _head("STEP 6 — Installing artifacts")
        installed, skipped = install_artifacts(root)
        for f in installed:
            _ok(f"Installed: {f}")
        for f in skipped:
            _warn(f"Skipped (not in zip): {f}")

        # ── 7. cache invalidation ──────────────────────────────────────────
        _head("STEP 7 — Cache invalidation")
        cleared = invalidate_backend_caches()
        if cleared:
            _ok("Backend lru_cache cleared via /cache/invalidate")
        else:
            _warn("Could not reach /cache/invalidate — restart the backend manually:")
            _warn("  pkill -f 'uvicorn app.main' && uvicorn app.main:app --port 8000 &")

        # ── 8. summary ─────────────────────────────────────────────────────
        _head("DEPLOYMENT COMPLETE")

        new_metrics = _load_json(root / "reports/xgb_metrics.json")
        new_config  = _load_json(root / "configs/backend_model_config.json")

        print(f"\n  Model:          XGBoost")
        print(f"  LSTM enabled:   {new_config.get('use_lstm', False)}")
        if new_metrics:
            print(f"  XGB ROC-AUC:    {_metric(new_metrics, 'roc_auc'):.4f}")
            print(f"  XGB threshold:  {_metric(new_metrics, 'threshold_used'):.4f}")
        print(f"  Backup:         model_backups/{backup_path.name}/")
        print(f"  Files installed: {len(installed)}")
        print(f"\n  ✓  Backend is ready. Restart uvicorn if cache invalidation failed.\n")


if __name__ == "__main__":
    main()
