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
=======
from src.core.utils import get_resource_path
>>>>>>> 5380d9a25d4e84c58e2a84c467fbc6e2b0173307

console = Console()

class SkillManager:
    def __init__(self, library_path="tools_library"):
<<<<<<< HEAD
        self.library_path = Path(library_path)