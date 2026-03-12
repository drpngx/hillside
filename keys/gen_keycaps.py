import os
import io
import urllib.parse
import requests
import trimesh
import numpy as np

# --- CONFIGURATION ---
BED_SIZE = 240
MARGIN = 10
SPACING = 20

# The Hillside 52 Recipe
# Updated for new filename format in KLP-Lame-Keycaps repo
KEY_RECIPE = {
    "MX_Stem_Choc_Size_Normal_Homing.stl": 2,
    "MX_Stem_Choc_Size_Normal.stl": 10,
    "MX_Stem_Choc_Size_Normal_Tilted.stl": 24,
    "MX_Stem_Choc_Size_Thumb.stl": 16
}

# Ensure it exports to your actual workspace if running via `bazel run`
WORKSPACE_DIR = os.environ.get("BUILD_WORKSPACE_DIRECTORY", ".")
OUTPUT_FILE = os.path.join(WORKSPACE_DIR, "keys.stl")


def fetch_mesh_from_github(filename):
  """Downloads the STL directly into memory to bypass Bazel's read-only sandbox."""
  # Properly encode spaces and '+' signs, but leave '/' alone
  folder_path = urllib.parse.quote("STL/MX Stem + Choc Size/")
  # New repo uses master branch only (no main branch)
  safe_filename = urllib.parse.quote(filename)

  # Try both branches just in case the repo updates
  for branch in ["master", "main"]:
    url = f"https://raw.githubusercontent.com/braindefender/KLP-Lame-Keycaps/{branch}/{folder_path}{safe_filename}"

    response = requests.get(url)
    if response.status_code == 200:
      print(f"[{branch}] Successfully fetched {filename}")
      # Load the STL directly from the downloaded bytes
      return trimesh.load(file_obj=io.BytesIO(response.content), file_type='stl')

  print(f"[!] Error: Could not find {filename} on GitHub (HTTP 404).")
  return None


def build_plate():
  plate_scene = trimesh.Scene()
  current_x = MARGIN
  current_y = MARGIN
  placed_count = 0

  print("Fetching keycaps from GitHub and arranging on the 240x240 bed...")

  for filename, quantity in KEY_RECIPE.items():
    base_mesh = fetch_mesh_from_github(filename)

    if base_mesh is None:
      continue

    for _ in range(quantity):
      mesh_copy = base_mesh.copy()

      # Check if we need to wrap to a new row
      if current_x + SPACING > BED_SIZE - MARGIN:
        current_x = MARGIN
        current_y += SPACING

        # Failsafe for bed height
        if current_y + SPACING > BED_SIZE - MARGIN:
          print("Warning: Out of bed space! Stopping placement.")
          break

      translation_matrix = trimesh.transformations.translation_matrix([current_x, current_y, 0])
      mesh_copy.apply_transform(translation_matrix)
      plate_scene.add_geometry(mesh_copy)

      current_x += SPACING
      placed_count += 1

  # Safely catch an empty plate before trimesh throws an error
  if placed_count == 0:
    print("\n[!] FATAL ERROR: No keycaps were downloaded. The build plate is empty.")
    print("Please check your internet connection or Bazel network proxy settings.")
    return

  print(f"\nSuccessfully placed {placed_count} keycaps.")
  print(f"Exporting to {OUTPUT_FILE}...")
  # Export as combined STL ( Scene.export to 3mf requires lxml which is a soft dep)
  combined = plate_scene.to_geometry()
  combined.export(OUTPUT_FILE)
  print("Done! You can now open this file in your slicer.")


if __name__ == "__main__":
  build_plate()
