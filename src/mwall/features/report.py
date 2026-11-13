"""Feature dictionary (docs/features.md) and Gate 2 feature QA report (docs/qa/gate2_features.md)
with one distribution figure per family, by property type, under docs/qa/features/.

All statistics are computed in DuckDB straight from panel/features.parquet, so the report never
holds the full table in memory.
"""
from __future__ import annotations

import datetime as dt

import duckdb
import numpy as np
import pandas as pd

from mwall.common import paths
from mwall.features.build import LATE_SNAPSHOT_DAYS
from mwall.features.catalog import CATALOG

FEATURES = paths.PANEL_DIR / "features.parquet"
INK, INK2, MUTED, SURFACE, GRID, SERIES = "#0b0b0b", "#52514e", "#8a8984", "#fcfcfb", "#e7e6e2", "#2a78d6"
TYPES = ["multifamily", "office", "retail", "industrial", "lodging", "self_storage", "mixed_use", "other"]
GROUP_SQL = ("case when property_group in ('multifamily','office','retail','industrial','lodging','self_storage',"
             "'mixed_use') then property_group else 'other' end")


def _src() -> str:
    return f"read_parquet('{FEATURES.as_posix()}')"


def present() -> set[str]:
    return set(duckdb.connect().execute(f"describe select * from {_src()}").df()["column_name"])


def stats(rep_only: bool = True) -> pd.DataFrame:
    """Per feature and property group (plus 'all'): rows, non-null rows, quantiles or share true."""
    con = duckdb.connect()
    cols = present()
    where = "where is_representative" if rep_only else ""
    out = []
    for ft in CATALOG:
        if ft.name not in cols:
            continue
        if ft.kind == "num":
            agg = f"quantile_cont({ft.name}::double, [0.1, 0.25, 0.5, 0.75, 0.9]) q, null::double share_true"
        elif ft.kind == "bool":
            agg = f"null q, avg({ft.name}::int) share_true"
        else:
            agg = "null q, null::double share_true"
        for g in (GROUP_SQL, "'all'"):
            df = con.execute(f"select {g} grp, count(*) n, count({ft.name}) nn, {agg} from {_src()} {where} "
                             "group by 1").df()
            df["feature"] = ft.name
            out.append(df)
    return pd.concat(out, ignore_index=True)


def write_dictionary(st: pd.DataFrame | None = None) -> None:
    cov = {}
    if st is not None:
        a = st[st["grp"].eq("all")]
        cov = dict(zip(a["feature"], a["nn"] / a["n"]))
    L = ["# Feature dictionary", "",
         "Generated from `src/mwall/features/catalog.py`; do not edit by hand. SOP section 9. The snapshot date "
         "T of a row is its filing date. Every feature is computed from information public on or before T; "
         "`lag` says how. Nothing is imputed: a missing input leaves the feature null, and `f_noi_missing` "
         "marks rows without current NOI. Ratios use the whole-loan balance (`wl_balance_est`), because NOI, "
         "value and reported DSCR describe the whole collateral.", ""]
    for fam in dict.fromkeys(ft.family for ft in CATALOG):
        L += [f"## {fam}", "", "| feature | definition | unit | inputs | lag | nulls | coverage |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
        for ft in (x for x in CATALOG if x.family == fam):
            c = cov.get(ft.name)
            c = "pending" if (st is not None and not c) else ("" if c is None else f"{100 * c:.0f}%")
            inputs = ", ".join(f"`{i}`" for i in ft.inputs)
            L.append(f"| `{ft.name}` | {ft.definition} | {ft.unit} | {inputs} | {ft.lag} | {ft.nulls} | {c} |")
        L.append("")
    L += ["Coverage: share of representative loan-months (one per whole loan and month) where the feature is not "
          "null. Columns `asof_*` in panel/features.parquet hold the publication date of each market value used, "
          "for the leakage audit.", ""]
    (paths.DOCS_DIR / "features.md").write_text("\n".join(L), encoding="utf-8")


def plot_family(st: pd.DataFrame, family: str, path) -> bool:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    feats = [ft for ft in CATALOG if ft.family == family and ft.kind != "cat"
             and st.loc[st["feature"].eq(ft.name), "nn"].sum() > 0]
    if not feats:
        return False
    ncol = 3
    nrow = int(np.ceil(len(feats) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.4 * ncol, 2.9 * nrow), squeeze=False, facecolor=SURFACE)
    ys = np.arange(len(TYPES))[::-1]
    for ax, ft in zip(axes.flat, feats):
        ax.set_facecolor(SURFACE)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(colors=INK2, labelsize=7.5, length=0)
        ax.grid(axis="x", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        sub = st[st["feature"].eq(ft.name)].set_index("grp")
        lo, hi = ft.clip or (0, 1)
        for y, t in zip(ys, TYPES):
            if t not in sub.index or sub.loc[t, "nn"] == 0:
                continue
            r = sub.loc[t]
            null_pct = 100 * (1 - r["nn"] / r["n"])
            if ft.kind == "bool":
                ax.barh(y, r["share_true"], height=0.5, color=SERIES, linewidth=0)
                ax.text(r["share_true"], y, f" {100 * r['share_true']:.0f}%", va="center", fontsize=6.5, color=INK2)
            else:
                q = np.clip(np.asarray(r["q"], dtype=float), lo, hi)
                ax.plot([q[0], q[4]], [y, y], color=SERIES, linewidth=1.2, alpha=0.55, solid_capstyle="round")
                ax.plot([q[1], q[3]], [y, y], color=SERIES, linewidth=5, solid_capstyle="round")
                ax.plot([q[2]], [y], "o", color=SURFACE, markersize=5.5, markeredgecolor=INK, markeredgewidth=1.1)
            ax.text(1.0, y, f" {null_pct:.0f}% null", transform=ax.get_yaxis_transform(), ha="left", va="center",
                    fontsize=6, color=MUTED)
        ax.set_yticks(ys, TYPES)
        ax.set_xlim(*((0, 1.15) if ft.kind == "bool" else (lo, hi)))
        ax.set_title(f"{ft.name}  ({ft.unit})", fontsize=8.5, color=INK, loc="left", pad=6)
    for ax in list(axes.flat)[len(feats):]:
        ax.set_visible(False)
    fig.suptitle(f"{family}, by property type. Dot: median. Bar: 25th to 75th percentile. Line: 10th to 90th. "
                 "Flags: share true.", fontsize=9.5, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 0.96, 0.97))
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)
    return True


