#!/usr/bin/env bash
# Run the GUI and API with the same ROS environment as the laptop stack.
set -eo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/usr/bin:$PATH"
export PYTHONNOUSERSITE=1
source /opt/ros/humble/setup.bash
source "$REPO_ROOT/ros/install/setup.bash"
export ROS_DOMAIN_ID=0 ROS_LOCALHOST_ONLY=0 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://$REPO_ROOT/ros/config/laptop/cyclonedds.xml"
export MATROV_JOY_BACKEND="${MATROV_JOY_BACKEND:-pygame}"
cd "$REPO_ROOT/mission_control"
PYTHON="$PWD/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo 'Create mission_control/.venv and install requirements first.' >&2
    exit 1
fi
if "$PYTHON" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",8000)); s.close()' 2>/dev/null; then
    "$PYTHON" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
    backend_pid=$!
    trap 'kill "$backend_pid" 2>/dev/null || true; wait "$backend_pid" 2>/dev/null || true' EXIT
else
    echo 'Port 8000 is already in use; the GUI will connect to that backend.'
fi
"$PYTHON" gui/app.py
