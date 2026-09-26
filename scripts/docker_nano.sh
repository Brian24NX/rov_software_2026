#!/usr/bin/env bash
#
# Run the Jetson ROS 2 stack in a container, for hosts that cannot run Humble
# natively (e.g. a Nano flashed with a JetPack based on Ubuntu 24.04).
#
#   bash scripts/docker_nano.sh build     # build the image
#   bash scripts/docker_nano.sh           # interactive shell in the container
#   bash scripts/docker_nano.sh <cmd...>  # run one command in the container

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IMAGE:-materov-nano:humble}"

command -v docker >/dev/null || {
  echo "docker is not installed. Install it with:" >&2
  echo "  sudo apt install -y docker.io && sudo usermod -aG docker \$USER" >&2
  echo "then log out and back in." >&2
  exit 1
}

if [ "${1:-}" = "build" ]; then
  exec docker build -f "$REPO_ROOT/Dockerfile.nano" -t "$IMAGE" "$REPO_ROOT"
fi

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Image $IMAGE not found. Build it first:" >&2
  echo "  bash scripts/docker_nano.sh build" >&2
  exit 1
fi

# Pass through only devices that actually exist - docker run aborts on a
# --device that isn't there, which would make a missing camera look like a
# container problem.
DEVICES=()
for dev in /dev/i2c-7 /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyACM0; do
  [ -e "$dev" ] && DEVICES+=(--device="$dev")
done
for dev in /dev/video*; do
  [ -e "$dev" ] && DEVICES+=(--device="$dev")
done

echo "Passing through: ${DEVICES[*]:-(no devices found)}"

# --network=host and --ipc=host are both required for DDS: bridge networking
# blocks multicast discovery, and without host IPC Cyclone drops off shared
# memory between containerised and host nodes.
exec docker run -it --rm \
  --name materov-nano \
  --network=host \
  --ipc=host \
  "${DEVICES[@]}" \
  -v "$REPO_ROOT":/workspace \
  -w /workspace \
  -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}" \
  -e ROS_LOCALHOST_ONLY=0 \
  -e RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
  -e CYCLONEDDS_URI="file:///workspace/ros/config/jetson/cyclonedds.xml" \
  "$IMAGE" "$@"
