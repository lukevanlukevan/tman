import curses
import yaml
import subprocess
import argparse
import os
import time

def load_config(config_path):
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or {"items": []}
    except FileNotFoundError:
        return {"items": []}
    except yaml.YAMLError:
        return {"items": []}

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout, result.stderr
    except subprocess.SubprocessError as e:
        return "", f"Error running command: {e}"

def get_tmux_output(name):
    """Capture the output of a tmux session."""
    check_cmd = f'tmux has-session -t "{name}"'
    result = subprocess.run(check_cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        return "No active session."
    
    capture_cmd = f'tmux capture-pane -t "{name}" -p'
    stdout, stderr = run_command(capture_cmd)
    if stderr:
        return f"Error capturing output: {stderr}"
    return stdout or "No output available."

def do_start(item):
    name = item.get("name", "Unnamed")
    command = item.get("command", "")
    directory = item.get("directory", None)
    
    if directory:
        exec_cmd = f'cd "{directory}" && {command}'
    else:
        exec_cmd = command
    
    check_cmd = f'tmux has-session -t "{name}"'
    result = subprocess.run(check_cmd, shell=True, capture_output=True)
    
    if result.returncode == 0:
        return "Session already exists."
    else:
        start_cmd = f'tmux new-session -d -s "{name}" "{exec_cmd}"'
        stdout, stderr = run_command(start_cmd)
        if stderr:
            return stderr
        else:
            return "Session started successfully."

def do_restart(item):
    name = item.get("name", "Unnamed")
    command = item.get("command", "")
    directory = item.get("directory", None)
    
    if directory:
        exec_cmd = f'cd "{directory}" && {command}'
    else:
        exec_cmd = command
    
    kill_cmd = f'tmux kill-session -t "{name}"'
    run_command(kill_cmd)  # Ignore output, proceeds even if session doesn't exist
    
    start_cmd = f'tmux new-session -d -s "{name}" "{exec_cmd}"'
    stdout, stderr = run_command(start_cmd)
    if stderr:
        return stderr
    else:
        return "Session restarted successfully."

def do_close(item):
    name = item.get("name", "Unnamed")
    kill_cmd = f'tmux kill-session -t "{name}"'
    stdout, stderr = run_command(kill_cmd)
    if "can't find session" in stderr:
        return "Session does not exist."
    elif stderr:
        return stderr
    else:
        return "Session closed successfully."

def do_open(item):
    name = item.get("name", "Unnamed")
    check_cmd = f'tmux has-session -t "{name}"'
    result = subprocess.run(check_cmd, shell=True, capture_output=True)
    
    if result.returncode != 0:
        return "Session does not exist."
    
    # Attach to the tmux session and exit the curses app
    os.system(f'tmux attach-session -t "{name}"')
    return "Attaching to session..."

def draw_menu(stdscr, items, selected_row, output, tmux_output):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    
    # Draw border for the item list (left panel)
    stdscr.box()
    stdscr.addstr(0, 2, " Commands ")
    
    # Draw items in the left panel
    left_width = w // 3
    for idx, item in enumerate(items):
        name = item.get("name", "Unnamed")
        if idx == selected_row:
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(idx + 1, 1, name[:left_width-2].ljust(left_width-2))
            stdscr.attroff(curses.A_REVERSE)
        else:
            stdscr.addstr(idx + 1, 1, name[:left_width-2])
    
    # Draw output in the right panel
    stdscr.addstr(0, left_width + 1, " Output ")
    stdscr.vline(1, left_width, curses.ACS_VLINE, h-2)
    
    # Prioritize tmux_output if available, otherwise show action output
    display_output = tmux_output if tmux_output else output
    if display_output:
        lines = display_output.split('\n')
        for i, line in enumerate(lines[:h-3]):  # Adjusted for hotkey bar
            stdscr.addstr(i + 1, left_width + 2, line[:w-left_width-3])
    
    # Draw hotkey bar at the bottom
    hotkey_bar = " [s] Start  [r] Restart  [c] Close  [o] Open  [q] Quit "
    stdscr.addstr(h-1, 0, hotkey_bar[:w-1].center(w-1), curses.A_REVERSE)
    
    stdscr.refresh()

def main(stdscr, config_path):
    curses.curs_set(0)  # Hide cursor
    items = load_config(config_path).get("items", [])
    selected_row = 0
    output = ""  # For action status messages
    last_selected = None
    tmux_output = ""  # For tmux session output
    
    while True:
        # Fetch tmux output only when selection changes or after an action
        if items and (selected_row != last_selected or output):
            tmux_output = get_tmux_output(items[selected_row].get("name", "Unnamed"))
            last_selected = selected_row
            if output:  # Clear action output after displaying once
                output = ""
        
        draw_menu(stdscr, items, selected_row, output, tmux_output)
        stdscr.timeout(1000)  # Refresh every second to update tmux output
        key = stdscr.getch()
        
        # Navigation
        if (key == curses.KEY_UP or key == ord('k')) and selected_row > 0:
            selected_row -= 1
        elif (key == curses.KEY_DOWN or key == ord('j')) and selected_row < len(items) - 1:
            selected_row += 1
        elif key in [ord('\n'), ord('s')] and items:  # Enter or 's' to start
            output = do_start(items[selected_row])
            tmux_output = get_tmux_output(items[selected_row].get("name", "Unnamed"))
        elif key == ord('r') and items:  # Restart
            output = do_restart(items[selected_row])
            tmux_output = get_tmux_output(items[selected_row].get("name", "Unnamed"))
        elif key == ord('c') and items:  # Close
            output = do_close(items[selected_row])
            tmux_output = "No active session."
        elif key == ord('o') and items:  # Open (attach to tmux session)
            output = do_open(items[selected_row])
            break  # Exit curses after attaching
        elif key == ord('q'):  # Quit
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI app with config-driven commands")
    parser.add_argument('--config', default='config.yml', help='Path to config file')
    args = parser.parse_args()
    
    if not os.path.exists(args.config):
        with open(args.config, 'w') as f:
            yaml.dump({"items": []}, f, default_flow_style=False)
    
    curses.wrapper(main, args.config)
