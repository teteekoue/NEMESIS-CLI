from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PtStyle

class SlashCompleter(Completer):
    def __init__(self, commands=None):
        self.commands = commands or []

    def get_completions(self, document, complete_event):
        text = document.text
        if text.startswith('/'):
            query = text[1:].lower()
            for cmd in self.commands:
                if cmd.lower().startswith(query):
                    yield Completion(cmd, start_position=-len(query))

class NemesisInputHandler:
    def __init__(self, commands=None):
        self.commands = commands or []
        self.history = InMemoryHistory()
        self._cancelled = False
        self._exited = False

        kb = KeyBindings()
        @kb.add('c-c')
        def _(event):
            event.current_buffer.text = ""
            self._cancelled = True

        self.session = PromptSession(
            history=self.history,
            auto_suggest=AutoSuggestFromHistory(),
            completer=SlashCompleter(self.commands),
            complete_while_typing=False,
            key_bindings=kb,
            multiline=False,
            style=PtStyle.from_dict({
                'prompt': '#8BE9FD bold',
                'completion': 'bg:#44475A #F8F8F2',
                'completion-menu.completion.current': 'bg:#8BE9FD #282A36',
                'scrollbar.background': '#44475A',
                'scrollbar.button': '#BD93F9',
            }),
            enable_open_in_editor=False,
        )

    def get_input(self, prompt="❯ "):
        self._cancelled = False
        self._exited = False
        try:
            result = self.session.prompt(prompt)
            return result.strip() if result else ""
        except (KeyboardInterrupt, EOFError):
            self._cancelled = True
            return ""

    def set_commands(self, commands):
        self.commands = commands
        self.session.completer = SlashCompleter(commands)
