"""
Answer overlay — streaming-first, no auto-scroll.

Streaming strategy
──────────────────
DURING streaming : insertPlainText(token)        O(1) per token, instant
ON finish        : setHtml(md_to_html(...))       O(n), called once only

Auto-scroll REMOVED — user controls scroll position freely at all times.
"""

import sys
import os
import re
import html as html_module

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QTextEdit, QApplication, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QFont, QTextCursor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils import window_hide
    _HAS_WINDOW_HIDE = True
except ImportError:
    _HAS_WINDOW_HIDE = False

try:
    from settings import config
except ImportError:
    config = {}


# ── Theme palettes ─────────────────────────────────────────────────────────────

DARK = {
    "window_bg":        "#0a0a0d",
    "header_bg":        "#0e0e12",
    "header_border":    "#1a1a20",
    "text":             "#dcdcdc",
    "subtext":          "#666680",
    "accent":           "#4f8ef7",
    "accent_dim":       "#161e36",
    "error":            "#e05252",
    "sep":              "#16161c",
    "code_bg":          "#0f0f13",
    "code_border":      "#222228",
    "code_text":        "#abb2bf",
    "code_lang":        "#44445a",
    "inline_code_bg":   "#18181e",
    "inline_code_fg":   "#e06c75",
    "scrollbar":        "rgba(255,255,255,0.06)",
    "scrollbar_h":      "rgba(255,255,255,0.14)",
    "nav_bg":           "#16161c",
    "nav_border":       "#22222a",
    "nav_disabled":     "#2a2a32",
    "question_bg":      "#0b1220",
    "question_border":  "#162040",
    "question_text":    "#6a9fe0",
    "table_bg":         "#0e0e12",
    "table_header_bg":  "#131318",
    "table_border":     "#1e1e26",
    "table_text":       "#dcdcdc",
    "table_header_text":"#4f8ef7",
    "syn_keyword":      "#c678dd",
    "syn_builtin":      "#e5c07b",
    "syn_string":       "#98c379",
    "syn_comment":      "#4a4a5e",
    "syn_number":       "#d19a66",
    "syn_function":     "#61afef",
    "syn_decorator":    "#e06c75",
    "syn_type":         "#56b6c2",
    "syn_operator":     "#56b6c2",
}

LIGHT = {
    "window_bg":        "#f6f6f9",
    "header_bg":        "#ededf2",
    "header_border":    "#d8d8e0",
    "text":             "#18182a",
    "subtext":          "#70708a",
    "accent":           "#2563eb",
    "accent_dim":       "#dbeafe",
    "error":            "#dc2626",
    "sep":              "#e0e0ea",
    "code_bg":          "#ededf2",
    "code_border":      "#d4d4de",
    "code_text":        "#1e293b",
    "code_lang":        "#707088",
    "inline_code_bg":   "#e6e6ee",
    "inline_code_fg":   "#c0392b",
    "scrollbar":        "rgba(0,0,0,0.08)",
    "scrollbar_h":      "rgba(0,0,0,0.18)",
    "nav_bg":           "#e8e8f0",
    "nav_border":       "#ccccda",
    "nav_disabled":     "#c0c0cc",
    "question_bg":      "#eff6ff",
    "question_border":  "#bfdbfe",
    "question_text":    "#1d4ed8",
    "table_bg":         "#ffffff",
    "table_header_bg":  "#f0f0f8",
    "table_border":     "#d0d0de",
    "table_text":       "#18182a",
    "table_header_text":"#2563eb",
    "syn_keyword":      "#7c3aed",
    "syn_builtin":      "#b45309",
    "syn_string":       "#15803d",
    "syn_comment":      "#6b7280",
    "syn_number":       "#c2410c",
    "syn_function":     "#1d4ed8",
    "syn_decorator":    "#dc2626",
    "syn_type":         "#0369a1",
    "syn_operator":     "#0369a1",
}


# ── Stylesheet ─────────────────────────────────────────────────────────────────

