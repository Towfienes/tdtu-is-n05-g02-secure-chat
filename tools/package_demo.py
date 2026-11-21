"""Package source, documentation, and captured evidence. Omit all generated keys."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
NAME = "Demo_N05_G02_524H0195_524H0191_524H0187"
SKIP = {".gradle", ".idea", "build", "generated", "__pycache__"}


def main():
    output = ROOT.parent / f"{NAME}.zip"
    temporary = output.with_suffix(".zip.tmp")
    entries = [
        ROOT / name
        for name in (".gitignore", "README.md", "DEMO_SCRIPT_VI.md", "LICENSE")
    ]
    for directory in ("android", "backend", "tools", "evidence", "report"):
        entries.extend(
            item
            for item in (ROOT / directory).rglob("*")
            if item.is_file() and not (set(item.relative_to(ROOT).parts) & SKIP)
        )
    for name in (
        "report/Final_Demonstration.docx",
        "report/Final_Demonstration.pdf",
        "evidence/results.json",
    ):
        if not (ROOT / name).is_file():
            raise FileNotFoundError(name)
    with ZipFile(temporary, "w", ZIP_DEFLATED, compresslevel=7) as archive:
        for item in sorted(entries):
            if (
                item.is_symlink()
                or item.name == "local.properties"
                or item.suffix in {".key", ".pem", ".p12", ".jks", ".apk"}
            ):
                raise ValueError(
                    f"Unexpected file in submission: {item.relative_to(ROOT)}"
                )
            archive.write(item, f"{NAME}/{item.relative_to(ROOT).as_posix()}")
    with ZipFile(temporary) as archive:
        assert archive.testzip() is None
    temporary.replace(output)
    print(f"{output.name}: {len(entries)} files, ZIP CRC verified")


if __name__ == "__main__":
    main()
