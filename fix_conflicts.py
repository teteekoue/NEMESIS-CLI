import re
from pathlib import Path

files = [
    "./agent_modular.py",
    "./tools.py",
    "./src/core/agent_manager.py",
    "./src/core/default_commands.py",
    "./src/core/skills_manager.py",
    "./.gitignore",
    "./prompt_system.txt",
    "./requirements.txt",
    "./bridge_client.py",
    "./readme.md"
]

# Pattern to find conflict: 
# <<<<<<< HEAD
# local_code
# =======
# remote_code
# >>>>>>> hash
# We want to replace it with:
# local_code

pattern = re.compile(r'<<<<<<< HEAD\n(.*?)\n=======\n.*?\n>>>>>>> .*', re.S)

for file_path in files:
    p = Path(file_path)
    if p.exists():
        content = p.read_text()
        if '<<<<<<< HEAD' in content:
            print(f"Fixing {file_path}")
            # Note: the conflict markers might have different number of newlines, 
            # I need to be careful.
            
            # Revised pattern:
            # <<<<<<< HEAD\n(.*?)\n=======(\n.*?)*?\n>>>>>>> .*
            # This is safer to handle variable remote content.
            
            new_content = re.sub(r'<<<<<<< HEAD\n(.*?)\n=======\n.*?\n>>>>>>> .*', r'\1', content, flags=re.S)
            p.write_text(new_content)
