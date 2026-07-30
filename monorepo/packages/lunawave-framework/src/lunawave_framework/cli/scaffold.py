import os
import shutil
from pathlib import Path

def get_templates_dir() -> Path:
    return Path(__file__).parent.parent / "templates"

def replace_in_file(filepath: Path, search: str, replace: str):
    if not filepath.exists() or not filepath.is_file():
        return
    content = filepath.read_text(encoding="utf-8")
    if search in content:
        content = content.replace(search, replace)
        filepath.write_text(content, encoding="utf-8")

def scaffold_project(name: str):
    print(f"Scaffolding new project '{name}'...")
    target_dir = Path(os.getcwd()) / name
    if target_dir.exists():
        print(f"Error: Directory '{name}' already exists.")
        return
    
    template_dir = get_templates_dir() / "project"
    if not template_dir.exists():
        print("Error: Project template not found.")
        return

    shutil.copytree(template_dir, target_dir)
    
    for root, _, files in os.walk(target_dir):
        for file in files:
            filepath = Path(root) / file
            replace_in_file(filepath, "{{PROJECT_NAME}}", name)
            
    print(f"Project '{name}' successfully created!")

def scaffold_module(name: str):
    print(f"Scaffolding new module '{name}'...")
    target_dir = Path(os.getcwd()) / name
    if target_dir.exists():
        print(f"Error: Module '{name}' already exists.")
        return
        
    template_dir = get_templates_dir() / "module"
    if not template_dir.exists():
        print("Error: Module template not found. Creating empty module...")
        target_dir.mkdir(parents=True)
        (target_dir / "__init__.py").write_text("")
        print(f"Module '{name}' successfully created!")
        return

    shutil.copytree(template_dir, target_dir)
    for root, _, files in os.walk(target_dir):
        for file in files:
            filepath = Path(root) / file
            replace_in_file(filepath, "{{MODULE_NAME}}", name)
    print(f"Module '{name}' successfully created!")

def scaffold_plugin(name: str):
    print(f"Scaffolding new plugin '{name}'...")
    target_dir = Path(os.getcwd()) / name
    if target_dir.exists():
        print(f"Error: Plugin '{name}' already exists.")
        return
        
    template_dir = get_templates_dir() / "plugin"
    if not template_dir.exists():
        print("Error: Plugin template not found.")
        target_dir.mkdir(parents=True)
        (target_dir / f"{name.lower()}.py").write_text(f'from lunawave_framework.core.plugins.base import BasePlugin\n\nclass {name}Plugin(BasePlugin):\n    pass\n')
        print(f"Plugin '{name}' successfully created!")
        return

    shutil.copytree(template_dir, target_dir)
    for root, _, files in os.walk(target_dir):
        for file in files:
            filepath = Path(root) / file
            replace_in_file(filepath, "{{PLUGIN_NAME}}", name)
            replace_in_file(filepath, "{{PLUGIN_LOWER}}", name.lower())
    print(f"Plugin '{name}' successfully created!")

def scaffold_adapter(name: str):
    print(f"Scaffolding new adapter '{name}'...")
    target_dir = Path(os.getcwd()) / name
    if target_dir.exists():
        print(f"Error: Adapter '{name}' already exists.")
        return
        
    template_dir = get_templates_dir() / "adapter"
    if not template_dir.exists():
        print("Error: Adapter template not found.")
        target_dir.mkdir(parents=True)
        (target_dir / f"{name.lower()}.py").write_text(f'class {name}Adapter:\n    pass\n')
        print(f"Adapter '{name}' successfully created!")
        return

    shutil.copytree(template_dir, target_dir)
    for root, _, files in os.walk(target_dir):
        for file in files:
            filepath = Path(root) / file
            replace_in_file(filepath, "{{ADAPTER_NAME}}", name)
            replace_in_file(filepath, "{{ADAPTER_LOWER}}", name.lower())
    print(f"Adapter '{name}' successfully created!")
