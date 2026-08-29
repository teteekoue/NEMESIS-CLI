# NEMESIS CLI — Tool Call Format

## Overview

NEMESIS CLI accepts **only** the JSON tool-call format. The parser is deliberately strict on the surface (JSON only) and extremely tolerant underneath (aggressive repair of common LLM mistakes).

No YAML, XML, or natural-language fallbacks are used.

## Canonical Format

```json
{
  "tool": "tool_name",
  "parameters": {
    "param1": "value1",
    "param2": "value2"
  }
}
```

The block should appear inside a markdown code fence (` ```json ` … ` ``` `). Bare `{…}` objects are also detected when they form a valid tool call.

### Accepted key aliases

| Role        | Accepted keys                          |
|-------------|----------------------------------------|
| Tool name   | `tool`, `name`, `action`               |
| Arguments   | `parameters`, `arguments`, `params`    |

### Tool name normalisation

- Hyphens are converted to underscores (`web-search` → `web_search`).
- Legacy names are mapped: `search_replace` / `replace` → `edit`, `write` → `write_file`, `read` → `read_file`, etc.

## Escaping Rules

Inside every JSON string value you must escape:

| Character     | Escape sequence |
|---------------|-----------------|
| `"`           | `\"`            |
| `\`           | `\\`            |
| newline       | `\n`            |
| tab           | `\t`            |
| carriage return | `\r`          |

Example with Python code containing a docstring:

```json
{
  "tool": "write_file",
  "parameters": {
    "file_path": "hello.py",
    "content": "def greet(name):\n    \"\"\"Return a greeting.\"\"\"\n    return f\"Hello, {name}!\\n\""
  }
}
```

## Parser Repair Capabilities

When the LLM produces imperfect JSON the parser will attempt, in order:

1. Escape real newlines / tabs / CRs that appear inside string literals.
2. Remove trailing commas before `}` or `]`.
3. Strip `//` and `/* */` comments.
4. Quote unquoted object keys.
5. Convert single-quoted strings that look like delimiters.
6. Close truncated braces / brackets.
7. Fix common invalid backslash escapes.

These repairs are applied progressively so that large payloads containing code, paths with backslashes, or multi-line content still parse successfully.

## Examples

### edit (formerly search_replace)

```json
{
  "tool": "edit",
  "parameters": {
    "file_path": "src/config.py",
    "old_string": "DEBUG = False",
    "new_string": "DEBUG = True"
  }
}
```

### bash

```json
{
  "tool": "bash",
  "parameters": {
    "command": "ls -la /tmp | head -5"
  }
}
```

### read_file

```json
{
  "tool": "read_file",
  "parameters": {
    "path": "README.md",
    "offset": 1,
    "limit": 50
  }
}
```

## What Is No Longer Supported

- YAML-style named fences (` ```edit\n…\n``` `)
- XML `<ACTION type="…">…</ACTION>`
- Natural-language fallbacks ("I will use bash to …")

All tool calls must be valid (or repairable) JSON.
