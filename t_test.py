import os
import json
from functools import partial
from collections import defaultdict

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from shapely.geometry import shape
from scipy import stats

from gerrychain import (
    Election,
    Graph,
    MarkovChain,
    Partition,
    accept,
    constraints,
    updaters,
)
from gerrychain.proposals import recom
from gerrychain.updaters import cut_edges

alpha        = 0.05        # significance level for t-test

sns.set_style("whitegrid")

# ——————————————
# Modified for Delhi
graph_path      = "/Users/ayush/Desktop/Project/final.json"  # ← your GeoJSON
unique_label    = "id"                                # node id in your GeoJSON
pop_col         = "TOT_POP"
district_col    = "INIT_DIST"
election_names  = ["LS25"]
election_cols   = [["LS25BJP", "LS25AAP"]]

gdf = gpd.read_file("/Users/ayush/Desktop/Project/Delhi_Shapefile/Delhi_AC.shp")

# 2) Build the GerryChain graph, telling it to use your GEOID10 as node‐ids:
graph = Graph.from_json(graph_path)

# 3) Updaters: pop + cut‐edges + the single election
updater_dict = {
    "population": updaters.Tally(pop_col, alias="population"),
    "cut_edges": cut_edges,
}
elections = [
    Election(
        election_names[0],
        {"BJP": election_cols[0][0],
         "AAP": election_cols[0][1]}
    )
]
updater_dict.update({e.name: e for e in elections})

initial_partition = Partition(graph, district_col, updater_dict)

ideal_pop = sum(initial_partition["population"].values()) / len(initial_partition)

proposal = partial(
    recom,
    pop_col=pop_col,
    pop_target=ideal_pop,
    epsilon=0.4,
    node_repeats=2
)

compactness = constraints.UpperBound(
    lambda p: len(p["cut_edges"]),
    2 * len(initial_partition["cut_edges"])
)

total_steps   = 1000
chain = MarkovChain(
    proposal=proposal,
    constraints=[compactness, accept.always_accept],
    accept=accept.always_accept,
    initial_state=initial_partition,
    total_steps=total_steps,
)

# ──────────────────────────────────────────────────────────
#  2. Metric helpers
# ──────────────────────────────────────────────────────────
def efficiency_gap_partition(part):
    """Efficiency gap for one partition (Party A positive)."""
    eg = part["LS25"].efficiency_gap()
    return eg

def mean_median_partition(part):
    """Mean–Median for Party A."""
    mm = part["LS25"].mean_median()
    return mm

# enacted metrics
initial_EG = efficiency_gap_partition(initial_partition)
initial_MM = mean_median_partition(initial_partition)

# ──────────────────────────────────────────────────────────
#  3. Walk the chain & collect metrics
# ──────────────────────────────────────────────────────────
egs, mms = [], []
for part in chain:
    egs.append(efficiency_gap_partition(part))
    mms.append(mean_median_partition(part))

egs = np.array(egs)
mms = np.array(mms)

# ──────────────────────────────────────────────────────────
#  4. One-sample t-tests
# ──────────────────────────────────────────────────────────
t_eg, p_eg = stats.ttest_1samp(egs, initial_EG)
t_mm, p_mm = stats.ttest_1samp(mms, initial_MM)

print("\n===== One-sample t-tests vs ensemble =====")
print(f"Efficiency Gap : enacted = {initial_EG:+.4f} | "
      f"ensemble mean = {egs.mean():+.4f} ± {egs.std(ddof=1):.4f}")
print(f"  t = {t_eg:.3f},  p = {p_eg:.4g}  ⇒  "
      f"{'SIGNIFICANT' if p_eg < alpha else 'ns'} (α={alpha})")

print(f"Mean–Median    : enacted = {initial_MM:+.4f} | "
      f"ensemble mean = {mms.mean():+.4f} ± {mms.std(ddof=1):.4f}")
print(f"  t = {t_mm:.3f},  p = {p_mm:.4g}  ⇒  "
      f"{'SIGNIFICANT' if p_mm < alpha else 'ns'} (α={alpha})")
print("==========================================\n")

# ──────────────────────────────────────────────────────────
#  5. Plot histograms with t-test annotation
# ──────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Efficiency gap
sns.histplot(egs, bins=30, kde=True, ax=axes[0], color="C0")
axes[0].axvline(initial_EG, color="k", linestyle="--")
axes[0].set_title("Ensemble Efficiency Gap")
axes[0].set_xlabel("Efficiency Gap")
axes[0].annotate(
    f"t = {t_eg:.2f}\np = {p_eg:.3g}",
    xy=(0.05, 0.93), xycoords="axes fraction",
    ha="left", va="top", fontsize=9,
    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="0.8")
)

# Mean–Median
sns.histplot(mms, bins=30, kde=True, ax=axes[1], color="C1")
axes[1].axvline(initial_MM, color="k", linestyle="--")
axes[1].set_title("Ensemble Mean–Median Gap")
axes[1].set_xlabel("Mean–Median Gap")
axes[1].annotate(
    f"t = {t_mm:.2f}\np = {p_mm:.3g}",
    xy=(0.05, 0.93), xycoords="axes fraction",
    ha="left", va="top", fontsize=9,
    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="0.8")
)

plt.tight_layout()
plt.savefig("ensemble_vs_initial_comparison.png", dpi=300)
plt.show()
