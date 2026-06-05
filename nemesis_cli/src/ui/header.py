from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from .theme import UIColors

# Écriture simple et ultra-lisible
NEMESIS_SIMPLE_LOGO = r"""
  _   _  ______  __  __  ______   _____  _____   _____ 
 | \ | ||  ____||  \/  ||  ____| / ____||_   _| / ____|
 |  \| || |__   | \  / || |__   | (___    | |  | (___  
 | . ` ||  __|  | |\/| ||  __|   \___ \   | |   \___ \ 
 | |\  || |____ | |  | || |____  ____) | _| |_  ____) |
 |_| \_||______||_|  |_||______||_____/ |_____||_____/ 
                                                       
           C  L  I      A  G  E  N  T
"""

def get_header(version="2.0.0"):
    logo_text = Text(NEMESIS_SIMPLE_LOGO, style="bold bright_cyan")
    
    tagline = Text("L'agent de codage à votre portée", style="italic white")
    ver = Text(f"Version {version}", style="dim")
    
    header_group = Group(
        Align.center(logo_text),
        Align.center(tagline),
        Align.center(ver)
    )
    
    return Panel(
        header_group,
        border_style="bright_blue",
        padding=(1, 2)
    )
