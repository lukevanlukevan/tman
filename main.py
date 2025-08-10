import curses
import yaml
import subprocess
import argparse
import os
import time
import re

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
        return "", f"Error running command: {str(e)}"

def get_tmux_output(name):
    """Capture the output of a tmux session with ANSI color codes."""
    check_cmd = f'tmux has-session -t "{name}" 2>/dev/null'
    result = subprocess.run(check_cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        return "No active session."
    
    capture_cmd = f'tmux capture-pane -e -p -t "{name}"'
    stdout, stderr = run_command(capture_cmd)
    if stderr:
        return f"Error capturing output: stdout='{stdout}', stderr='{stderr}'"
    return stdout or "No output available."

def do_start(item):
    name = item.get("name", "Unnamed")
    command = item.get("command", "")
    directory = item.get("directory", None)
    
    if not command:
        return "No command specified."
    
    if directory:
        exec_cmd = f'cd "{directory}" && {command}'
    else:
        exec_cmd = command
    
    exec_cmd = f'source ~/.zshrc && {exec_cmd}; exec zsh'
    
    check_cmd = f'tmux has-session -t "{name}" 2>/dev/null'
    result = subprocess.run(check_cmd, shell=True, capture_output=True)
    
    if result.returncode == 0:
        return "Session already exists."
    
    start_cmd = f'tmux new-session -d -s "{name}" "zsh -c \'{exec_cmd}\'"'
    stdout, stderr = run_command(start_cmd)
    if stderr or stdout:
        return f"Start session: stdout='{stdout}', stderr='{stderr}'"
    
    result = subprocess.run(check_cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        return f"Failed to create session: stdout='{stdout}', stderr='{stderr}'"
    
    time.sleep(0.5)
    return "Session started successfully."

def do_restart(item):
    name = item.get("name", "Unnamed")
    command = item.get("command", "")
    directory = item.get("directory", None)
    
    if not command:
        return "No command specified."
    
    if directory:
        exec_cmd = f'cd "{directory}" && {command}'
    else:
        exec_cmd = command
    
    exec_cmd = f'source ~/.zshrc && {exec_cmd}; exec zsh'
    
    kill_cmd = f'tmux kill-session -t "{name}" 2>/dev/null'
    run_command(kill_cmd)
    
    start_cmd = f'tmux new-session -d -s "{name}" "zsh -c \'{exec_cmd}\'"'
    stdout, stderr = run_command(start_cmd)
    if stderr or stdout:
        return f"Restart session: stdout='{stdout}', stderr='{stderr}'"
    
    check_cmd = f'tmux has-session -t "{name}" 2>/dev/null'
    result = subprocess.run(check_cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        return f"Failed to restart session: stdout='{stdout}', stderr='{stderr}'"
    
    time.sleep(0.5)
    return "Session restarted successfully."

def do_close(item):
    name = item.get("name", "Unnamed")
    kill_cmd = f'tmux kill-session -t "{name}" 2>/dev/null'
    stdout, stderr = run_command(kill_cmd)
    if "can't find session" in stderr:
        return "Session does not exist."
    elif stderr or stdout:
        return f"Close session: stdout='{stdout}', stderr='{stderr}'"
    return "Session closed successfully."

def do_open(item):
    name = item.get("name", "Unnamed")
    check_cmd = f'tmux has-session -t "{name}" 2>/dev/null'
    result = subprocess.run(check_cmd, shell=True, capture_output=True)
    
    if result.returncode != 0:
        return "Session does not exist."
    
    os.system(f'tmux attach-session -t "{name}"')
    return "Attaching to session..."

def init_colors():
    """Initialize curses color pairs for ANSI color codes."""
    curses.start_color()
    curses.use_default_colors()
    
    # Map ANSI color codes to curses color pairs
    # ANSI: 30=black, 31=red, 32=green, 33=yellow, 34=blue, 35=magenta, 36=cyan, 37=white
    for i, color in enumerate([
        curses.COLOR_BLACK, curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_YELLOW,
        curses.COLOR_BLUE, curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_WHITE
    ], 1):
        curses.init_pair(i, color, -1)  # Foreground color, default background
    curses.init_pair(9, -1, -1)  # Default color (no ANSI code)

def parse_ansi(text):
    """Parse ANSI escape codes and yield (text, color_pair) tuples."""
    ansi_pattern = re.compile(r'\x1b\[([0-9;]*)m')
    parts = ansi_pattern.split(text)
    current_pair = 9  # Default color pair
    i = 0
    
    while i < len(parts):
        if i % 2 == 0:
            if parts[i]:
                yield parts[i], current_pair
        else:
            codes = parts[i].split(';')
            if not codes or codes == ['']:
                current_pair = 9  # Reset to default
            else:
                for code in codes:
                    if code in ['30', '31', '32', '33', '34', '35', '36', '37']:
                        current_pair = int(code) - 29  # Map 30->1, 31->2, etc.
                    elif code == '0':
                        current_pair = 9  # Reset
        i += 1

def draw_menu(stdscr, items, selected_row, output, tmux_output):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    
    stdscr.box()
    stdscr.addstr(0, 2, " Commands ")
    
    left_width = w // 3
    for idx, item in enumerate(items):
        name = item.get("name", "Unnamed")
        if idx == selected_row:
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(idx + 1, 1, name[:left_width-2].ljust(left_width-2))
            stdscr.attroff(curses.A_REVERSE)
        else:
            stdscr.addstr(idx + 1, 1, name[:left_width-2])
    
    stdscr.addstr(0, left_width + 1, " Output ")
    stdscr.vline(1, left_width, curses.ACS_VLINE, h-2)
    
    display_output = tmux_output if tmux_output else output
    if display_output:
        lines = display_output.split('\n')
        for i, line in enumerate(lines[:h-3]):
            if i >= h - 3:
                break
            x = left_width + 2
            for text, color_pair in parse_ansi(line):
                if x >= w - 1:
                    break
                display_text = text[:w - x - 1]
                if display_text:
                    try:
                        stdscr.addstr(i + 1, x, display_text, curses.color_pair(color_pair))
                    except curses.error:
                        pass  # Ignore errors from writing outside window
                    x += len(display_text)
    
    hotkey_bar = " [s] Start  [r] Restart  [c] Close  [o] Open  [q] Quit "
    stdscr.addstr(h-1, 0, hotkey_bar[:w-1].center(w-1), curses.A_REVERSE)
    
    stdscr.refresh()

def main(stdscr, config_path):
    init_colors()
    curses.curs_set(0)
    items = load_config(config_path).get("items", [])
    selected_row = 0
    output = ""
    last_selected = None
    tmux_output = ""
    last_tmux_output = ""
    
    while True:
        if items and (selected_row != last_selected or output):
            new_tmux_output = get_tmux_output(items[selected_row].get("name", "Unnamed"))
            if new_tmux_output != last_tmux_output or output or selected_row != last_selected:
                tmux_output = new_tmux_output
                last_tmux_output = tmux_output
                last_selected = selected_row
                draw_menu(stdscr, items, selected_row, output, tmux_output)
            if output:
                output = ""
        elif items:
            new_tmux_output = get_tmux_output(items[selected_row].get("name", "Unnamed"))
            if new_tmux_output != last_tmux_output:
                tmux_output = new_tmux_output
                last_tmux_output = tmux_output
                draw_menu(stdscr, items, selected_row, output, tmux_output)
        
        stdscr.timeout(1000)
        try:
            key = stdscr.getch()
        except curses.error:
            key = -1
        
        if (key == curses.KEY_UP or key == ord('k')) and selected_row > 0:
            selected_row -= 1
            draw_menu(stdscr, items, selected_row, output, tmux_output)
        elif (key == curses.KEY_DOWN or key == ord('j')) and selected_row < len(items) - 1:
            selected_row += 1
            draw_menu(stdscr, items, selected_row, output, tmux_output)
        elif key in [ord('\n'), ord('s')] and items:
            output = do_start(items[selected_row])
            tmux_output = get_tmux_output(items[selected_row].get("name", "Unnamed"))
            last_tmux_output = tmux_output
            draw_menu(stdscr, items, selected_row, output, tmux_output)
        elif key == ord('r') and items:
            output = do_restart(items[selected_row])
            tmux_output = get_tmux_output(items[selected_row].get("name", "Unnamed"))
            last_tmux_output = tmux_output
            draw_menu(stdscr, items, selected_row, output, tmux_output)
        elif key == ord('c') and items:
            output = do_close(items[selected_row])
            tmux_output = "No active session."
            last_tmux_output = tmux_output
            draw_menu(stdscr, items, selected_row, output, tmux_output)
        elif key == ord('o') and items:
            output = do_open(items[selected_row])
            break
        elif key == ord('q'):
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI app with config-driven commands")
    parser.add_argument('--config', default='config.yml', help='Path to config file')
    args = parser.parse_args()
    
    if not os.path.exists(args.config):
        with open(args.config, 'w') as f:
            yaml.dump({"items": []}, f, default_flow_style=False)
    
    curses.wrapper(main, args.config)
