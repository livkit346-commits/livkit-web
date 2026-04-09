import os
import json
import datetime

history_dir = os.path.expandvars(r"%APPDATA%\Code\User\History")

for root, dirs, files in os.walk(history_dir):
    if 'entries.json' in files:
        entries_path = os.path.join(root, 'entries.json')
        try:
            with open(entries_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                resource = data.get('resource', '')
                if 'templates/index.html' in resource.replace('\\', '/') or 'templates/live.html' in resource.replace('\\', '/'):
                    print(f"History for: {resource}")
                    for entry in data.get('entries', []):
                        timestamp = entry.get('timestamp')
                        dt = datetime.datetime.fromtimestamp(timestamp / 1000.0)
                        entry_id = entry.get('id')
                        entry_file = os.path.join(root, entry_id)
                        size = os.path.getsize(entry_file) if os.path.exists(entry_file) else 0
                        print(f"  Entry: {entry_id}, Time: {dt}, Size: {size}")
        except Exception as e:
            pass