def _stylesheet(t: dict) -> str:
    return f"""
QWidget#overlay_root {{
    background: {t['window_bg']};
    border-radius: 16px;
    border: 1px solid {t['sep']};
}}
QWidget#header_bar {{
    background: {t['header_bg']};
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    border-bottom: 1px solid {t['header_border']};
}}
QTextEdit#question_view {{
    background: {t['question_bg']};
    border: none;
    border-bottom: 1px solid {t['question_border']};
    color: {t['question_text']};
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 12px;
    padding: 5px 16px;
    selection-background-color: {t['accent_dim']};
}}
QTextEdit#question_view QScrollBar:vertical {{
    background: transparent;
    width: 4px;
}}
QTextEdit#question_view QScrollBar::handle:vertical {{
    background: {t['scrollbar']};
    border-radius: 2px;
    min-height: 16px;
}}
QTextEdit#question_view QScrollBar::add-line:vertical,
QTextEdit#question_view QScrollBar::sub-line:vertical {{ height: 0; }}
QTextEdit#answer_view {{
    background: {t['window_bg']};
    border: none;
    color: {t['text']};
    font-family: 'Segoe UI', 'Inter', 'Helvetica Neue', sans-serif;
    font-size: 13px;
    selection-background-color: {t['accent_dim']};
    selection-color: {t['text']};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 4px 2px;
}}
QScrollBar::handle:vertical {{
    background: {t['scrollbar']};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t['scrollbar_h']};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical  {{ height: 0; background: none; }}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical  {{ background: none; }}
QScrollBar:horizontal           {{ height: 0; background: transparent; }}
QFrame#sep_line {{
    background: {t['sep']};
    max-height: 1px;
    min-height: 1px;
}}
QPushButton#hdr_btn {{
    background: transparent;
    border: none;
    color: {t['subtext']};
    font-size: 14px;
    border-radius: 6px;
    padding: 2px 6px;
    min-width: 26px;
    min-height: 26px;
}}
QPushButton#hdr_btn:hover {{
    color: {t['accent']};
    background: rgba(127,127,127,0.10);
}}
QPushButton#hdr_btn:pressed {{
    background: rgba(127,127,127,0.18);
}}
QPushButton#nav_btn {{
    background: {t['nav_bg']};
    border: 1px solid {t['nav_border']};
    color: {t['text']};
    font-size: 15px;
    font-weight: bold;
    border-radius: 6px;
    min-width: 28px;
    min-height: 26px;
    padding: 0 6px;
}}
QPushButton#nav_btn:hover {{
    border-color: {t['accent']};
    color: {t['accent']};
}}
QPushButton#nav_btn:disabled {{
    color: {t['nav_disabled']};
    border-color: {t['nav_disabled']};
    background: transparent;
}}
QLabel#lbl_history {{
    color: {t['subtext']};
    font-size: 10px;
    font-family: 'Segoe UI', sans-serif;
    min-width: 64px;
}}
QLabel#lbl_status {{
    color: {t['accent']};
    font-size: 10px;
    font-family: 'Segoe UI', sans-serif;
}}
QLabel#lbl_title {{
    color: {t['subtext']};
    font-size: 9px;
    font-family: 'Segoe UI', sans-serif;
    letter-spacing: 1.8px;
    font-weight: 700;
}}
"""


# ── Syntax highlighter ─────────────────────────────────────────────────────────
# (identical logic, kept in full for drop-in replacement)

_KEYWORDS = {
    "python": {
        "keywords": {
            "def", "class", "if", "elif", "else", "for", "while", "return",
            "import", "from", "as", "with", "try", "except", "finally",
            "raise", "pass", "break", "continue", "lambda", "yield",
            "async", "await", "not", "and", "or", "in", "is", "del",
            "global", "nonlocal", "assert",
        },
        "builtins": {
            "print", "len", "range", "enumerate", "zip", "map", "filter",
            "sorted", "reversed", "list", "dict", "set", "tuple", "str",
            "int", "float", "bool", "type", "isinstance", "hasattr",
            "getattr", "setattr", "open", "super", "self", "cls",
            "True", "False", "None",
        },
        "types": {
            "int", "str", "bool", "float", "list", "dict", "tuple", "set",
            "bytes", "complex", "frozenset", "object", "type", "None",
            "Any", "Optional", "Union", "List", "Dict", "Tuple", "Set",
        },
    },
    "javascript": {
        "keywords": {
            "const", "let", "var", "function", "class", "if", "else",
            "for", "while", "return", "import", "export", "default",
            "from", "as", "try", "catch", "finally", "throw", "new",
            "delete", "typeof", "instanceof", "in", "of", "async",
            "await", "yield", "break", "continue", "switch", "case",
        },
        "builtins": {
            "console", "window", "document", "Array", "Object", "String",
            "Number", "Boolean", "Math", "JSON", "Promise", "Error",
            "Map", "Set", "undefined", "null", "true", "false",
            "this", "super",
        },
        "types": {
            "number", "string", "boolean", "object", "any", "void",
            "never", "unknown", "undefined", "null",
        },
    },
    "typescript": {
        "keywords": {
            "const", "let", "var", "function", "class", "if", "else",
            "for", "while", "return", "import", "export", "default",
            "from", "as", "try", "catch", "finally", "throw", "new",
            "delete", "typeof", "instanceof", "in", "of", "async",
            "await", "yield", "break", "continue", "switch", "case",
            "interface", "type", "enum", "namespace", "declare",
            "abstract", "implements", "extends", "readonly",
            "private", "public", "protected", "static",
        },
        "builtins": {
            "console", "Array", "Object", "String", "Number", "Boolean",
            "Promise", "Error", "Map", "Set", "undefined", "null",
            "true", "false", "this", "super",
        },
        "types": {
            "number", "string", "boolean", "object", "any", "void",
            "never", "unknown", "undefined", "null",
        },
    },
}
_KEYWORDS["js"] = _KEYWORDS["javascript"]
_KEYWORDS["ts"] = _KEYWORDS["typescript"]

_GENERIC_KEYWORDS = {
    "keywords": {
        "def", "class", "if", "else", "elif", "for", "while", "return",
        "import", "from", "as", "with", "try", "except", "finally",
        "function", "const", "let", "var", "export", "default", "new",
        "throw", "catch", "async", "await", "yield", "break", "continue",
        "switch", "case", "interface", "enum", "type", "struct", "fn",
        "pub", "mod", "use", "impl", "trait", "match", "in", "and", "or",
    },
    "builtins": {
        "true", "false", "null", "None", "True", "False", "undefined",
        "self", "this", "super", "print", "len", "range", "console",
    },
    "types": {
        "int", "str", "bool", "float", "list", "dict", "tuple", "set",
        "void", "any", "string", "number", "boolean", "object",
    },
}


