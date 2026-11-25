"""Archive the same offline web assets used by the Android APK."""

import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from stage_android_web import OUTPUT


def main(destination):
    destination.mkdir(parents=True, exist_ok=True)
    timestamp_file = OUTPUT / "reader-build-time.txt"
    timestamp = int(timestamp_file.read_text(encoding="ascii"))
    archive = destination / "reader-web-v1.zip"
    with ZipFile(archive, "w") as bundle:
        for source in sorted(OUTPUT.rglob("*")):
            if source.is_file() and source != timestamp_file:
                name = source.relative_to(OUTPUT).as_posix()
                entry = ZipInfo(name)
                bundle.writestr(entry, source.read_bytes(), compress_type=ZIP_DEFLATED)
    data = archive.read_bytes()
    if len(data) > 12 * 1024 * 1024:
        raise SystemExit("Android web update exceeds the installed APK's download limit")
    manifest = {
        "schema": 1,
        "timestamp": timestamp,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    (destination / "reader-web-v1.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
