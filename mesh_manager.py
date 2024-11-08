import os
import time
import re
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

PRINTER_CFG_PATH = Path.home() / "printer_data" / "config" / "printer.cfg"
TIMESTAMP_FILE_PATH = Path.home() / "printer_data" / "config" / "mesh_timestamp.txt"
CHECK_INTERVAL = 60 * 60  # Check every hour
MAX_AGE = 12 * 60 * 60  # 12 hours in seconds

def read_printer_cfg():
    with open(PRINTER_CFG_PATH, 'r') as file:
        return file.read()

def write_printer_cfg(content):
    with open(PRINTER_CFG_PATH, 'w') as file:
        file.write(content)

def get_mesh_data(content, mesh_name):
    mesh_pattern = rf'#\*# \[bed_mesh {mesh_name}\](.*?)(?=#\*# \[|\Z)'
    match = re.search(mesh_pattern, content, re.DOTALL)
    return match.group(0) if match else None

def read_timestamp():
    if TIMESTAMP_FILE_PATH.exists():
        with open(TIMESTAMP_FILE_PATH, 'r') as file:
            return int(file.read().strip())
    return None

def write_timestamp(timestamp):
    with open(TIMESTAMP_FILE_PATH, 'w') as file:
        file.write(str(timestamp))

def rename_mesh(content, old_name, new_name):
    return content.replace(f'[bed_mesh {old_name}]', f'[bed_mesh {new_name}]')

def delete_mesh(content, mesh_name):
    mesh_pattern = rf'#\*# \[bed_mesh {mesh_name}\](.*?)(?=#\*# \[|\Z)'
    return re.sub(mesh_pattern, '', content, flags=re.DOTALL)

def is_file_in_use(filepath):
    try:
        with open(filepath, 'r+'):
            return False
    except IOError:
        return True

def check_and_manage_mesh():
    timestamp = read_timestamp()
    current_time = int(time.time())
    
    if timestamp is None:
        print("No timestamp found. Creating new timestamp.")
        write_timestamp(current_time)
    elif current_time - timestamp > MAX_AGE:
        print("Mesh is older than 12 hours. Attempting to rename to outdated_session_mesh.")
        if not is_file_in_use(PRINTER_CFG_PATH):
            content = read_printer_cfg()
            content = delete_mesh(content, 'outdated_session_mesh')
            content = rename_mesh(content, 'session_mesh', 'outdated_session_mesh')
            write_printer_cfg(content)
            print("Renamed session_mesh to outdated_session_mesh.")
        else:
            print("printer.cfg is in use. Will try again later.")
    else:
        print("Mesh is up to date.")

class PrinterCfgHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_modified = time.time()

    def on_modified(self, event):
        if event.src_path == str(PRINTER_CFG_PATH):
            current_time = time.time()
            if current_time - self.last_modified > 5:  # Debounce: only process events every 5 seconds
                self.last_modified = current_time
                print("printer.cfg modified. Updating timestamp.")
                write_timestamp(int(current_time))

def main():
    print("Mesh manager service started")
    print(f"Monitoring printer.cfg at: {PRINTER_CFG_PATH}")

    event_handler = PrinterCfgHandler()
    observer = Observer()
    observer.schedule(event_handler, path=str(PRINTER_CFG_PATH.parent), recursive=False)
    observer.start()

    try:
        while True:
            check_and_manage_mesh()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
