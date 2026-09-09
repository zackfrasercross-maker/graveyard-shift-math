"""Reproduce tests, exact feasibility and the real SDK warning comparison."""
import contextlib
import hashlib
import io
import json
import unittest
import warnings
from pathlib import Path
from types import SimpleNamespace

from games.graveyard_shift.audit import json_default, maxzero_feasibility


def main():
    root = Path(__file__).resolve().parents[2]
    report_dir = root / "docs" / "graveyard"
    suite = unittest.defaultTestLoader.loadTestsFromName("games.graveyard_shift.test_audit")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        return 1
    from utils.analysis.distribution_functions import get_etl_cvar_p5k_10k_vales
    from utils.rgs_verification import verify_mode_volatility

    report = maxzero_feasibility()
    hit = report["metrics"]["nonzero_probability"]
    values = get_etl_cvar_p5k_10k_vales({0: float(1 - hit), 25000: float(hit)}, 1000)
    stats = SimpleNamespace(**dict(zip(["prob5k", "prob10k", "etl10k", "etl40b", "cvar"], values)), rtp=.962)
    captured = io.StringIO()
    with warnings.catch_warnings(record=True), contextlib.redirect_stdout(captured):
        violations = verify_mode_volatility("maxzero_analytical_only", stats)
    report["pinned_sdk_comparison"] = {
        "fork_base_commit": "e37dd1f5993db231f72070a0f0bf991ff4f5767a",
        "upstream_checked_commit": "307e6812b38489e212f835001f21e9f7d4c18a4d",
        "metrics": vars(stats), "violations": violations,
        "source_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in
                          ["utils/rgs_verification.py", "utils/analysis/distribution_functions.py"]},
        "note": "SDK files were not changed. Live documentation and SDK use different risk calculations; these are separate reports.",
    }
    report["regression_tests"] = {"run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors)}
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "maxzero-feasibility.json").write_text(json.dumps(report, indent=2, default=json_default) + "\n")
    print("Saved analytical feasibility and SDK comparison; full game math remains incomplete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
