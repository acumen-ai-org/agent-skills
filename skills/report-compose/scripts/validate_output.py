#!/usr/bin/env python3
"""Validate a report-compose output file against the single-file contract.

Usage: validate_output.py <report.html>

Checks:
  - parses as HTML with <html>, <head>, <body> and a non-empty <title>
  - every src/href/srcset/CSS-url() target is a pinned jsdelivr URL, a Google
    Fonts URL, a data: URI, a #fragment, or a mailto: link — nothing relative,
    no other hosts. Sole exception: <link rel="satellite" href="<dir>/<id>.html">
    declarations (written by build_report.py for declared satellite pages) and
    <a> hrefs exactly matching a declared satellite
  - every jsdelivr <script>/<link> carries integrity + crossorigin and pins a
    version with @<semver> in the URL (Google Fonts is the sole SRI exemption)
  - provenance: <meta name="generator" content="report-compose"> and an
    ISO YYYY-MM-DD date in body text

Reports byte size on stdout. Sizes above 25 MB print a warning (browsers
handle larger files, but transfer and review get painful) — never a failure.

Exit codes:
  0  pass
  1  bad usage
  2  file missing or unreadable
  3  contract violations (listed on stderr)
"""
import html.parser
import pathlib
import re
import sys

ALLOWED_ORIGINS = (
    "https://cdn.jsdelivr.net",
    "https://fonts.googleapis.com",
    "https://fonts.gstatic.com",
)
ALLOWED_SCHEMES = ("data:", "#", "mailto:")


def is_allowed(url):
    if url.startswith(ALLOWED_SCHEMES):
        return True
    return any(url == origin or url.startswith(origin + "/") for origin in ALLOWED_ORIGINS)
GENERATOR_RE = re.compile(r"^report-compose$")
SATELLITE_HREF_RE = re.compile(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+\.html$")
ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
JSDELIVR_VERSION_RE = re.compile(r"@\d+\.\d+\.\d+(?:[./-]|$)")
CSS_URL_RE = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")
SIZE_WARN_BYTES = 25 * 1024 * 1024


class ReportParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags_seen = set()
        self.refs = []
        self.generator = None
        self.title_parts = []
        self.body_text_parts = []
        self.style_parts = []
        self._stack = []

    def handle_starttag(self, tag, attrs):
        self._stack.append(tag)
        self.tags_seen.add(tag)
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name") == "generator":
            self.generator = attrs.get("content", "")
        for key in ("src", "href"):
            if attrs.get(key):
                self.refs.append((tag, key, attrs[key], attrs))
        if attrs.get("srcset"):
            for candidate in attrs["srcset"].split(","):
                url = candidate.strip().split()[0]
                if url:
                    self.refs.append((tag, "srcset", url, attrs))
        if attrs.get("style"):
            self.style_parts.append(attrs["style"])
        if tag in ("br", "img", "meta", "link", "input", "hr", "source"):
            self._stack.pop()

    def handle_endtag(self, tag):
        while self._stack and self._stack.pop() != tag:
            pass

    def handle_data(self, data):
        if "title" in self._stack:
            self.title_parts.append(data)
        if "style" in self._stack:
            self.style_parts.append(data)
        if "body" in self._stack and "script" not in self._stack:
            self.body_text_parts.append(data)


def validate(path):
    violations = []
    raw = path.read_bytes()
    parser = ReportParser()
    parser.feed(raw.decode("utf-8", errors="replace"))

    for tag in ("html", "head", "body"):
        if tag not in parser.tags_seen:
            violations.append(f"missing <{tag}> element")
    if not "".join(parser.title_parts).strip():
        violations.append("missing or empty <title>")

    satellite_hrefs = set()
    for tag, key, url, attrs in parser.refs:
        if tag == "link" and attrs.get("rel") == "satellite":
            if SATELLITE_HREF_RE.match(url):
                satellite_hrefs.add(url)
            else:
                violations.append(f'<link rel="satellite" href="{url}"> must be a relative <dir>/<id>.html path')

    for tag, key, url, attrs in parser.refs:
        if tag == "link" and attrs.get("rel") == "satellite":
            continue
        if tag == "a" and url in satellite_hrefs:
            continue
        if not is_allowed(url):
            violations.append(f"<{tag} {key}=\"{url}\"> is not an allowed reference (pinned jsdelivr, Google Fonts, data:, #fragment, mailto:, or a declared satellite)")
            continue
        if url.startswith("https://cdn.jsdelivr.net/"):
            if not JSDELIVR_VERSION_RE.search(url):
                violations.append(f"<{tag}> jsdelivr URL is not version-pinned: {url}")
            if not attrs.get("integrity"):
                violations.append(f"<{tag}> jsdelivr reference lacks integrity attribute: {url}")
            if "crossorigin" not in attrs:
                violations.append(f"<{tag}> jsdelivr reference lacks crossorigin attribute: {url}")

    for css in parser.style_parts:
        for url in CSS_URL_RE.findall(css):
            if not is_allowed(url):
                violations.append(f"CSS url({url}) is not an allowed reference")

    if parser.generator is None:
        violations.append('missing <meta name="generator" content="report-compose">')
    elif not GENERATOR_RE.match(parser.generator):
        violations.append(f'generator meta "{parser.generator}" is not exactly "report-compose"')

    if not ISO_DATE_RE.search(" ".join(parser.body_text_parts)):
        violations.append("no ISO YYYY-MM-DD provenance date found in body text")

    return violations, len(raw)


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 1
    path = pathlib.Path(sys.argv[1])
    if not path.is_file():
        print(f"not a readable file: {path}", file=sys.stderr)
        return 2
    violations, size = validate(path)
    human = f"{size / 1024:.0f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB"
    print(f"{path}: {size} bytes ({human})")
    if size > SIZE_WARN_BYTES:
        print(f"warning: file exceeds 25 MB — browsers handle it, but transfer and review get painful", file=sys.stderr)
    if violations:
        for v in violations:
            print(f"violation: {v}", file=sys.stderr)
        print(f"{len(violations)} violation(s)", file=sys.stderr)
        return 3
    print("pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