def _apply_syntax_highlighting(code: str, lang: str, t: dict) -> str:
    lang      = lang.lower().strip()
    lang_keys = _KEYWORDS.get(lang, _GENERIC_KEYWORDS)
    kw  = lang_keys.get("keywords", set())
    bi  = lang_keys.get("builtins", set())
    typ = lang_keys.get("types",    set())

    result = []
    i = 0
    n = len(code)

    while i < n:
        if code[i] == "&":
            end = code.find(";", i)
            if end != -1 and end - i <= 10:
                result.append(code[i:end+1])
                i = end + 1
                continue

        if code[i] == "#":
            end = code.find("\n", i)
            end = n if end == -1 else end
            result.append(
                f'<span style="color:{t["syn_comment"]};font-style:italic;">'
                f'{code[i:end]}</span>'
            )
            i = end
            continue

        if i + 1 < n and code[i:i+2] == "//":
            end = code.find("\n", i)
            end = n if end == -1 else end
            result.append(
                f'<span style="color:{t["syn_comment"]};font-style:italic;">'
                f'{code[i:end]}</span>'
            )
            i = end
            continue

        if i + 1 < n and code[i:i+2] == "/*":
            end = code.find("*/", i + 2)
            end = n if end == -1 else end + 2
            result.append(
                f'<span style="color:{t["syn_comment"]};font-style:italic;">'
                f'{code[i:end]}</span>'
            )
            i = end
            continue

        if code[i] == '"' or code[i:i+6] == "&quot;":
            is_entity = code[i:i+6] == "&quot;"
            qi        = i + (6 if is_entity else 1)
            buf       = ("&quot;" if is_entity else '"')
            escaped   = False
            while qi < n:
                ch = code[qi]
                if ch == "\\":
                    escaped = not escaped
                    buf += ch
                    qi += 1
                    continue
                if not escaped:
                    if is_entity and code[qi:qi+6] == "&quot;":
                        buf += "&quot;"
                        qi += 6
                        break
                    elif not is_entity and ch == '"':
                        buf += ch
                        qi += 1
                        break
                buf += ch
                escaped = False
                qi += 1
            result.append(f'<span style="color:{t["syn_string"]};">{buf}</span>')
            i = qi
            continue

        if code[i] == "'":
            qi = i + 1
            buf = "'"
            escaped = False
            while qi < n:
                ch = code[qi]
                if ch == "\\" and not escaped:
                    escaped = True
                    buf += ch
                    qi += 1
                    continue
                buf += ch
                escaped = False
                qi += 1
                if ch == "'":
                    break
            result.append(f'<span style="color:{t["syn_string"]};">{buf}</span>')
            i = qi
            continue

        if code[i] == "`":
            qi = i + 1
            buf = "`"
            while qi < n:
                ch = code[qi]
                buf += ch
                qi += 1
                if ch == "`":
                    break
            result.append(f'<span style="color:{t["syn_string"]};">{buf}</span>')
            i = qi
            continue

        if code[i] == "@":
            qi = i + 1
            buf = "@"
            while qi < n and (code[qi].isalnum() or code[qi] == "_"):
                buf += code[qi]
                qi += 1
            result.append(
                f'<span style="color:{t["syn_decorator"]};">{buf}</span>'
            )
            i = qi
            continue

        if code[i].isdigit() or (
            code[i] == "." and i + 1 < n and code[i+1].isdigit()
        ):
            qi  = i
            buf = ""
            while qi < n and (
                code[qi].isdigit()
                or code[qi] in ".xXoObBaAcCdDeEfFlLuU_"
            ):
                buf += code[qi]
                qi += 1
            result.append(
                f'<span style="color:{t["syn_number"]};">{buf}</span>'
            )
            i = qi
            continue

        if code[i].isalpha() or code[i] == "_":
            qi = i
            while qi < n and (code[qi].isalnum() or code[qi] == "_"):
                qi += 1
            word = code[i:qi]
            if word in kw:
                result.append(
                    f'<span style="color:{t["syn_keyword"]};font-weight:600;">'
                    f'{word}</span>'
                )
            elif word in typ:
                result.append(
                    f'<span style="color:{t["syn_type"]};">{word}</span>'
                )
            elif word in bi:
                result.append(
                    f'<span style="color:{t["syn_builtin"]};">{word}</span>'
                )
            elif code[qi:qi+1] == "(":
                result.append(
                    f'<span style="color:{t["syn_function"]};">{word}</span>'
                )
            else:
                result.append(word)
            i = qi
            continue

        if code[i] in "+-*/%=<>!&|^~?:":
            result.append(
                f'<span style="color:{t["syn_operator"]};">{code[i]}</span>'
            )
            i += 1
            continue

        result.append(code[i])
        i += 1

    return "".join(result)


# ── Markdown → HTML ────────────────────────────────────────────────────────────

def _escape_html(text: str) -> str:
    return html_module.escape(text)


def _inline_format(safe: str, t: dict) -> str:
    safe = re.sub(
        r"`([^`\n]+)`",
        lambda m: (
            f'<code style="background:{t["inline_code_bg"]};'
            f'color:{t["inline_code_fg"]};border-radius:3px;'
            f'padding:1px 5px 2px;font-family:Consolas,monospace;'
            f'font-size:12px;font-weight:500;">'
            f'{_escape_html(m.group(1))}</code>'
        ),
        safe,
    )
    safe = re.sub(r"\*\*\*(.+?)\*\*\*",
                  f'<b><i style="color:{t["text"]};">\\1</i></b>', safe)
    safe = re.sub(r"\*\*(.+?)\*\*",
                  f'<b style="color:{t["text"]};">\\1</b>', safe)
    safe = re.sub(r"\*(.+?)\*",
                  f'<i style="color:{t["subtext"]};">\\1</i>', safe)
    safe = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        f'<a href="\\2" style="color:{t["accent"]}; '
        f'text-decoration:underline;">\\1</a>',
        safe,
    )
    return safe


