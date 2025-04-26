
"""
build_delhi_ac_graph.py

Creates <state>_ac_graph.json for Delhi, Goa, and Assam, with:
  • nodes:   id==ac_no, name, district_id, district
  • adjacency: shared‑perimeter neighbour lists

If any AC ends up with no neighbours, we warn but still emit JSON.
"""

import json
import urllib.request
from pathlib import Path

import geopandas as gpd
import pandas as pd
from tqdm import tqdm

# 1) Which states (ST_CODE) to process
STATES = {
    "delhi": 7,   # 70 ACs
    "goa":   30,  # 40 ACs
    "assam": 18   # 126 ACs
}

# 2) Download shapefile pieces if needed
RAW_BASE = ("https://raw.githubusercontent.com/datameet/maps/master/"
            "assembly-constituencies/India_AC")
for ext in ("shp", "shx", "dbf", "prj"):
    fp = Path(f"India_AC.{ext}")
    if not fp.exists():
        print(f"[+] Downloading India_AC.{ext} …")
        urllib.request.urlretrieve(f"{RAW_BASE}.{ext}", fp)

# 3) Load the master shapefile
print("[+] Reading India_AC.shp …")
gdf = gpd.read_file("India_AC.shp")  # CRS: EPSG:4326

# helper to find district columns
def find_col(cols, *needles):
    for c in cols:
        up = c.upper()
        if all(n in up for n in needles):
            return c
    return None

# 4) Process each state
for state, code in STATES.items():
    print(f"\n=== {state.upper()} (ST_CODE={code}) ===")
    sub = gdf[gdf["ST_CODE"].astype(str).str.lstrip("0") == str(code)].copy()
    if sub.empty:
        print(f"⚠️  No polygons found for ST_CODE {code}")
        continue

    sub.sort_values("AC_NO", inplace=True)
    sub.reset_index(drop=True, inplace=True)

    # detect district columns
    dcode_col = find_col(sub.columns, "DIST", "COD") or find_col(sub.columns, "DIST", "NO")
    dname_col = find_col(sub.columns, "DIST", "NAME")
    sub["district_id"] = sub[dcode_col] if dcode_col else pd.NA
    sub["district"]    = sub[dname_col] if dname_col else pd.NA

    # build adjacency
    sp = sub.to_crs(32644)
    sp["geometry"] = sp.geometry.buffer(0)
    sp["perim"]    = sp.geometry.length

    n = len(sp)
    adjacency = [[] for _ in range(n)]
    sindex = sp.sindex
    print("    Computing adjacency …")
    for idx in tqdm(range(n), desc="adjacency"):
        geom_i = sp.at[idx, "geometry"]
        per_i  = sp.at[idx, "perim"]
        ac_i   = int(sp.at[idx, "AC_NO"])
        for j in sindex.query(geom_i, predicate="touches"):
            if idx == j:
                continue
            shared = geom_i.intersection(sp.at[j, "geometry"]).length
            if shared > 0:
                ac_j = int(sp.at[j, "AC_NO"])
                adjacency[ac_i - 1].append({
                    "id": ac_j,
                    "shared_perim": float(shared / per_i)
                })

    # warn about empty neighbour lists
    empties = [i+1 for i, nbrs in enumerate(adjacency) if not nbrs]
    if empties:
        print(f"⚠️  These AC_NO have no neighbours: {empties}")

    # build nodes
    nodes = []
    for _, r in sub.iterrows():
        nodes.append({
            "id": int(r.AC_NO),
            "ac_no": int(r.AC_NO),
            "name": r.AC_NAME,
            "district_id": None if pd.isna(r.district_id) else int(r.district_id),
            "district":    None if pd.isna(r.district)    else str(r.district)
        })

    # write JSON
    out = {"nodes": nodes, "adjacency": adjacency}
    out_file = Path(f"{state}_ac_graph.json")
    out_file.write_text(json.dumps(out, indent=2), "utf-8")
    print(f"    → Wrote {out_file}  ({len(nodes)} ACs)")


    print("\nAll available ST_CODE values:")
    mapping = gdf[["ST_CODE", "ST_NAME"]].drop_duplicates().sort_values("ST_CODE")
    for sc, sn in zip(mapping.ST_CODE, mapping.ST_NAME):
        print(f"  {sc}  →  {sn}")
