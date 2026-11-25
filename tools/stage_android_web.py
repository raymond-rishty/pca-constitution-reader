"""Stage the static reader and its offline assets for Capacitor."""

import re
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from shutil import copy2
from subprocess import check_output


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build" / "android-web"


class ReaderScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            src = dict(attrs).get("src")
            if src:
                self.paths.add(Path(src))


def main():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    scripts = ReaderScripts()
    scripts.feed(html)
    assets = scripts.paths | {
        Path("manifest.webmanifest"),
        Path("android-content-update.js"),
        Path("apple-touch-icon.png"),
        Path("icon-192.png"),
        Path("icon-512.png"),
    }
    for pattern in ("content/cit/*.js", "diagrams/appendix-h*.svg"):
        matches = {source.relative_to(ROOT) for source in ROOT.glob(pattern)}
        if not matches:
            raise SystemExit(f"No Android assets match {pattern}")
        assets.update(matches)

    for path in assets:
        if not (ROOT / path).is_file():
            raise SystemExit(f"Missing Android asset: {path}")

    # Remove files staged by previous runs so removed citations stay removed.
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for file in OUTPUT.rglob("*"):
        if file.is_file() and file.relative_to(OUTPUT) not in assets:
            file.unlink()

    for path in sorted(assets):
        target = OUTPUT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(ROOT / path, target)

    # Native builds have their assets on disk and use the reader's font fallbacks.
    html = "\n".join(
        line for line in html.splitlines()
        if not line.startswith(('<link rel="preconnect" href="https://fonts.', '<link href="https://fonts.'))
    )
    # The Android bootstrap restores cached data before running the bundled reader.
    inline = re.search(r"(?ms)^<script>\s*(.*?)^</script>", html)
    if not inline:
        raise SystemExit("Missing inline reader script")
    baseline = check_output(["node", "tools/build_android_content.cjs"], cwd=ROOT, text=True)
    metadata = '<meta name="reader-content-baseline" content="' + escape(baseline) + '">'
    policy = (
        '<meta http-equiv="Content-Security-Policy" content="script-src \'self\'; '
        'object-src \'none\'; base-uri \'none\'; frame-src \'none\'; form-action \'none\'">'
    )
    html = (
        html[:inline.start()]
        + '<script defer src="android-content-update.js"></script>'
        + html[inline.end():]
    )
    html = html.replace("<head>", f"<head>\n{policy}\n{metadata}", 1)
    (OUTPUT / "android-reader.js").write_text(inline.group(1), encoding="utf-8")
    (OUTPUT / "index.html").write_text(html + "\n", encoding="utf-8")
    print(f"Staged {len(assets) + 2} reader files in {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
