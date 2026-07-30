import os
import re
from pathlib import Path

music_static = Path(r"c:\Users\PUTRA JAYA LIMBANGAN\Documents\LWF\monorepo\apps\lunawave-music\web\static")

files_to_check = []
for root, _, files in os.walk(music_static):
    for file in files:
        if file.endswith(".js"):
            files_to_check.append(Path(root) / file)

for filepath in files_to_check:
    content = filepath.read_text(encoding="utf-8")
    original_content = content
    
    content = re.sub(r'from\s+["\'][^"\']*store\.js["\']', 'from "/framework/static/js/core/store.js"', content)
    content = re.sub(r'from\s+["\'][^"\']*transport\.js["\']', 'from "/framework/static/js/core/transport.js"', content)
    content = re.sub(r'from\s+["\'][^"\']*router\.js["\']', 'from "/framework/static/js/core/router.js"', content)
    
    if content != original_content:
        filepath.write_text(content, encoding="utf-8")
        print(f"Updated {filepath}")
