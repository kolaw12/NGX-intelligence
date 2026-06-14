"""Export latest XGBoost model signals for the frontend.

The frontend can load this JSON instantly, so the AI tab stays fast even when
the live API is cold or blocked by CORS. The values come from the backend's
trained XGBoost artifacts through app.services.model_snapshot.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DEFAULT_OUTPUT = REPO_ROOT / "frontend" / "src" / "data" / "xgboost-signals.snapshot.json"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.model_snapshot import rebuild_model_signal_snapshot  # noqa: E402
from app.services.xgboost_predictor import warmup_xgboost  # noqa: E402


def export_snapshot(output_path: Path) -> int:
    """Build and write the frontend XGBoost signal snapshot."""

    metadata = warmup_xgboost()
    signals = rebuild_model_signal_snapshot()
    payload = {
        "schema": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "model": {
            "kind": "xgboost",
            "source": "backend-trained-artifact",
            "modelPath": _repo_relative(metadata["model"]),
            "featureListPath": _repo_relative(metadata["feature_list"]),
            "featureCount": metadata["feature_count"],
        },
        "signals": {
            signal.public_symbol.upper(): asdict(signal)
            for signal in sorted(signals.values(), key=lambda item: item.public_symbol)
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return len(signals)


def _repo_relative(path: object) -> str:
    """Return a portable repo-relative path for published metadata."""

    try:
        return str(Path(str(path)).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return Path(str(path)).name


def main() -> None:
    parser = argparse.ArgumentParser(description="Export latest XGBoost signals for the frontend.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    count = export_snapshot(args.output)
    print(f"Exported {count} XGBoost signals to {args.output}")


if __name__ == "__main__":
    main()
