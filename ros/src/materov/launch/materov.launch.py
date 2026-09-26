"""Vehicle nodes recover independently; optional ZED can be disabled explicitly."""
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory, PackageNotFoundError


def generate_launch_description():
    actions = [DeclareLaunchArgument('enable_zed', default_value='true')]
    for executable in ('jetson_node', 'camera_node', 'imu_sensor_node',
                       'pressure_sensor_node', 'signal_publisher_node'):
        actions.append(Node(package='materov', executable=executable,
                            output='screen', respawn=True, respawn_delay=5.0))
    try:
        path = os.path.join(get_package_share_directory('zed_wrapper'),
                            'launch', 'zed_camera.launch.py')
        actions.append(IncludeLaunchDescription(
            PythonLaunchDescriptionSource(path),
            condition=IfCondition(LaunchConfiguration('enable_zed')),
            launch_arguments={'camera_model': 'zed2i', 'publish_tf': 'true'}.items()))
    except PackageNotFoundError:
        print('zed_wrapper not installed; skipping optional ZED')
    return LaunchDescription(actions)
