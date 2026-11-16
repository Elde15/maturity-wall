"""Gate 3 driver: ``python -m mwall model --stage ...``. Every stage reuses what is already on disk.

rolling, ablations, family: the first specification (unconstrained logistic and boosted trees).
signed, signed_ablations, signed_family: the sign-constrained logistic regression (D054), the final model.
logic: the credit-logic shock check. maturity: the maturity-window evaluation at 60, 90 and 120 days' grace.
final: the deployed models and data/outputs/scores.parquet. report: docs/qa/gate3_models.md.
"""
from __future__ import annotations

from mwall.model import frame, logic, maturity, report, rolling, scenario, score

STAGES = ("rolling", "ablations", "family", "signed", "signed_ablations", "signed_family", "logic", "maturity",
          "final", "report")


def run(stages: tuple[str, ...] = STAGES, log=print) -> None:
    stages = tuple(x.strip() for s in stages for x in s.split(",") if x.strip())
    unknown = set(stages) - set(STAGES)
    if unknown:
        raise SystemExit(f"unknown stage(s): {sorted(unknown)}; choose from {STAGES}")
    log(f"model stages: {', '.join(stages)}")
    d = None

    def data():
        nonlocal d
        if d is None:
            d = frame.load()
        return d

    signed = {"models": ("logit",), "shap_rows": 0, "signs": frame.CREDIT_SIGNS}
    if "rolling" in stages:
        rolling.run(data(), tag="main", scenarios=scenario.rate_scenarios(), log=log)
    if "ablations" in stages:
        for name, drop in frame.ABLATIONS.items():
            rolling.run(data(), tag=f"ablation_{name}", drop=drop, models=("gbm",), with_baselines=False,
                        shap_rows=0, log=log)
    if "family" in stages:
        rolling.run(data(), tag="family_holdout", group="family_fold", models=("logit", "gbm"),
                    with_baselines=True, shap_rows=0, log=log)
    if "signed" in stages:
        rolling.run(data(), tag="signed", with_baselines=False, scenarios=scenario.rate_scenarios(), log=log,
                    **signed)
    if "signed_ablations" in stages:
        for name, drop in frame.ABLATIONS.items():
            rolling.run(data(), tag=f"signed_ablation_{name}", drop=drop, with_baselines=False, log=log, **signed)
    if "signed_family" in stages:
        rolling.run(data(), tag="signed_family_holdout", group="family_fold", with_baselines=True, log=log,
                    **signed)
    if "logic" in stages:
        logic.run(data(), log=log)
    if "maturity" in stages:
        for grace in (90, 60, 120):
            maturity.evaluate(grace=grace, log=log)
        maturity.evaluate(grace=90, signs=None, tag="_unconstrained", log=log)
    if "final" in stages:
        d = None
        score.run(log=log)
    if "report" in stages:
        report.write(log=log)
