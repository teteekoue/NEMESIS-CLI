from typing import Dict, List, Callable, Optional
import sys
import os
import yaml
import time
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from src.core.commands import registry
from src.core.skills_manager import SkillManager