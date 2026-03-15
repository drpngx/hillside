#!/usr/bin/env python3
"""Build script for ZMK firmware."""

import os
import subprocess
import sys

# Constant referencing the ZMK Studio mmv issue
# See: https://github.com/zmkfirmware/zmk-studio/issues/168
# ZMK Studio doesn't support mmv (mouse movement), so this flag controls
# whether we build with ZMK Studio support.
ENABLE_ZMK_STUDIO = False

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ZMK_CONFIG_DIR = os.path.join(SCRIPT_DIR, "zmk-config")
FIRMWARE_OUTPUT_DIR = os.path.join(ZMK_CONFIG_DIR, "firmware")
ZMK_WORKSPACE_VOLUME = "zmk-workspace"
DOCKER_IMAGE = "zmkfirmware/zmk-dev-arm:4.1-branch"

# Build flags
LEFT_SHIELD = "hshs52_left nice_view_adapter nice_view"
RIGHT_SHIELD = "hshs52_right nice_view_adapter nice_view"
BOARD = "nice_nano/nrf52840/zmk"


def run_command(cmd: list[str], check: bool = True) -> None:
    """Run a shell command."""
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=check)


def check_docker() -> None:
    """Check if Docker is available."""
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: Docker is not installed or not running.", file=sys.stderr)
        sys.exit(1)


def main() -> int:
    """Main entry point."""
    print("Starting ZMK firmware build... ⚙️")

    # Check Docker availability
    check_docker()

    # Ensure the ZMK config directory exists
    if not os.path.isdir(ZMK_CONFIG_DIR):
        print(f"Error: ZMK config directory not found at {ZMK_CONFIG_DIR}", file=sys.stderr)
        return 1

    # Create the output directory if it doesn't exist
    os.makedirs(FIRMWARE_OUTPUT_DIR, exist_ok=True)

    print(f"Building with config from: {ZMK_CONFIG_DIR}")
    print(f"Firmware will be placed in: {FIRMWARE_OUTPUT_DIR}")
    print(f"Using Docker volume: {ZMK_WORKSPACE_VOLUME}")
    print(f"ZMK Studio enabled: {ENABLE_ZMK_STUDIO}")

    # Create the Docker volume if it doesn't exist
    subprocess.run(
        ["docker", "volume", "create", ZMK_WORKSPACE_VOLUME],
        capture_output=True
    )

    # Build the command sequence
    studio_flag = "-S studio-rpc-usb-uart" if ENABLE_ZMK_STUDIO else ""
    studio_config = "-DCONFIG_ZMK_STUDIO=y" if ENABLE_ZMK_STUDIO else ""

    command = f"""
set -eux

# Create workspace directory if it doesn't exist
mkdir -p /app/workspace
cd /app/workspace

# Always ensure fresh config and proper west initialization
echo 'Ensuring fresh config...'
rm -rf config
cp -r /app/config/config ./

# Create a hash of the current config to detect changes
CONFIG_HASH=$(find config -type f -exec sha256sum {{}} \\; | sort | sha256sum | cut -d' ' -f1)
STORED_HASH=""
if [ -f .config_hash ]; then
    STORED_HASH=$(cat .config_hash)
fi

# Re-initialize if config changed or workspace not initialized
if [ ! -f .west/config ] || [ "$CONFIG_HASH" != "$STORED_HASH" ]; then
    echo 'Config changed or workspace not initialized - reinitializing...'
    rm -rf .west
    west init -l config
    echo "$CONFIG_HASH" > .config_hash
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
west build -p auto -s zmk/app -b {BOARD} {studio_flag} -d build/left -- \\
    -DSHIELD=\"{LEFT_SHIELD}\" \\
    -DZMK_CONFIG=/app/workspace/config {studio_config} \\
    -DCMAKE_BUILD_TYPE=Release \\
    -DCMAKE_C_FLAGS_RELEASE='-O3' \\
    -DCMAKE_CXX_FLAGS_RELEASE='-O3'
cp build/left/zephyr/zmk.uf2 /app/firmware/hshs52_left.uf2

# --- Build Right Half ---
echo 'Building Right Half...'
west build -p auto -s zmk/app -b {BOARD} -d build/right -- \\
    -DSHIELD=\"{RIGHT_SHIELD}\" \\
    -DZMK_CONFIG=/app/workspace/config {studio_config} \\
    -DCMAKE_BUILD_TYPE=Release \\
    -DCMAKE_C_FLAGS_RELEASE='-O3' \\
    -DCMAKE_CXX_FLAGS_RELEASE='-O3'
cp build/right/zephyr/zmk.uf2 /app/firmware/hshs52_right.uf2
"""

    # Run the entire command sequence inside the container with volume mounting
    docker_cmd = [
        "docker", "run", "--rm", "-it",
        "--mount", f"type=bind,source={ZMK_CONFIG_DIR},target=/app/config,readonly",
        "--mount", f"type=bind,source={FIRMWARE_OUTPUT_DIR},target=/app/firmware",
        "--mount", f"type=volume,source={ZMK_WORKSPACE_VOLUME},target=/app/workspace",
        DOCKER_IMAGE,
        "bash", "-c", command
    ]

    try:
        run_command(docker_cmd)
    except subprocess.CalledProcessError as e:
        print(f"Build failed with exit code {e.returncode}", file=sys.stderr)
        return e.returncode

    print("Build complete! ✅")
    print(f"Your firmware files are hshs52_right.uf2 and hshs52_left.uf2 inside the '{FIRMWARE_OUTPUT_DIR}' directory.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
