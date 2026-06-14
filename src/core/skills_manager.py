import os
import shutil
import subprocess
import requests
import zipfile
import io
import yaml
import re
from pathlib import Path
from rich.console import Console
from src.core.utils import get_resource_path

console = Console()

class SkillManager:
    def __init__(self, library_path="tools_library"):
        self.library_path = Path(library_path)