"""Stage the static reader and its offline assets for Capacitor."""

from html.parser import HTMLParser
from pathlib import Path
from shutil import copy2


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
    (OUTPUT / "index.html").write_text(html + "\n", encoding="utf-8")
    print(f"Staged {len(assets) + 1} reader files in {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
