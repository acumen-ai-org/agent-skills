#!/usr/bin/env python3
"""Static network egress/ingress inventory by import and call pattern.

Usage:
  run-network-extractor.py <repo> <out_dir>

Walks the source tree (git-tracked files when <repo> is a git repo, else the
filesystem) and matches each line against a fixed table of outbound-client and
inbound-listener signatures across Python, JavaScript/TypeScript, Go, Rust,
Java/Kotlin, C#, Ruby, PHP, and shell. Writes
<out_dir>/network.raw.json — a factual inventory to-fragment.py folds into the
one `security` attack-surface fragment. No findings are judged here; the
threat-synthesis.md role narrates the surface.

Exit codes:
  0  inventory written
  1  bad arguments
  5  repo path does not exist
"""
import json
import pathlib
import re
import subprocess
import sys

SCANNABLE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".kts", ".cs",
    ".rb", ".php", ".sh", ".bash",
}

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "target", "dist", "build",
    "__pycache__", ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache",
}

MAX_FILE_BYTES = 2_000_000

EGRESS_PATTERNS = [
    ("python-requests", r"\brequests\.(?:get|post|put|delete|patch|head|request|Session)\s*\("),
    ("python-httpx", r"\bhttpx\.(?:get|post|put|delete|patch|AsyncClient|Client)\s*\("),
    ("python-urllib", r"\burllib\.request\.urlopen\s*\("),
    ("python-aiohttp", r"\baiohttp\.ClientSession\s*\("),
    ("python-socket-connect", r"\bsocket\.socket\s*\([^)]*\)[\s\S]{0,80}?\.connect\s*\("),
    ("js-fetch", r"(?<![\w.])fetch\s*\(\s*[`'\"]https?://"),
    ("js-axios", r"\baxios\s*(?:\.\s*(?:get|post|put|delete|patch|request))?\s*\("),
    ("js-http-request", r"\b(?:https?|http)\.(?:request|get)\s*\("),
    ("js-xhr", r"\bnew\s+XMLHttpRequest\s*\("),
    ("js-websocket", r"\bnew\s+WebSocket\s*\("),
    ("go-http-client", r"\bhttp\.(?:Get|Post|PostForm|Head|NewRequest|Client\{)"),
    ("go-net-dial", r"\bnet\.Dial(?:Timeout)?\s*\("),
    ("rust-reqwest", r"\breqwest::(?:get|Client::new|blocking::get)\b"),
    ("rust-tcp-connect", r"\bTcpStream::connect\s*\("),
    ("java-httpclient", r"\bHttpClient\.newHttpClient\s*\(|\bnew\s+URL\s*\(\s*\"https?://"),
    ("java-okhttp", r"\bnew\s+OkHttpClient\b|\bRequest\.Builder\s*\("),
    ("csharp-httpclient", r"\bnew\s+HttpClient\s*\(|\bWebRequest\.Create\s*\("),
    ("ruby-nethttp", r"\bNet::HTTP\.(?:get|post|start|new)\b"),
    ("php-curl", r"\bcurl_init\s*\(|\bfile_get_contents\s*\(\s*[\"']https?://"),
    ("shell-curl", r"(?<![\w/])curl\s+[^\n]*https?://"),
    ("shell-wget", r"(?<![\w/])wget\s+[^\n]*https?://"),
]

INGRESS_PATTERNS = [
    ("python-flask-route", r"@\w+\.route\s*\(|\bapp\.add_url_rule\s*\("),
    ("python-fastapi-route", r"@\w+\.(?:get|post|put|delete|patch|websocket)\s*\("),
    ("python-django-urls", r"\b(?:path|re_path|url)\s*\(\s*[r]?[\"']"),
    ("python-socket-bind", r"\.bind\s*\(\s*\([^)]*\)\s*\)"),
    ("python-http-server", r"\bHTTPServer\s*\(|\bsocketserver\.\w+Server\s*\("),
    ("js-express-listen", r"\.listen\s*\(\s*\d|\bapp\.(?:get|post|put|delete|patch|use)\s*\(\s*[`'\"]/"),
    ("js-http-createserver", r"\b(?:https?|http)\.createServer\s*\("),
    ("js-ws-server", r"\bnew\s+WebSocketServer\s*\(|\bnew\s+WebSocket\.Server\s*\("),
    ("go-http-listen", r"\bhttp\.(?:ListenAndServe|HandleFunc|Handle)\s*\(|\bnet\.Listen\s*\("),
    ("rust-tcp-listen", r"\bTcpListener::bind\s*\(|\bHttpServer::new\s*\("),
    ("java-spring-mapping", r"@(?:Get|Post|Put|Delete|Patch|Request)Mapping\b|\bServerSocket\s*\("),
    ("csharp-aspnet-route", r"\[(?:HttpGet|HttpPost|HttpPut|HttpDelete|Route)\b|\bMapControllers\s*\("),
    ("ruby-rack-listen", r"\bRack::Handler|\bget\s+[\"']/|\bpost\s+[\"']/"),
    ("php-route", r"\$(?:router|app)\s*->\s*(?:get|post|put|delete|patch)\s*\(|\$_SERVER\['REQUEST_URI'\]"),
    ("shell-nc-listen", r"(?<![\w/])nc\s+-l\b|(?<![\w/])socat\s+[^\n]*LISTEN"),
]


def _git_tracked_files(repo):
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "-z"],
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return None
    names = result.stdout.decode("utf-8", "replace").split("\0")
    return [repo / name for name in names if name]


def _walk_files(repo):
    files = []
    for path in repo.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            files.append(path)
    return files


def _candidate_files(repo):
    tracked = _git_tracked_files(repo)
    paths = tracked if tracked is not None else _walk_files(repo)
    return [
        path
        for path in paths
        if path.suffix.lower() in SCANNABLE_SUFFIXES
        and not any(part in SKIP_DIRS for part in path.parts)
    ]


def _scan_file(path, repo, compiled):
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return []
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rel = path.relative_to(repo).as_posix()
    hits = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if len(line) > 4000:
            continue
        for direction, signature, regex in compiled:
            if regex.search(line):
                hits.append(
                    {
                        "direction": direction,
                        "signature": signature,
                        "path": rel,
                        "line": line_number,
                        "code": line.strip()[:200],
                    }
                )
    return hits


def main():
    args = sys.argv[1:]
    if len(args) != 2:
        sys.stderr.write("usage: run-network-extractor.py <repo> <out_dir>\n")
        return 1

    repo = pathlib.Path(args[0])
    out_dir = pathlib.Path(args[1])
    if not repo.exists():
        sys.stderr.write(f"repo path does not exist: {repo}\n")
        print("TOOL run-network-extractor exit=5")
        return 5

    repo = repo.resolve()
    compiled = (
        [("egress", name, re.compile(pattern)) for name, pattern in EGRESS_PATTERNS]
        + [("ingress", name, re.compile(pattern)) for name, pattern in INGRESS_PATTERNS]
    )

    egress = []
    ingress = []
    for path in _candidate_files(repo):
        for hit in _scan_file(path, repo, compiled):
            (egress if hit["direction"] == "egress" else ingress).append(hit)

    sort_key = lambda h: (h["signature"], h["path"], h["line"])
    egress.sort(key=sort_key)
    ingress.sort(key=sort_key)

    inventory = {
        "repo": repo.as_posix(),
        "egress": egress,
        "ingress": ingress,
        "egress_count": len(egress),
        "ingress_count": len(ingress),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "network.raw.json"
    raw_path.write_text(
        json.dumps(inventory, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"wrote {raw_path}")
    print("TOOL run-network-extractor exit=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
