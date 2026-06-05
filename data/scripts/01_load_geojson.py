"""
Phase 0 — Script 1: Load India District GeoJSON into Supabase
Downloads from datameet/maps GitHub, builds adjacency matrix, seeds districts table.

Usage: python data/scripts/01_load_geojson.py
Pre-req: Supabase schema applied (run schema.sql first)
"""

import sys
import os
import json
import math
import time
import requests
from pathlib import Path
from io import StringIO

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import mapping
from tqdm import tqdm
from supabase import create_client

# ─── Config ───────────────────────────────────────────────────────────────────
# The user downloaded the datameet/maps GitHub zip.
# The shapefile is in: data/raw/india_geojson/maps-master/Districts/Census_2011/
GEOJSON_PATH = ROOT / "data/raw/india_geojson/maps-master/Districts/Census_2011/2011_Dist.shp"
GEOJSON_URL  = "https://raw.githubusercontent.com/datameet/maps/master/Districts/India_Districts.geojson"
BATCH_SIZE   = 50   # districts per Supabase upsert batch

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# ─── Download if not present ───────────────────────────────────────────────────
def ensure_geojson_available():
    """Check that the shapefile is present. Download GeoJSON as fallback."""
    if GEOJSON_PATH.exists():
        print(f"Using shapefile: {GEOJSON_PATH}")
        return GEOJSON_PATH

    # Try alternate locations in the extracted zip
    alternates = [
        ROOT / "data/raw/india_geojson/maps-master/Districts/Census_2011/2011_Dist.shp",
        ROOT / "data/raw/india_geojson/maps-master/Districts/Census_2001/2001_Dist.shp",
        ROOT / "data/raw/india_geojson/Districts.geojson",
    ] + list((ROOT / "data/raw/india_geojson").rglob("*.shp")) \
      + list((ROOT / "data/raw/india_geojson").rglob("*district*.geojson")) \
      + list((ROOT / "data/raw/india_geojson").rglob("*dist*.geojson"))

    for alt in alternates:
        if alt.exists():
            print(f"Found at alternate path: {alt}")
            return alt

    # Nothing found locally — download
    print(f"Shapefile not found. Downloading GeoJSON fallback...")
    out = ROOT / "data/raw/india_geojson/Districts.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(GEOJSON_URL, timeout=120)
    if r.status_code == 200:
        out.write_bytes(r.content)
        print(f"Downloaded ({len(r.content)//1024} KB) to {out}")
        return out
    else:
        print(f"Download failed (HTTP {r.status_code}). Place shapefile at:")
        print(f"  {GEOJSON_PATH}")
        sys.exit(1)

# ─── Load + clean GeoJSON ─────────────────────────────────────────────────────
def load_and_clean_geodataframe(path):
    print(f"\n📂 Loading data from {path}...")
    gdf = gpd.read_file(str(path))
    print(f"   Loaded {len(gdf)} features. CRS: {gdf.crs}")
    print(f"   Columns: {list(gdf.columns)}")

    # Normalize property names
    col_map = {}
    cols_lower = {c.lower(): c for c in gdf.columns}

    district_col = cols_lower.get("district") or cols_lower.get("dtname") or cols_lower.get("dt_nm")
    state_col    = cols_lower.get("st_nm") or cols_lower.get("stname") or cols_lower.get("state")
    census_col   = cols_lower.get("dt_cen_cd") or cols_lower.get("censuscode") or cols_lower.get("census_code") or cols_lower.get("st_cen_cd")

    if not district_col:
        print("❌ Cannot find district name column. Available:", list(gdf.columns))
        sys.exit(1)

    gdf = gdf.rename(columns={
        district_col: "district_name",
        state_col: "state_name",
    })
    if census_col:
        gdf = gdf.rename(columns={census_col: "census_code"})
    else:
        print("⚠️  No census code column found — generating synthetic IDs")
        gdf["census_code"] = (
            gdf["state_name"].str[:3].str.upper() + "_" +
            gdf["district_name"].str[:6].str.upper().str.replace(" ", "_")
        )

    # Clean names
    gdf["district_name"] = gdf["district_name"].astype(str).str.strip().str.title()
    gdf["state_name"]    = gdf["state_name"].astype(str).str.strip().str.title()
    gdf["census_code"]   = gdf["census_code"].astype(str).str.strip()

    # Drop nulls
    before = len(gdf)
    gdf = gdf.dropna(subset=["district_name", "state_name", "geometry"])
    print(f"   After dropping nulls: {len(gdf)} rows (removed {before - len(gdf)})")

    return gdf

