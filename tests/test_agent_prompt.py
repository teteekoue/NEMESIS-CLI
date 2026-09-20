from agent import NemesisApp


class _FakeConsole:
    def print(self, *_args, **_kwargs):
        pass


class _FakeComposer:
    def __init__(self, choices):
        self.choices = iter(choices)

    def prompt_input(self, **_kwargs):
        return next(self.choices)


def _app_with_choices(*choices):
    app = NemesisApp.__new__(NemesisApp)
    app.console = _FakeConsole()
    app.composer = _FakeComposer(choices)
    app._send_system_prompt = False
    app._prompt_sent = False
    return app


def test_system_prompt_is_disabled_by_default():
    app = _app_with_choices("")

    app._ask_system_prompt()

    assert app._send_system_prompt is False
    assert app._prompt_sent is True


def test_system_prompt_can_be_enabled():
    app = _app_with_choices("o")

    app._ask_system_prompt()

    assert app._send_system_prompt is True
    assert app._prompt_sent is False
