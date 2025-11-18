import json

with open("/workspaces/blank-app/file.geojson", "r") as f:
    geojson_data = json.load(f)

print(geojson_data["features"][0]["properties"])