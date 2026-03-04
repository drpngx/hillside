#!/bin/bash
# Exit on error, treat unset variables as errors, and fail on pipe errors.
set -euo pipefail

# --- Configuration ---
# Get the absolute path to your ZMK config directory.
ZMK_CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)/zmk-config"
# Define a directory to store the built firmware.
FIRMWARE_OUTPUT_DIR="${ZMK_CONFIG_DIR}/firmware"
# Docker volume name for caching the west workspace
ZMK_WORKSPACE_VOLUME="zmk-workspace"

# --- Script ---
echo "Starting ZMK firmware build... ⚙️"

# Ensure the ZMK config directory exists
if [ ! -d "$ZMK_CONFIG_DIR" ]; then
  echo "Error: ZMK config directory not found at $ZMK_CONFIG_DIR" >&2
  exit 1
fi

# Create the output directory if it doesn't exist
mkdir -p "$FIRMWARE_OUTPUT_DIR"

echo "Building with config from: $ZMK_CONFIG_DIR"
echo "Firmware will be placed in: $FIRMWARE_OUTPUT_DIR"
echo "Using Docker volume: $ZMK_WORKSPACE_VOLUME"

# Create the Docker volume if it doesn't exist
docker volume create "$ZMK_WORKSPACE_VOLUME" >/dev/null 2>&1 || true

# This command sequence builds firmware with cached workspace
COMMAND="
  # Exit on error and print each command before running it.
  set -eux

  # Create workspace directory if it doesn't exist
  mkdir -p /app/workspace
  cd /app/workspace

  # Always ensure fresh config and proper west initialization
  echo 'Ensuring fresh config...'
  rm -rf config
  cp -r /app/config/config ./

  # Create a hash of the current config to detect changes
  CONFIG_HASH=\$(find config -type f -exec sha256sum {} \\; | sort | sha256sum | cut -d' ' -f1)
  STORED_HASH=""
  if [ -f .config_hash ]; then
    STORED_HASH=\$(cat .config_hash)
  fi

  # Re-initialize if config changed or workspace not initialized
  if [ ! -f .west/config ] || [ \"\$CONFIG_HASH\" != \"\$STORED_HASH\" ]; then
    echo 'Config changed or workspace not initialized - reinitializing...'
    rm -rf .west
    west init -l config
    echo \"\$CONFIG_HASH\" > .config_hash
  else
    echo 'Config unchanged, using existing workspace'
  fi

  # Update dependencies (this will be much faster after first run)
  echo 'Updating dependencies...'
  west update

  # Export the Zephyr CMake package
  echo 'Exporting Zephyr...'
  west zephyr-export

  # Clean any previous builds
  rm -rf build

  # --- Build Left Half ---
  echo 'Building Left Half...'
  west build -p auto -s zmk/app -b nice_nano/nrf52840/zmk -S studio-rpc-usb-uart -d build/left -- \
    -DSHIELD=\"hshs52_left nice_view_adapter nice_view\" \
    -DZMK_CONFIG=/app/workspace/config -DCONFIG_ZMK_STUDIO=n \
    -DCMAKE_BUILD_TYPE=Release \
     -DCMAKE_C_FLAGS_RELEASE='-O3' \
     -DCMAKE_CXX_FLAGS_RELEASE='-O3'
  cp build/left/zephyr/zmk.uf2 /app/firmware/hshs52_left.uf2

  # --- Build Right Half ---
  echo 'Building Right Half...'
  west build -p auto -s zmk/app -b nice_nano/nrf52840/zmk -d build/right -- \
    -DSHIELD=\"hshs52_right nice_view_adapter nice_view\" \
    -DZMK_CONFIG=/app/workspace/config -DCONFIG_ZMK_STUDIO=n \
    -DCMAKE_BUILD_TYPE=Release \
     -DCMAKE_C_FLAGS_RELEASE='-O3' \
     -DCMAKE_CXX_FLAGS_RELEASE='-O3'
  cp build/right/zephyr/zmk.uf2 /app/firmware/hshs52_right.uf2
"

# Run the entire command sequence inside the container with volume mounting
docker run --rm -it \
  --mount type=bind,source="$ZMK_CONFIG_DIR",target=/app/config,readonly \
  --mount type=bind,source="$FIRMWARE_OUTPUT_DIR",target=/app/firmware \
  --mount type=volume,source="$ZMK_WORKSPACE_VOLUME",target=/app/workspace \
  zmkfirmware/zmk-dev-arm:3.5-branch \
  bash -c "$COMMAND"

echo "Build complete! ✅"
echo "Your firmware files are hshs52_right.uf2 and hshs52_left.uf2 inside the '$FIRMWARE_OUTPUT_DIR' directory."
