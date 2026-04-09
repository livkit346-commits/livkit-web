import os

history_dir = os.path.expandvars(r"%APPDATA%\Code\User\History")

found = []
for root, dirs, files in os.walk(history_dir):
    for f in files:
        if len(f) > 10:
            continue
        filepath = os.path.join(root, f)
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as file_obj:
                content = file_obj.read()
                # Use a very specific CSS class that we know was there
                if '.streamer-profile-pill' in content:
                    found.append((filepath, len(content)))
        except:
            pass

found.sort(key=lambda x: x[1], reverse=True)
for p, s in found[:20]:
    print(f"Match: {p} - {s} chars")
