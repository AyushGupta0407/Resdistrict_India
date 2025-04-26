import geopandas as gpd

# Load the full India AC shapefile (in your working dir)
india = gpd.read_file("India_AC.shp")

# Quick check
print("States:", india["ST_NAME"].unique())

# Filter for Delhi (match the uppercase value)
delhi = india[india["ST_NAME"] == "DELHI"]

# Export directly alongside, no sub‑folders
delhi.to_file("Delhi_AC.shp")

print(f"Exported {len(delhi)} Delhi constituencies to Delhi_AC.shp")
