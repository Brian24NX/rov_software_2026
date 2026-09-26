# Mission control desktop (Matrov)

FastAPI backend + CustomTkinter GUI for ROV task selection, instructions, image
uploads, and robot commands through the ROS 2 bridge to the Nano.

## Setup

```bash
cd mission_control
/usr/bin/python3 -m venv .venv  # Python 3.10 for ROS 2 Humble
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## Run

From the repository root, run these in separate terminals after building the ROS
workspace (see the [root README](../README.md)):

```bash
bash scripts/launch_laptop.sh           # video, joystick and reconstruction
bash scripts/launch_mission_control.sh  # API and GUI with the ROS environment
```

API default: `http://127.0.0.1:8000`. Optional pygame joystick: see
`requirements-joystick.txt` (Linux/Windows only).

## Layout

| Path | Role |
|------|------|
| `backend/` | FastAPI app, `tasks.json`, upload storage |
| `gui/` | CustomTkinter screens and API client |
| `shared/` | `RobotInterface` ROS/API bridge |

## Controls and tasks

Arrows/Enter/Escape provide keyboard navigation. Gamepad menu navigation is
disabled while armed or vehicle state is unknown. Leaving the thruster screen or
closing the app requests disarm; the footer shows the vehicle's acknowledged
state and reports UNKNOWN when its heartbeat expires.

Task 1.2 requests live image capture and COLMAP reconstruction. Other task entries
provide operator instructions; automated `run_task` and `send_images` actions are
not implemented. Image uploads are separate laptop storage, not reconstruction
inputs. Uploads accept up to 20 JPEG/PNG/BMP/GIF files, 10 MiB per file and 50 MiB
per request, with unique stored names.

## macOS notes

If `tkinter.Tk()` aborts, use Homebrew Python 3.12 and a fresh venv. Run
`python diagnose_gui.py` from this folder to verify Tcl/Tk. These notes cover the
standalone GUI; vehicle commands require a compatible ROS environment.

