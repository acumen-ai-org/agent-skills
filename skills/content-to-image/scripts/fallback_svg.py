#!/usr/bin/env python3
"""Write a self-contained diagnostic SVG when image generation fails.

Pure stdlib: SVG is a valid image, embeddable as a data URI and renders in a
report <img>/image body, so a failed render still yields an artifact. The SVG
shows the headline "Failed to generate image" and, below it, one wrapped line
per attempt (provider + HTTP status / error). All dynamic text is XML-escaped.

Usage: fallback_svg.py <out.svg> <reason> [attempt ...]
  <out.svg>   destination path
  <reason>    short hard-failure summary (one line)
  attempt...  zero or more "provider: HTTP <code> <detail>" strings

Exit codes:
  0  SVG written
  1  bad arguments
"""
import sys
import xml.sax.saxutils as saxutils

CANVAS_WIDTH = 1024
CANVAS_HEIGHT = 576
MARGIN_X = 64
HEADLINE_Y = 132
HEADLINE_SIZE = 44
REASON_Y = 188
REASON_SIZE = 22
DIAG_TITLE_Y = 252
DIAG_TITLE_SIZE = 22
DIAG_FIRST_Y = 296
DIAG_LINE_HEIGHT = 34
DIAG_SIZE = 19
WRAP_CHARS = 92
BACKGROUND = "#1B1B22"
HEADLINE_COLOR = "#FF6B6B"
BODY_COLOR = "#E6E6EC"
MUTED_COLOR = "#9AA0AC"


def wrap(text: str, width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= width:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def text_element(x: int, y: int, size: int, color: str, content: str, weight: str = "normal") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Menlo,Consolas,monospace" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}" '
        f'xml:space="preserve">{saxutils.escape(content)}</text>'
    )


def main() -> int:
    if len(sys.argv) < 3:
        sys.stderr.write("usage: fallback_svg.py <out.svg> <reason> [attempt ...]\n")
        return 1

    out_path = sys.argv[1]
    reason = sys.argv[2]
    attempts = sys.argv[3:]

    elements = [
        f'<rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="{BACKGROUND}"/>',
        text_element(MARGIN_X, HEADLINE_Y, HEADLINE_SIZE, HEADLINE_COLOR,
                     "Failed to generate image", weight="bold"),
        text_element(MARGIN_X, REASON_Y, REASON_SIZE, MUTED_COLOR, reason),
        text_element(MARGIN_X, DIAG_TITLE_Y, DIAG_TITLE_SIZE, BODY_COLOR,
                     "Attempts:", weight="bold"),
    ]

    line_y = DIAG_FIRST_Y
    diagnostic_lines = attempts if attempts else ["(no provider attempts recorded)"]
    for attempt in diagnostic_lines:
        wrapped_lines = wrap(attempt, WRAP_CHARS)
        for index, wrapped in enumerate(wrapped_lines):
            prefix = "  - " if index == 0 else "    "
            elements.append(
                text_element(MARGIN_X, line_y, DIAG_SIZE, BODY_COLOR, f"{prefix}{wrapped}")
            )
            line_y += DIAG_LINE_HEIGHT

    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" '
        f'width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}">\n'
        + "\n".join(elements)
        + "\n</svg>\n"
    )

    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(svg)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