def _render_table(rows: list, t: dict) -> str:
    if not rows:
        return ""
    parts = [
        f'<div style="margin:10px 0;overflow-x:auto;">',
        f'<table style="border-collapse:collapse;width:100%;'
        f'border:1px solid {t["table_border"]};'
        f'border-radius:8px;overflow:hidden;">',
    ]
    for ri, row in enumerate(rows):
        is_hdr = ri == 0
        bg = t["table_header_bg"] if is_hdr else (
            t["table_bg"] if ri % 2 == 0 else t["window_bg"]
        )
        parts.append(f'<tr style="background:{bg};">')
        tag = "th" if is_hdr else "td"
        for cell in row:
            cc    = _inline_format(_escape_html(cell.strip()), t)
            color = t["table_header_text"] if is_hdr else t["table_text"]
            fw    = "font-weight:600;" if is_hdr else ""
            parts.append(
                f'<{tag} style="padding:6px 12px;'
                f'border:1px solid {t["table_border"]};'
                f'font-size:12px;color:{color};{fw}'
                f'font-family:Segoe UI,sans-serif;text-align:left;">'
                f'{cc}</{tag}>'
            )
        parts.append("</tr>")
    parts.extend(["</table>", "</div>"])
    return "".join(parts)


def md_to_html(md: str, t: dict) -> str:
    if not md:
        return ""

    lines = md.split("\n")
    out   = []

    in_code       = False
    code_lang     = ""
    code_buf: list[str] = []
    in_list_ul    = False
    in_list_ol    = False
    list_items:   list[str] = []
    list_style    = ""
    in_blockquote = False
    bq_buf:       list[str] = []
    in_table      = False
    table_rows:   list[list[str]] = []

    def _flush_list():
        nonlocal in_list_ul, in_list_ol, list_items, list_style
        if not list_items:
            return
        items_html = ""
        for item in list_items:
            items_html += (
                f'<div style="display:flex;align-items:baseline;'
                f'margin:2px 0;gap:8px;color:{t["text"]};">'
                f'<span style="color:{t["accent"]};min-width:12px;'
                f'font-size:12px;"></span>'
                f'<span style="line-height:1.65;font-size:13px;'
                f'font-family:Segoe UI,sans-serif;">{item}</span>'
                f'</div>'
            )
        out.append(f'<div style="margin:6px 0 6px 8px;">{items_html}</div>')
        list_items[:] = []
        in_list_ul = False
        in_list_ol = False
        list_style = ""

    def _flush_blockquote():
        nonlocal in_blockquote, bq_buf
        if not bq_buf:
            return
        content = "<br>".join(bq_buf)
        out.append(
            f'<div style="border-left:2px solid {t["accent"]};margin:8px 0;'
            f'padding:6px 14px;background:{t["accent_dim"]};'
            f'border-radius:0 6px 6px 0;">'
            f'<span style="color:{t["subtext"]};font-style:italic;'
            f'font-size:13px;line-height:1.65;">{content}</span></div>'
        )
        bq_buf[:] = []
        in_blockquote = False

    def _flush_table():
        nonlocal in_table, table_rows
        if table_rows:
            out.append(_render_table(table_rows, t))
        table_rows[:] = []
        in_table = False

    def _is_sep(line: str) -> bool:
        s = line.strip()
        return bool(s.startswith("|") and re.match(r"^\|[\s\-:\|]+\|$", s))

    def _parse_row(line: str) -> list[str]:
        s = line.strip().strip("|")
        return [c.strip() for c in s.split("|")]

    i = 0
    while i < len(lines):
        line     = lines[i]
        stripped = line.strip()

        # ── Fenced code block ──────────────────────────────────────────────────
        if stripped.startswith("```"):
            if not in_code:
                _flush_list(); _flush_blockquote(); _flush_table()
                in_code   = True
                code_lang = stripped[3:].strip()
                code_buf  = []
            else:
                in_code = False
                raw     = "\n".join(code_buf)
                escaped = _escape_html(raw)
                hi      = _apply_syntax_highlighting(escaped, code_lang, t)
                lang_disp = code_lang.upper() if code_lang else "CODE"
                out.append(
                    f'<div style="margin:10px 0;border-radius:10px;'
                    f'border:1px solid {t["code_border"]};overflow:hidden;">'
                    # header bar
                    f'<div style="background:{t["code_border"]};'
                    f'padding:5px 14px;display:flex;align-items:center;'
                    f'justify-content:space-between;">'
                    f'<span style="color:{t["code_lang"]};font-size:10px;'
                    f'font-family:Consolas,monospace;letter-spacing:1px;'
                    f'font-weight:700;">{lang_disp}</span>'
                    f'<span style="color:{t["code_lang"]};font-size:10px;">'
                    f'{len(code_buf)} lines</span></div>'
                    # code body
                    f'<div style="background:{t["code_bg"]};'
                    f'padding:12px 16px;overflow-x:auto;">'
                    f'<pre style="margin:0;padding:0;white-space:pre;'
                    f'font-family:Consolas,\'Courier New\',monospace;'
                    f'font-size:12.5px;color:{t["code_text"]};'
                    f'line-height:1.65;tab-size:4;">{hi}</pre>'
                    f'</div></div>'
                )
                code_lang = ""
                code_buf  = []
            i += 1
            continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # ── Table ──────────────────────────────────────────────────────────────
        if stripped.startswith("|"):
            if _is_sep(stripped):
                in_table = True
                i += 1
                continue
            row = _parse_row(stripped)
            if row:
                table_rows.append(row)
                in_table = True
                i += 1
                continue
        elif in_table:
            _flush_table()

        # ── Blockquote ─────────────────────────────────────────────────────────
        if stripped.startswith("> "):
            _flush_list(); _flush_table()
            bq_buf.append(_inline_format(_escape_html(stripped[2:]), t))
            in_blockquote = True
            i += 1
            continue
        elif in_blockquote:
            _flush_blockquote()

        # ── Blank line ─────────────────────────────────────────────────────────
        if not stripped:
            _flush_list(); _flush_blockquote(); _flush_table()
            out.append('<div style="height:5px;"></div>')
            i += 1
            continue

        # ── HR ─────────────────────────────────────────────────────────────────
        if stripped in ("---", "___", "***") or re.match(r"^-{3,}$", stripped):
            _flush_list()
            out.append(
                f'<div style="height:1px;background:{t["sep"]};'
                f'margin:12px 0;border-radius:1px;"></div>'
            )
            i += 1
            continue

        # ── Headings ───────────────────────────────────────────────────────────
        hm = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if hm:
            _flush_list(); _flush_table()
            level = len(hm.group(1))
            text  = _inline_format(_escape_html(hm.group(2)), t)
            sizes  = {1:"18px", 2:"16px", 3:"14px", 4:"13px", 5:"13px", 6:"12px"}
            weight = {1:"800",  2:"700",  3:"650",  4:"600",  5:"600",  6:"600"}
            top_m  = {1:"16px", 2:"14px", 3:"10px", 4:"8px",  5:"8px",  6:"8px"}
            out.append(
                f'<div style="color:{t["accent"]};font-size:{sizes[level]};'
                f'font-weight:{weight[level]};margin:{top_m[level]} 0 4px;'
                f'font-family:Segoe UI,sans-serif;">{text}</div>'
            )
            if level <= 2:
                op = "0.35" if level == 1 else "0.18"
                out.append(
                    f'<div style="height:{2 if level==1 else 1}px;'
                    f'background:{t["accent"]};opacity:{op};'
                    f'margin-bottom:8px;border-radius:1px;"></div>'
                )
            i += 1
            continue

        # ── Unordered list ─────────────────────────────────────────────────────
        ul = re.match(r"^(\s*)[-*+]\s+(.+)$", line)
        if ul:
            _flush_blockquote(); _flush_table()
            if list_style and list_style != "ul":
                _flush_list()
            list_style = "ul"
            in_list_ul = True
            content    = _inline_format(_escape_html(ul.group(2)), t)
            indent     = len(ul.group(1))
            bc         = t["accent"] if indent == 0 else t["subtext"]
            list_items.append(
                f'<span style="padding-left:{indent*12}px;">'
                f'<span style="color:{bc};">•</span> {content}</span>'
            )
            i += 1
            continue

        # ── Ordered list ───────────────────────────────────────────────────────
        ol = re.match(r"^(\s*)(\d+)\.\s+(.+)$", line)
        if ol:
            _flush_blockquote(); _flush_table()
            if list_style and list_style != "ol":
                _flush_list()
            list_style = "ol"
            in_list_ol = True
            content    = _inline_format(_escape_html(ol.group(3)), t)
            indent     = len(ol.group(1))
            list_items.append(
                f'<span style="padding-left:{indent*12}px;">'
                f'<span style="color:{t["accent"]};font-weight:600;">'
                f'{ol.group(2)}.</span> {content}</span>'
            )
            i += 1
            continue

        if in_list_ul or in_list_ol:
            _flush_list()

        # ── Normal paragraph ───────────────────────────────────────────────────
        safe_line = _inline_format(_escape_html(stripped), t)
        out.append(
            f'<div style="margin:3px 0;line-height:1.7;color:{t["text"]};'
            f'font-family:Segoe UI,sans-serif;font-size:13px;">'
            f'{safe_line}</div>'
        )
        i += 1

    _flush_list()
    _flush_blockquote()
    _flush_table()

    return (
        f'<div style="padding:12px 18px 16px;'
        f'font-family:Segoe UI,sans-serif;'
        f'color:{t["text"]};background:{t["window_bg"]};">'
        f'{"".join(out)}'
        f'</div>'
    )


