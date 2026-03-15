# fix_portal.py
import re

with open('pages/student_portal.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove learning_style=dominant argument
content = re.sub(
    r',\s*learning_style\s*=\s*\w+',
    '',
    content,
    flags=re.MULTILINE | re.DOTALL
)

# Remove the ls = ... line
content = re.sub(
    r'\s*ls\s*=\s*st\.session_state\.get\([^)]+\)\s*\n',
    '\n',
    content
)

# Remove the dominant = ... line
content = re.sub(
    r'\s*dominant\s*=\s*ls\.get\([^)]+\)\s*\n',
    '\n',
    content
)

with open('pages/student_portal.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done. Checking for remaining occurrences:")
found = False
for i, line in enumerate(content.split('\n'), 1):
    if 'learning_style' in line or 'dominant' in line:
        print(f"  Line {i}: {line.strip()}")
        found = True
if not found:
    print("  None found — file is clean.")