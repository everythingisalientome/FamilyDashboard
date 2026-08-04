"""Compress the ambient-background JPEGs in static/img/bg in place.

A one-off dev/ops tool (not part of the running app), so it is not in
requirements.txt. It needs Pillow:

    python -m pip install Pillow

Then, from the repo root:

    python scripts/compress_backgrounds.py            # compress with defaults
    python scripts/compress_backgrounds.py --quality 78
    python scripts/compress_backgrounds.py --dry-run  # report only, write nothing

Each image is re-encoded as a progressive, optimized JPEG and downscaled to fit
within --max-width x --max-height (the backgrounds are meant to be 1920x1080).
The result replaces the original only when it is actually smaller, so re-running
is safe and already-lean files are left alone (use --force to override).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO_ROOT / "static" / "img" / "bg"
EXTENSIONS = {".jpg", ".jpeg"}


def _human(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR,
                        help=f"folder of JPEGs to compress (default: {DEFAULT_DIR})")
    parser.add_argument("--quality", type=int, default=82,
                        help="JPEG quality 1-95 (default: 82)")
    parser.add_argument("--max-width", type=int, default=1920,
                        help="max width in px (default: 1920)")
    parser.add_argument("--max-height", type=int, default=1080,
                        help="max height in px (default: 1080)")
    parser.add_argument("--force", action="store_true",
                        help="write the re-encoded file even if it isn't smaller")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change without writing anything")
    return parser.parse_args(argv)


def compress_one(path: Path, args: argparse.Namespace, Image) -> tuple[int, int]:
    """Return (old_size, new_size). new_size == old_size means 'left as is'."""
    import io

    old_size = path.stat().st_size
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((args.max_width, args.max_height), Image.LANCZOS)  # fit, keep AR
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=args.quality,
                 optimize=True, progressive=True)

    new_bytes = buffer.getvalue()
    new_size = len(new_bytes)

    if args.dry_run:
        return old_size, new_size
    if new_size < old_size or args.force:
        path.write_bytes(new_bytes)
        return old_size, new_size
    return old_size, old_size  # keep the original; it was already smaller


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    try:
        from PIL import Image
    except ImportError:
        print("Pillow is required. Install it with:  python -m pip install Pillow",
              file=sys.stderr)
        return 1

    if not args.dir.is_dir():
        print(f"No such folder: {args.dir}", file=sys.stderr)
        return 1

    images = sorted(p for p in args.dir.iterdir()
                    if p.is_file() and p.suffix.lower() in EXTENSIONS)
    if not images:
        print(f"No .jpg/.jpeg files in {args.dir}")
        return 0

    verb = "Would compress" if args.dry_run else "Compressing"
    print(f"{verb} {len(images)} image(s) in {args.dir} "
          f"(quality={args.quality}, max={args.max_width}x{args.max_height})\n")

    total_old = total_new = 0
    for path in images:
        try:
            old_size, new_size = compress_one(path, args, Image)
        except Exception as err:  # never let one bad file abort the batch
            print(f"  ! {path.name}: skipped ({err})")
            continue
        total_old += old_size
        total_new += new_size
        if new_size < old_size:
            pct = (1 - new_size / old_size) * 100
            print(f"  {path.name:<30} {_human(old_size):>9} -> {_human(new_size):>9}  (-{pct:.0f}%)")
        else:
            print(f"  {path.name:<30} {_human(old_size):>9}   (unchanged)")

    if total_old:
        saved = total_old - total_new
        pct = (saved / total_old) * 100 if total_old else 0
        print(f"\nTotal: {_human(total_old)} -> {_human(total_new)}  "
              f"(saved {_human(saved)}, {pct:.0f}%)")
        if args.dry_run:
            print("Dry run - nothing was written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
