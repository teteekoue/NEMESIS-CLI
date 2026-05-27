from rich.console import Console
from rich.table import Table
from rich.text import Text
from src.core.commands import registry

from prompt_toolkit import Application
from prompt_toolkit.completion import Completer, Completion, WordCompleter
from prompt_toolkit.layout import Layout, FloatContainer, Float
from prompt_toolkit.widgets import Frame, TextArea
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style as PtStyle

class SlashCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text
        if text.startswith('/'):
            query = text[1:].lower()
            for cmd in registry.list_commands():
                if cmd.name.lower().startswith(query):
                    yield Completion(
                        cmd.name, 
                        start_position=-len(query),
                        display=HTML(f'<style fg="magenta">/{cmd.name}</style> <style fg="grey">{cmd.description}</style>')
                    )

class Composer:
    def __init__(self, console: Console):
        self.console = console
        
        self.pt_style = PtStyle.from_dict({
            'frame.border': '#555555',
            'prompt': 'bold #00ffff',
            'completion-menu.completion': 'bg:#333333 #ffffff',
            'completion-menu.completion.current': 'bg:#00ffff #000000',
            'completion-menu.border': '#00ffff',
        })
        
        self.input_area = TextArea(
            prompt=' > ',
            multiline=False,
            wrap_lines=False,
            completer=SlashCompleter(),
            complete_while_typing=True
        )
        
        self.frame = Frame(
            self.input_area,
            title="Entrée de Commande",
        )
        
        # Le container flottant pour le menu de complétion
        self.root_container = FloatContainer(
            self.frame,
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=CompletionsMenu(max_height=10),
                )
            ],
        )
        
        # Key bindings pour quitter/soumettre
        self.kb = KeyBindings()
        @self.kb.add('c-c')
        def _(event): event.app.exit(result=None)
        @self.kb.add('enter')
        def _(event): event.app.exit(result=self.input_area.text)

        self.app = Application(
            layout=Layout(self.root_container),
            key_bindings=self.kb,
            full_screen=False,
            mouse_support=True
        )

    def display_help_overlay(self):
        table = Table(box=None, show_header=False, padding=(0, 3))
        for cmd in registry.list_commands():
            table.add_row(
                Text(f"/{cmd.name}", style="bold magenta"),
                Text(cmd.description, style="italic grey70")
            )
        self.console.print(table)

    def get_input(self) -> str:
        self.input_area.text = ""
        result = self.app.run()
        return result.strip() if result else ""