# ─── Compute spatial attributes ───────────────────────────────────────────────
def compute_spatial_attributes(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    print("\n📐 Computing centroids and areas...")

    # Work in WGS84 for centroids, projected CRS for area
    gdf_wgs84 = gdf.to_crs(epsg=4326)

    # Centroid in WGS84 (approximate, fine for our use case)
    centroids = gdf_wgs84.geometry.centroid
    gdf["centroid_lat"] = centroids.y.round(6)
    gdf["centroid_lon"] = centroids.x.round(6)

    # Area in km² (project to Indian grid: EPSG 32643 = UTM Zone 43N)
    try:
        gdf_proj = gdf.to_crs(epsg=32643)
        gdf["area_km2"] = (gdf_proj.geometry.area / 1e6).round(2)
    except Exception as e:
        print(f"   ⚠️  Area projection failed ({e}), estimating from lat/lon")
        gdf["area_km2"] = None

    print(f"   Centroid range: lat {gdf['centroid_lat'].min():.2f}–{gdf['centroid_lat'].max():.2f}, "
          f"lon {gdf['centroid_lon'].min():.2f}–{gdf['centroid_lon'].max():.2f}")
    return gdf

# ─── Compute adjacency matrix ─────────────────────────────────────────────────
def compute_adjacency(gdf: gpd.GeoDataFrame) -> dict[str, list[str]]:
    """Returns {census_code: [neighbor_census_codes]} for all districts."""
    print(f"\n🗺️  Computing district adjacency (this may take 2-5 minutes)...")

    gdf_idx = gdf.set_index("census_code")
    n = len(gdf_idx)
    ids = list(gdf_idx.index)
    geoms = list(gdf_idx.geometry)

    # Spatial index for efficient intersection queries
    sindex = gdf.sindex

    adjacency: dict[str, list[str]] = {id_: [] for id_ in ids}
    pair_count = 0

    for i, (id_a, geom_a) in enumerate(tqdm(zip(ids, geoms), total=n, desc="Building adjacency")):
        # Candidate neighbors from spatial index (bounding box overlap)
        candidates_idx = list(sindex.intersection(geom_a.bounds))
        for j in candidates_idx:
            if j <= i:
                continue
            id_b = ids[j]
            geom_b = geoms[j]
            try:
                if geom_a.touches(geom_b) or (
                    geom_a.intersects(geom_b) and
                    not geom_a.intersection(geom_b).is_empty and
                    geom_a.intersection(geom_b).length > 0.001  # shared border > ~100m
                ):
                    adjacency[id_a].append(id_b)
                    adjacency[id_b].append(id_a)
                    pair_count += 1
            except Exception:
                pass  # topology errors — skip silently

    print(f"   Found {pair_count} adjacent pairs across {n} districts")
    avg_neighbors = sum(len(v) for v in adjacency.values()) / n
    print(f"   Average neighbors per district: {avg_neighbors:.1f}")

    return adjacency

# ─── Upload to Supabase ───────────────────────────────────────────────────────
def upload_to_supabase(gdf: gpd.GeoDataFrame, adjacency: dict):
    print(f"\nUploading {len(gdf)} districts to Supabase...")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    records = []
    id_col = "canonical_id" if "canonical_id" in gdf.columns else "census_code"
    for _, row in gdf.iterrows():
        dist_id   = row[id_col]
        neighbors = adjacency.get(dist_id, [])

        record = {
            "id":             dist_id,
            "name":           row["district_name"],
            "state":          row["state_name"],
            "centroid_lat":   float(row["centroid_lat"]) if pd.notna(row["centroid_lat"]) else None,
            "centroid_lon":   float(row["centroid_lon"]) if pd.notna(row["centroid_lon"]) else None,
            "area_km2":       float(row["area_km2"]) if pd.notna(row.get("area_km2")) else None,
            "adjacency_ids":  neighbors,
            "population":     None,
        }
        records.append(record)

    # Batch upsert
    success_count = 0
    for i in tqdm(range(0, len(records), BATCH_SIZE), desc="Uploading batches"):
        batch = records[i:i + BATCH_SIZE]
        try:
            client.table("districts").upsert(batch, on_conflict="id").execute()
            success_count += len(batch)
        except Exception as e:
            print(f"\n   ❌ Batch {i//BATCH_SIZE} failed: {e}")
            time.sleep(1)
            # Retry once
            try:
                client.table("districts").upsert(batch, on_conflict="id").execute()
                success_count += len(batch)
            except Exception as e2:
                print(f"   ❌ Retry also failed: {e2}")

    print(f"\n✅ Uploaded {success_count}/{len(records)} districts to Supabase")

# ─── Save adjacency for ML pipeline ──────────────────────────────────────────
def save_adjacency_for_ml(gdf: gpd.GeoDataFrame, adjacency: dict):
    out_path = ROOT / "data/processed/district_index.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    id_col = "canonical_id" if "canonical_id" in gdf.columns else "census_code"
    ids    = list(gdf[id_col])
    index  = {id_: i for i, id_ in enumerate(ids)}

    # Adjacency edge list for scipy sparse matrix (Phase 1 ML)
    edges = {"rows": [], "cols": [], "weights": []}
    gdf_idx = gdf.set_index("census_code")

    for id_a, neighbors in adjacency.items():
        i = index.get(id_a)
        if i is None:
            continue
        for id_b in neighbors:
            j = index.get(id_b)
            if j is None:
                continue
            edges["rows"].append(i)
            edges["cols"].append(j)
            edges["weights"].append(1.0)  # unweighted v1; Phase 1 can add border-length weights

    district_index = {
        "id_to_index": index,
        "index_to_id": {str(v): k for k, v in index.items()},
        "n_districts": len(ids),
        "edges": [[r, c] for r, c in zip(edges["rows"], edges["cols"])],
        "nodes": [{"id": row.get("canonical_id", row["census_code"]), "name": row["district_name"], "state": row["state_name"]} for _, row in gdf.iterrows()],
        "metadata": {
            "source": "datameet/maps",
            "created": pd.Timestamp.now().isoformat(),
            "n_edges": len(edges["rows"])
        }
    }

    with open(out_path, "w") as f:
        json.dump(district_index, f, indent=2)
    print(f"✅ Saved district index + adjacency → {out_path}")
    print(f"   {len(ids)} nodes, {len(edges['rows'])} directed edges")

# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Script 01 -- Load India District GeoJSON / Shapefile")
    print("="*60)

    src_path = ensure_geojson_available()
    gdf = load_and_clean_geodataframe(src_path)
    gdf = compute_spatial_attributes(gdf)
    adjacency = compute_adjacency(gdf)
    save_adjacency_for_ml(gdf, adjacency)

    if SUPABASE_URL and SUPABASE_KEY:
        upload_to_supabase(gdf, adjacency)
    else:
        print("\n⚠️  Supabase credentials not set — skipping upload.")
        print("   Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")

    print("\n✅ Script 01 complete.")
