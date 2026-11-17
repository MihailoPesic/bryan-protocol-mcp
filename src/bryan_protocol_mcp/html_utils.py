"""HTML-to-Markdown conversion and timestamp helpers using Python stdlib."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser


_SKIP_TAGS = frozenset({"script", "style", "svg", "noscript", "template", "iframe"})
_BLOCK_TAGS = frozenset({"p", "div", "section", "article", "blockquote", "pre", "figure", "figcaption", "header", "footer"})


class _MarkdownHTMLParser(HTMLParser):
    """Minimal HTML-to-Markdown converter tailored for protocol pages and blog posts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._list_stack: list[tuple[str, int]] = []
        self._in_link: str | None = None
        self._link_text: list[str] = []
        self._in_table_row = False
        self._row_cells: list[str] = []
        self._in_cell = False
        self._cell_parts: list[str] = []
        self._table_rows: list[list[str]] = []

    def _emit(self, text: str) -> None:
        if self._skip_depth > 0:
            return
        if self._in_cell:
            self._cell_parts.append(text)
        elif self._in_link is not None:
            self._link_text.append(text)
        else:
            self.parts.append(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return

        attr_map = dict(attrs)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(tag[1])
            self._emit(f"\n\n{'#' * level} ")
        elif tag == "br":
            self._emit("\n")
        elif tag == "hr":
            self._emit("\n\n---\n\n")
        elif tag in _BLOCK_TAGS:
            self._emit("\n\n")
        elif tag == "ul":
            self._list_stack.append(("ul", 0))
            self._emit("\n")
        elif tag == "ol":
            self._list_stack.append(("ol", 0))
            self._emit("\n")
        elif tag == "li":
            indent = "  " * max(0, len(self._list_stack) - 1)
            if self._list_stack:
                kind, idx = self._list_stack[-1]
                idx += 1
                self._list_stack[-1] = (kind, idx)
                bullet = f"{idx}. " if kind == "ol" else "- "
            else:
                bullet = "- "
            self._emit(f"\n{indent}{bullet}")
        elif tag in {"strong", "b"}:
            self._emit("**")
        elif tag in {"em", "i"}:
            self._emit("*")
        elif tag == "code":
            self._emit("`")
        elif tag == "a":
            href = (attr_map.get("href") or "").strip()
            if href and not href.startswith("javascript:"):
                self._in_link = href
                self._link_text = []
        elif tag == "table":
            self._table_rows = []
            self._emit("\n\n")
        elif tag == "tr":
            self._in_table_row = True
            self._row_cells = []
        elif tag in {"td", "th"}:
            self._in_cell = True
            self._cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth > 0:
            return

        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} or tag in _BLOCK_TAGS:
            self._emit("\n\n")
        elif tag in {"ul", "ol"}:
            if self._list_stack:
                self._list_stack.pop()
            self._emit("\n")
        elif tag in {"strong", "b"}:
            self._emit("**")
        elif tag in {"em", "i"}:
            self._emit("*")
        elif tag == "code":
            self._emit("`")
        elif tag == "a" and self._in_link is not None:
            href = self._in_link
            label = "".join(self._link_text).strip()
            self._in_link = None
            self._link_text = []
            if label:
                self._emit(f"[{label}]({href})" if href.startswith(("http://", "https://", "#")) else label)
        elif tag in {"td", "th"} and self._in_cell:
            self._in_cell = False
            cell = " ".join("".join(self._cell_parts).split())
            self._row_cells.append(cell.replace("|", "\\|"))
            self._cell_parts = []
        elif tag == "tr" and self._in_table_row:
            self._in_table_row = False
            if any(self._row_cells):
                self._table_rows.append(self._row_cells)
            self._row_cells = []
        elif tag == "table" and self._table_rows:
            cols = max(len(r) for r in self._table_rows)
            lines = []
            for idx, row in enumerate(self._table_rows):
                padded = row + [""] * (cols - len(row))
                lines.append("| " + " | ".join(padded) + " |")
                if idx == 0:
                    lines.append("| " + " | ".join(["---"] * cols) + " |")
            self._table_rows = []
            self._emit("\n" + "\n".join(lines) + "\n\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        cleaned = re.sub(r"[ \t\r\n]+", " ", data)
        self._emit(cleaned)


def html_to_markdown(raw_html: str) -> str:
    """Convert an HTML fragment into clean, readable Markdown."""
    if not raw_html:
        return ""
    parser = _MarkdownHTMLParser()
    parser.feed(raw_html)
    parser.close()
    text = "".join(parser.parts)
    text = html.unescape(text)
    # Clean stray spacing around newlines and formatting markers
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    total = max(0, int(seconds))
    hrs, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    if hrs > 0:
        return f"{hrs}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def youtube_timestamp_url(video_id: str, start_sec: float) -> str:
    """Build a YouTube watch URL deep-linked to a timestamp."""
    sec = max(0, int(start_sec))
    return f"https://www.youtube.com/watch?v={video_id}&t={sec}s"