def report(log=print) -> None:
    from mwall.clean.qa_report import md_table

    st = stats()
    write_dictionary(st)
    fig_dir = paths.DOCS_DIR / "qa" / "features"
    fig_dir.mkdir(parents=True, exist_ok=True)
    head = duckdb.connect().execute(f"""select count(*) n, count(*) filter (where is_representative) n_rep,
        count(*) filter (where flag_late_snapshot) n_late, avg((cbsa_code is not null)::int) metro
        from {_src()}""").df().iloc[0]
    cols = present()
    pending = [ft.name for ft in CATALOG if ft.name not in cols or st.loc[st["feature"].eq(ft.name), "nn"].sum() == 0]
    L = ["# Gate 2 features: coverage and distributions", "",
         f"Generated {dt.date.today().isoformat()} by `python -m mwall features`. Dictionary: `docs/features.md`. "
         f"Rows: {int(head['n']):,} loan-months; tables and plots use the {int(head['n_rep']):,} representative "
         "rows (one per whole loan and month).", "",
         f"- Late snapshots (filed more than {LATE_SNAPSHOT_DAYS} days after the period, or after the loan's next "
         f"period ended): {int(head['n_late']):,} rows, kept out of model training.",
         f"- Rows with a metro: {100 * head['metro']:.1f}%."]
    if pending:
        L.append(f"- Pending (inputs not yet in place): {', '.join(f'`{p}`' for p in pending)}.")
    cov = st.assign(c=st["nn"] / st["n"]).pivot_table(index="feature", columns="grp", values="c")
    cov = cov.reindex([ft.name for ft in CATALOG if ft.name in cov.index])
    cov = cov[[c for c in ["all", *TYPES] if c in cov.columns]].reset_index()
    L += ["", "## Coverage by property type (share not null)", "", md_table(cov, floatfmt=".2f"), ""]
    for fam in dict.fromkeys(ft.family for ft in CATALOG):
        name = fam.lower().replace(" and ", "_").replace(" ", "_").replace("-", "_")
        if plot_family(st, fam, fig_dir / f"{name}.png"):
            L += [f"## {fam}", "", f"![{fam}](features/{name}.png)", ""]
    (paths.DOCS_DIR / "qa" / "gate2_features.md").write_text("\n".join(L), encoding="utf-8")
    log(f"wrote docs/features.md and docs/qa/gate2_features.md ({len(pending)} features pending)")
