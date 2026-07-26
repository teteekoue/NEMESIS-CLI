TUI_CSS = """
Screen {
    background: #1a1b26;
    color: #c0caf5;
}

#app-grid {
    grid-size: 2;
    grid-columns: 1fr 260;
    grid-rows: 1fr auto;
    grid-gutter: 0;
}

#chat-area {
    background: #1a1b26;
    border: none;
}

#chat-scroll {
    background: #1a1b26;
}

#sidebar {
    background: #1f2030;
    border-left: solid #2a2b40;
    padding: 1;
    height: 100%;
    overflow-y: auto;
}

#input-bar {
    dock: bottom;
    height: auto;
    min-height: 3;
    max-height: 15;
    background: #1f2030;
    border-top: solid #2a2b40;
    padding: 0 1;
}

#input {
    background: #2a2b40;
    border: tall #414868;
    color: #c0caf5;
    padding: 0 1;
    min-height: 3;
}

#input:focus {
    border: tall #7aa2f7;
}

#input > .input--cursor {
    background: #7aa2f7;
    color: #1a1b26;
}

.msg-user {
    padding: 1;
    margin: 1 0;
}

.msg-user Prefix {
    color: #7dcfff;
    text-style: bold;
}

.msg-assistant {
    padding: 1;
    margin: 1 0;
}

.msg-assistant Prefix {
    color: #bb9af7;
    text-style: bold;
}

.msg-system {
    padding: 1 0;
    color: #565f89;
}

.msg-tool {
    padding: 0 1;
    color: #e0af68;
}

.msg-tool Prefix {
    color: #e0af68;
    text-style: bold;
}

.msg-tool-result {
    padding: 0 2;
    color: #73daca;
}

.msg-tool-result Prefix {
    color: #73daca;
    text-style: bold;
}

.msg-error {
    padding: 1;
    color: #f7768e;
}

.msg-error Prefix {
    color: #f7768e;
    text-style: bold;
}

StatusBar {
    background: #16161e;
    color: #565f89;
    height: 1;
    dock: bottom;
}

Sidebar Label {
    padding: 0 1;
}

#sidebar-title {
    text-style: bold;
    color: #bb9af7;
    padding: 1 1 0 1;
}

.sidebar-section {
    padding: 1 0 0 1;
    color: #7aa2f7;
    text-style: bold;
}

.sidebar-value {
    padding: 0 1;
    color: #565f89;
}

.sidebar-green {
    color: #9ece6a;
}

.sidebar-red {
    color: #f7768e;
}

.sidebar-yellow {
    color: #e0af68;
}

#welcome {
    padding: 2 1;
    text-align: center;
    color: #7aa2f7;
    text-style: bold;
}

#welcome-sub {
    text-align: center;
    color: #565f89;
    padding: 0 2 2 2;
}

.command-hint {
    color: #565f89;
    padding: 0 1;
}
"""
