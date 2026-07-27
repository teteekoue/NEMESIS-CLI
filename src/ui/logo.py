from rich.text import Text

def get_eagle_logo():
    """Logo ASCII Aigle pour NEMESIS."""
    return r"""
                    ___
               ____/   \____
              /             \
             |  (o)     (o)  |
             |       <       |   N E M E S I S
             |    \_____/    |      C L I
             |  /         \  |
              \ \  _____  / /
               \_\|_____||/_/
                  |_____||
                  |_____||
                  |_____||
                  |_____||
                  |_____||
    """

def get_full_logo():
    return (
        "[bold #FF79C6] N[/bold #FF79C6]"
        "[bold #FF79C6] E[/bold #FF79C6]"
        "[bold #FF79C6] M[/bold #FF79C6]"
        "[bold #FF79C6] E[/bold #FF79C6]"
        "[bold #FF79C6] S[/bold #FF79C6]"
        "[bold #FF79C6] I[/bold #FF79C6]"
        "[bold #FF79C6] S[/bold #FF79C6]"
        "[bold #BD93F9] -[/bold #BD93F9]"
        "[bold #8BE9FD] C[/bold #8BE9FD]"
        "[bold #8BE9FD] L[/bold #8BE9FD]"
        "[bold #8BE9FD] I[/bold #8BE9FD]"
    )

def get_inline_logo():
    return Text("NEMESIS-CLI", style="bold #FF79C6")
