#!/usr/bin/env bash
# Git-based deployment only; never pushes or overwrites uncommitted changes.
set -euo pipefail
NANO="${1:-m8rov123@192.168.2.2}"
ssh -t "$NANO" 'bash -lc '\''
set -eo pipefail
cd /home/m8rov123/materov_workspace/rov_software_2026
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "Tracked Nano files are modified. Preserve/reconcile them before deployment." >&2
    exit 1
fi
git pull --ff-only
export PATH=/usr/bin:$PATH PYTHONNOUSERSITE=1
source /opt/ros/humble/setup.bash
if [[ -f "$HOME/ros2_ws/install/setup.bash" ]]; then
    source "$HOME/ros2_ws/install/setup.bash"
fi
source ros/install/setup.bash
export ROS_LOCALHOST_ONLY=0 ROS_DOMAIN_ID=0 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://$PWD/ros/config/jetson/cyclonedds.xml"
if systemctl is-active --quiet rov-launch; then
    timeout 8s ros2 topic pub --once /commands std_msgs/msg/String "{data: disable_thrusters}"
fi
sudo systemctl stop rov-launch
cd ros
colcon build --packages-select interfaces materov
sudo systemctl restart rov-launch
systemctl is-active rov-launch
journalctl -u rov-launch -n 20 --no-pager
echo "Service restarted. Verify live /control/status and rebuild laptop interfaces after interface changes."
'\'''
