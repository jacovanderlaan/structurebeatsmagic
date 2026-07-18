"""Shared image handling for the site builders.

The renders in the product folders (W:/systems/concepts/<slug>/assets/ and
W:/systems/products/sbm/articles/<slug>/assets/) are full-size 1536px PNGs of
1.5-2 MB each. Those are the ORIGINALS and stay that way -- the product folder
is the source, the repo is the publishing channel.

What gets committed to the repo should be web-sized. Before this existed, the
builders did a straight shutil.copy2 of the originals, so:

  * the repo had grown to 322 MB of images,
  * pushes took minutes,
  * every visitor downloaded ~1.5 MB per hero,
  * and any manual optimisation was silently undone by the next build.

These are flat vector-style infographics, so downscaling to 1200px and
quantising to a 64-colour palette is visually indistinguishable (verified by eye
on line-heavy diagrams, text-heavy panels and photo-style renders) while cutting
roughly 70% of the bytes. Photographs are left alone -- see below.
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path

# Images at or below this size are already small enough to ship as-is.
SKIP_UNDER_BYTES = 700_000
MAX_EDGE = 1200
PALETTE_COLOURS = 64
# Only replace the original if quantising actually wins something meaningful;
# on photographs it usually does not, and a palette would visibly band them.
MIN_SAVING = 0.9


def copy_optimised(src: Path, dst: Path) -> None:
    """Copy an image into the site, web-optimising it on the way through.

    Falls back to a plain copy when Pillow is unavailable, when the file is
    already small, or when quantising would not meaningfully shrink it.
    """
    try:
        from PIL import Image
    except ImportError:
        shutil.copy2(src, dst)
        return

    if src.suffix.lower() != ".png" or src.stat().st_size < SKIP_UNDER_BYTES:
        shutil.copy2(src, dst)
        return

    try:
        im = Image.open(src).convert("RGB")
        im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
        quantised = im.quantize(
            colors=PALETTE_COLOURS, method=Image.MEDIANCUT, dither=Image.NONE
        )
        buf = io.BytesIO()
        quantised.save(buf, "PNG", optimize=True)
        data = buf.getvalue()
    except Exception:
        shutil.copy2(src, dst)
        return

    if len(data) < src.stat().st_size * MIN_SAVING:
        dst.write_bytes(data)
    else:
        shutil.copy2(src, dst)
