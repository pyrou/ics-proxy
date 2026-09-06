import os
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


CONTENT_LINE = re.compile(r"^[A-Za-z0-9-]+(?:;[^:]*)?:")
TEXT_PROPERTIES = {"SUMMARY", "DESCRIPTION", "LOCATION", "COMMENT", "CONTACT"}


def encode_text(value: str) -> str:
    """Escape an already mostly-iCalendar TEXT value without double escaping it."""
    result = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            following = value[index + 1]
            if following in "\\,;nN":
                result.extend((char, following))
                index += 2
                continue
            result.append("\\\\")
        elif char in ",;":
            result.extend(("\\", char))
        else:
            result.append(char)
        index += 1
    return "".join(result)


def fold_line(line: str, limit: int = 75) -> list[str]:
    """Fold one content line without splitting a UTF-8 code point."""
    folded = []
    remaining = line
    first = True
    while remaining:
        byte_limit = limit if first else limit - 1
        size = 0
        cut = 0
        for cut, char in enumerate(remaining, 1):
            char_size = len(char.encode("utf-8"))
            if size + char_size > byte_limit:
                cut -= 1
                break
            size += char_size
        else:
            cut = len(remaining)
        if cut == 0:
            raise ValueError("Unable to fold content line")
        folded.append(("" if first else " ") + remaining[:cut])
        remaining = remaining[cut:]
        first = False
    return folded or [""]


def repair_ics(payload: bytes, prefix: str) -> bytes:
    text = payload.decode("utf-8-sig")
    physical_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while physical_lines and physical_lines[-1] == "":
        physical_lines.pop()

    # Unfold legal continuations and repair raw newlines inside TEXT properties.
    logical_lines: list[str] = []
    for line in physical_lines:
        if line.startswith((" ", "\t")) and logical_lines:
            logical_lines[-1] += line[1:]
        elif CONTENT_LINE.match(line):
            logical_lines.append(line)
        elif logical_lines:
            previous_name = logical_lines[-1].split(":", 1)[0].split(";", 1)[0].upper()
            if previous_name not in TEXT_PROPERTIES:
                raise ValueError(f"Malformed content line after {previous_name}")
            logical_lines[-1] += "\\n" + line
        elif line:
            raise ValueError("Malformed first content line")

    output: list[str] = []
    in_event = False
    for line in logical_lines:
        left, value = line.split(":", 1)
        name = left.split(";", 1)[0].upper()
        if name == "BEGIN" and value.upper() == "VEVENT":
            in_event = True
        if name in TEXT_PROPERTIES:
            value = encode_text(value)
        if in_event and name == "SUMMARY":
            value = encode_text(prefix) + value
        output.extend(fold_line(f"{left}:{value}"))
        if name == "END" and value.upper() == "VEVENT":
            in_event = False

    return ("\r\n".join(output) + "\r\n").encode("utf-8")


def normalize_path(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("SERVER_PATH must not be empty")
    if not value.startswith("/"):
        value = "/" + value
    if "?" in value or "#" in value:
        raise ValueError("SERVER_PATH must not contain '?' or '#'")
    return value


INPUT_URL = os.environ.get("ICS_INPUT_URL", "")
SERVER_PATH = normalize_path(os.environ.get("SERVER_PATH", "/calendar.ics"))
SERVER_HOST = os.environ.get("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("SERVER_PORT", "8080"))
EVENT_PREFIX = os.environ.get("EVENT_PREFIX", "")
FETCH_TIMEOUT = float(os.environ.get("FETCH_TIMEOUT", "15"))


class Handler(BaseHTTPRequestHandler):
    server_version = "ics-proxy/1.0"

    def do_GET(self):
        self._serve(send_body=True)

    def do_HEAD(self):
        self._serve(send_body=False)

    def _serve(self, send_body: bool):
        request_path = self.path.split("?", 1)[0]
        if request_path != SERVER_PATH:
            self.send_error(404)
            return
        try:
            request = urllib.request.Request(
                INPUT_URL,
                headers={"Accept": "text/calendar", "User-Agent": "ics-proxy/1.0"},
            )
            with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
                repaired = repair_ics(response.read(), EVENT_PREFIX)
        except (urllib.error.URLError, UnicodeError, ValueError) as error:
            print(f"Upstream/ICS error: {error}", file=sys.stderr)
            self.send_error(502, "Unable to fetch or repair calendar")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/calendar; charset=utf-8")
        self.send_header("Content-Disposition", 'inline; filename="calendar.ics"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(repaired)))
        self.end_headers()
        if send_body:
            self.wfile.write(repaired)

    def log_message(self, fmt, *args):
        # Deliberately avoid logging the secret URL path.
        print(f'{self.address_string()} - {args[1]}', file=sys.stderr)


def main():
    if not INPUT_URL.startswith(("https://", "http://")):
        raise SystemExit("ICS_INPUT_URL must be an http:// or https:// URL")
    server = ThreadingHTTPServer((SERVER_HOST, SERVER_PORT), Handler)
    print(f"Listening on {SERVER_HOST}:{SERVER_PORT}", file=sys.stderr)
    server.serve_forever()


if __name__ == "__main__":
    main()
