import os

history_dir = os.path.expandvars(r"%APPDATA%\Code\User\History")

found_files = []
for root, dirs, files in os.walk(history_dir):
    for f in files:
        if len(f) > 10:
            continue  # entries.json etc
        filepath = os.path.join(root, f)
        try:
            size = os.path.getsize(filepath)
            # Only care about files ~20KB to ~80KB
            if 20000 < size < 100000:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as file_obj:
                    content = file_obj.read()
                    if 'top-header-overlay' in content and 'livestreams' in content:
                        found_files.append((filepath, size, os.path.getmtime(filepath)))
                    elif 'top-header-overlay' in content and '{% block content %}' in content:
                        found_files.append((filepath, size, os.path.getmtime(filepath)))
        except:
            pass

found_files.sort(key=lambda x: x[2], reverse=True)
for p, s, t in found_files[:10]:
    print(f"Match: {p} (Size: {s})")