# ── Answer Overlay ─────────────────────────────────────────────────────────────

class AnswerOverlay(QWidget):
    """
    Streaming: insertPlainText(token) O(1) during stream.
               setHtml(md_to_html())  O(n) once on finish.

    Auto-scroll: REMOVED — user scrolls freely at all times.
    """

    MAX_HEIGHT  = 475
    MAX_WIDTH   = 700
    MIN_WIDTH   = 560
    HEADER_H    = 44
    QUESTION_H  = 56
    MIN_VIEW_H  = 140

    def __init__(self, parent=None):
        super().__init__(parent)

        self._dark_mode        = True
        self._history: list[tuple[str, str, str]] = []
        self._history_index    = -1
        self._streaming        = False
        self._current_md       = ""
        self._current_question = ""
        self._drag_pos: QPoint | None = None

        raw_opacity   = (
            config.get("opacity", 0.96) if isinstance(config, dict) else 0.96
        )
        self._opacity = max(0.2, min(1.0, float(raw_opacity)))

        # Re-render timer for theme changes only
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(60)
        self._render_timer.timeout.connect(self._do_render)

        # Debounced live markdown render during streaming (every 300 ms)
        self._stream_render_timer = QTimer(self)
        self._stream_render_timer.setInterval(300)
        self._stream_render_timer.timeout.connect(self._do_stream_render)

        self._build_ui()
        self._apply_theme()
        self.setWindowOpacity(self._opacity)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setMinimumHeight(160)   # ← prevents UpdateLayeredWindowIndirect negative-rect crash
        self.setMaximumWidth(self.MAX_WIDTH)
        self.setMaximumHeight(self.MAX_HEIGHT)
        self.setFont(QFont("Segoe UI", 12))
        self.resize(640, self.MAX_HEIGHT)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)

        self._root = QWidget()
        self._root.setObjectName("overlay_root")
        outer.addWidget(self._root)

        root_vbox = QVBoxLayout(self._root)
        root_vbox.setContentsMargins(0, 0, 0, 0)
        root_vbox.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────────────
        self._header = QWidget()
        self._header.setObjectName("header_bar")
        self._header.setFixedHeight(self.HEADER_H)

        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(14, 0, 8, 0)
        hl.setSpacing(3)

        lbl_title = QLabel("GLASSNOTE")
        lbl_title.setObjectName("lbl_title")
        hl.addWidget(lbl_title)
        hl.addSpacing(6)

        self._btn_prev = QPushButton("‹")
        self._btn_prev.setObjectName("nav_btn")
        self._btn_prev.setToolTip("Previous answer  (Ctrl+Shift+[)")
        self._btn_prev.setEnabled(False)
        self._btn_prev.clicked.connect(self._go_prev)
        hl.addWidget(self._btn_prev)

        self._lbl_history = QLabel("No history")
        self._lbl_history.setObjectName("lbl_history")
        self._lbl_history.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_history.setMinimumWidth(72)
        hl.addWidget(self._lbl_history)

        self._btn_next = QPushButton("›")
        self._btn_next.setObjectName("nav_btn")
        self._btn_next.setToolTip("Next answer  (Ctrl+Shift+])")
        self._btn_next.setEnabled(False)
        self._btn_next.clicked.connect(self._go_next)
        hl.addWidget(self._btn_next)

        hl.addStretch(1)

        self._lbl_status = QLabel("")
        self._lbl_status.setObjectName("lbl_status")
        hl.addWidget(self._lbl_status)
        hl.addSpacing(4)

        for icon, tip, slot in [
            ("⎘", "Copy answer",        self._copy_answer),
            ("☀", "Toggle light / dark", self._toggle_theme),
            ("—", "Hide overlay",        self.hide),
        ]:
            btn = QPushButton(icon)
            btn.setObjectName("hdr_btn")
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            hl.addWidget(btn)
            if icon == "☀":
                self._btn_theme = btn

        root_vbox.addWidget(self._header)

        # ── Question bar ───────────────────────────────────────────────────────
        self._question_view = QTextEdit()
        self._question_view.setObjectName("question_view")
        self._question_view.setReadOnly(True)
        self._question_view.setFixedHeight(self.QUESTION_H)
        self._question_view.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._question_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._question_view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._question_view.document().setDocumentMargin(0)
        self._question_view.setVisible(False)
        root_vbox.addWidget(self._question_view)

        # ── Separator ──────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setObjectName("sep_line")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        root_vbox.addWidget(sep)

        # ── Answer view ────────────────────────────────────────────────────────
        self._answer_view = QTextEdit()
        self._answer_view.setObjectName("answer_view")
        self._answer_view.setReadOnly(True)
        self._answer_view.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._answer_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._answer_view.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._answer_view.document().setDocumentMargin(0)
        self._answer_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root_vbox.addWidget(self._answer_view)
        self._answer_view.setFixedHeight(self._calc_view_height())

    # ── Height math ────────────────────────────────────────────────────────────

    def _calc_view_height(self, question_visible: bool = False) -> int:
        q_h   = self.QUESTION_H if question_visible else 0
        taken = 16 + self.HEADER_H + 1 + q_h
        return max(self.MIN_VIEW_H, self.MAX_HEIGHT - taken)

    # ── Question bar ───────────────────────────────────────────────────────────

    def show_question(self, question: str):
        if not question:
            self._question_view.setVisible(False)
            self._answer_view.setFixedHeight(self._calc_view_height(False))
            return

        t       = self._theme()
        display = question.strip().strip('"')
        safe    = _escape_html(display)

        self._question_view.setHtml(
            f'<div style="padding:5px 16px;">'
            f'<span style="color:{t["subtext"]};font-size:10px;'
            f'font-weight:700;letter-spacing:0.8px;">Q &nbsp;</span>'
            f'<span style="color:{t["question_text"]};font-size:12px;'
            f'font-family:\'Segoe UI\',sans-serif;line-height:1.5;">'
            f'{safe}</span></div>'
        )
        self._question_view.verticalScrollBar().setValue(0)
        self._question_view.setVisible(True)
        self._current_question = question
        self._answer_view.setFixedHeight(self._calc_view_height(True))

    def hide_question(self):
        self._question_view.setVisible(False)
        self._answer_view.setFixedHeight(self._calc_view_height(False))

    # ── Theme ──────────────────────────────────────────────────────────────────

    def _theme(self) -> dict:
        return DARK if self._dark_mode else LIGHT

    def _apply_theme(self):
        self.setStyleSheet(_stylesheet(self._theme()))
        self._btn_theme.setText("☀" if self._dark_mode else "☾")
        if not self._streaming and self._current_md:
            self._do_render()
        if self._current_question:
            self.show_question(self._current_question)

    def _toggle_theme(self):
        self._dark_mode = not self._dark_mode
        self._apply_theme()

    def set_opacity(self, value: float):
        self._opacity = max(0.2, min(1.0, float(value)))
        self.setWindowOpacity(self._opacity)

    # ── Rendering ──────────────────────────────────────────────────────────────

    def _do_render(self):
        """
        Full markdown render.
        Called ONCE on finish_stream(), or on theme change / history nav.
        Never called mid-stream.
        """
        if not self._current_md:
            self._answer_view.setHtml("")
            return
        self._answer_view.setHtml(
            md_to_html(self._current_md, self._theme())
        )
        # No auto-scroll — user position is preserved

    # ── Streaming API ──────────────────────────────────────────────────────────

    def start_stream(self, label: str = "", question: str = ""):
        """Called immediately before the first token arrives."""
        self._streaming  = True
        self._current_md = ""
        self._render_timer.stop()
        self._stream_render_timer.stop()
        self._lbl_status.setText("⏳  Thinking…")

        if question:
            self.show_question(question)
        else:
            self.hide_question()

        t = self._theme()
        self._answer_view.setHtml(
            f'<div style="padding:20px 18px;color:{t["subtext"]};'
            f'font-family:Segoe UI,sans-serif;font-size:13px;">'
            f'<span style="color:{t["accent"]};">●</span> '
            f'Generating answer…</div>'
        )

        if not self.isVisible():
            self.show()
        self.setWindowOpacity(self._opacity)
        # TTFT-OPT: Disable live markdown render during streaming to save
        # 5-15ms per 300ms cycle. Rendering only happens on stream complete.
        # User sees raw tokens streaming; final render applies all formatting.
        # self._stream_render_timer.start()

    def _do_stream_render(self):
        """
        Debounced live markdown render called every 300 ms during streaming.
        Gives streaming text live syntax highlighting and formatting without
        blocking the UI on every single token.
        """
        if not self._streaming or not self._current_md:
            return
        # Preserve the user's scroll position
        sb  = self._answer_view.verticalScrollBar()
        pos = sb.value()
        self._answer_view.setHtml(md_to_html(self._current_md, self._theme()))
        sb.setValue(pos)

    def append_token(self, token: str):
        """
        O(1) per token — direct insertion, no re-parse, no re-layout.
        Auto-scroll intentionally removed: user scrolls freely.
        """
        if not token:
            return

        # Clear placeholder on very first token
        if not self._current_md:
            self._answer_view.clear()

        self._current_md += token

        self._answer_view.moveCursor(QTextCursor.MoveOperation.End)
        self._answer_view.insertPlainText(token)
        # ← no sb.setValue() — auto-scroll removed

    def finish_stream(self, label: str = ""):
        """One final setHtml() call at the end of the stream."""
        self._streaming = False
        self._stream_render_timer.stop()     # stop debounced live render
        self._lbl_status.setText("")

        self._render_timer.stop()
        self._do_render()                    # single full final render

        if self._current_md.strip():
            lbl = label or f"Answer {len(self._history) + 1}"
            self._history.append(
                (lbl, self._current_md, self._current_question)
            )
            self._history_index = len(self._history) - 1
            self._update_nav()

    # ── Non-streaming helpers ──────────────────────────────────────────────────

    def set_answer(self, markdown: str, label: str = "", question: str = ""):
        self._streaming  = False
        self._current_md = markdown
        self._render_timer.stop()
        self._lbl_status.setText("")

        if question:
            self.show_question(question)
        else:
            self.hide_question()

        self._do_render()

        if not self.isVisible():
            self.show()
        self.setWindowOpacity(self._opacity)

        if markdown.strip():
            lbl = label or f"Answer {len(self._history) + 1}"
            self._history.append((lbl, markdown, self._current_question))
            self._history_index = len(self._history) - 1
            self._update_nav()

    def set_error(self, message: str):
        self._streaming = False
        self._render_timer.stop()
        self._lbl_status.setText("")
        self.hide_question()

        t        = self._theme()
        safe_msg = _escape_html(message)
        self._answer_view.setHtml(
            f'<div style="padding:20px 18px;">'
            f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<span style="font-size:18px;">⚠</span>'
            f'<div>'
            f'<div style="color:{t["error"]};font-size:13px;'
            f'font-family:Segoe UI,sans-serif;font-weight:600;'
            f'margin-bottom:4px;">Error</div>'
            f'<div style="color:{t["text"]};font-size:13px;'
            f'font-family:Segoe UI,sans-serif;line-height:1.6;">'
            f'{safe_msg}</div></div></div></div>'
        )
        if not self.isVisible():
            self.show()
        self.setWindowOpacity(self._opacity)

    def show_notification_banner(self, message: str, ntype: str = "info") -> None:
        """
        BUG-10 fix: Show a non-destructive notification banner in the status bar.

        Unlike set_error(), this method does NOT overwrite the active answer or
        hide the question bar. It shows the notification text in the status label
        for 6 seconds, then auto-clears. If a stream is active, the banner is
        shown after the stream completes (queued via QTimer).

        Args:
            message: The notification text (plain text, no markdown).
            ntype:   "info" | "warning" | "critical" — controls icon + color.
        """
        t = self._theme()
        color_map = {
            "info":     t.get("accent",  "#4f8ef7"),
            "warning":  "#f59e0b",
            "critical": t.get("error",   "#e05252"),
        }
        color = color_map.get(ntype, color_map["info"])

        # Truncate long messages for the status bar
        display = message[:80] + ("…" if len(message) > 80 else "")

        def _show_banner():
            self._lbl_status.setStyleSheet(f"color: {color}; font-size: 11px;")
            self._lbl_status.setText(display)
            # Auto-clear after 6 seconds
            QTimer.singleShot(6000, lambda: (
                self._lbl_status.setStyleSheet(""),
                self._lbl_status.setText(""),
            ))

        if self._streaming:
            # Queue banner to show after stream finishes (don't interrupt)
            QTimer.singleShot(500, _show_banner)
        else:
            _show_banner()

    def show_transcript(self, text: str, status_line: str = "🔴 Recording…"):
        t = self._theme()
        self.hide_question()
        status_color = (
            t["accent"] if "Answering" in status_line else
            "#e5c07b"   if "Ready"     in status_line else
            "#e05252"
        )
        safe_text = _escape_html(text)
        self._answer_view.setHtml(
            f'<div style="padding:14px 18px;">'
            f'<div style="background:rgba(255,140,0,0.08);'
            f'border-radius:6px;padding:3px 12px;margin-bottom:12px;'
            f'display:inline-block;">'
            f'<span style="color:{status_color};font-size:10px;'
            f'font-weight:700;letter-spacing:1px;'
            f'font-family:Consolas,monospace;">'
            f'{_escape_html(status_line)}</span></div>'
            f'<div style="color:{t["text"]};font-size:15px;line-height:1.85;'
            f'font-family:Segoe UI,sans-serif;margin-top:4px;'
            f'word-break:break-word;">{safe_text}</div>'
            f'<div style="color:{t["subtext"]};font-size:11px;'
            f'margin-top:14px;font-family:Segoe UI,sans-serif;">'
            f'Press <b style="color:{t["accent"]};">Ctrl+Shift+I</b> '
            f'to stop</div></div>'
        )
        self._lbl_status.setText(status_line[:30])
        # ← no auto-scroll to bottom — removed
        if not self.isVisible():
            self.show()
            self.setWindowOpacity(self._opacity)

    # ── History ────────────────────────────────────────────────────────────────

    def _go_prev(self):
        if self._history_index > 0:
            self._history_index -= 1
            self._show_history_entry()

    def _go_next(self):
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self._show_history_entry()

    def _show_history_entry(self):
        if not (0 <= self._history_index < len(self._history)):
            return
        lbl, md, question      = self._history[self._history_index]
        self._current_md       = md
        self._current_question = question
        self._lbl_status.setText("")
        self._streaming        = False
        self._render_timer.stop()
        self._do_render()
        if question:
            self.show_question(question)
        else:
            self.hide_question()
        self._update_nav()

    def _update_nav(self):
        total = len(self._history)
        idx   = self._history_index
        self._btn_prev.setEnabled(idx > 0)
        self._btn_next.setEnabled(idx < total - 1)
        if total == 0:
            self._lbl_history.setText("No history")
        elif total == 1:
            lbl = self._history[0][0]
            self._lbl_history.setText(
                lbl[:20] + ("…" if len(lbl) > 20 else "")
            )
        else:
            self._lbl_history.setText(f"{idx + 1} / {total}")

    def prev_history(self):
        self._go_prev()

    def next_history(self):
        self._go_next()

    # ── Utilities ──────────────────────────────────────────────────────────────

    def _copy_answer(self):
        QApplication.clipboard().setText(self._current_md)
        self._lbl_status.setText("✓ Copied!")
        QTimer.singleShot(2000, lambda: self._lbl_status.setText(""))

    def move_by(self, direction: str):
        offsets = {
            "up":    QPoint(0, -20),
            "down":  QPoint(0,  20),
            "left":  QPoint(-20, 0),
            "right": QPoint( 20, 0),
        }
        if direction in offsets:
            self.move(self.pos() + offsets[direction])

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.setWindowOpacity(self._opacity)
            QTimer.singleShot(100, self._hide_from_capture)

    def _hide_from_capture(self):
        if _HAS_WINDOW_HIDE:
            try:
                window_hide.make_fully_invisible(self)
            except Exception:
                pass

    # ── Drag ───────────────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if (e.button() == Qt.MouseButton.LeftButton
                and self._header.geometry().contains(
                    e.position().toPoint()
                )):
            self._drag_pos = (
                e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def showEvent(self, e):
        super().showEvent(e)
        self.setWindowOpacity(self._opacity)
        QTimer.singleShot(120, self._hide_from_capture)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._answer_view.document().setTextWidth(
            self._answer_view.viewport().width()
        )