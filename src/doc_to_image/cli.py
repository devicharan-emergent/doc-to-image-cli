"""Convert PDF or DOCX documents into per-page PNG images.

CLI:
    doc-to-image <file.pdf|file.docx> [-o OUT] [-d DPI] [-p PAGES]

Prints one absolute PNG path per line on stdout. Designed to be chained with
the agent's `view_file` tool — the agent runs this CLI, reads the listed paths,
then calls view_file on each to actually see the content.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(add_completion=False, help=__doc__)

_SUPPORTED_SUFFIXES = {".pdf", ".docx"}


def _parse_pages(spec: Optional[str]) -> tuple[int, int]:
    """Return (start, end) inclusive page range. end=-1 means 'until last'."""
    if not spec:
        return (1, -1)
    if "-" not in spec:
        try:
            p = int(spec)
            if p < 1:
                raise ValueError
            return (p, p)
        except ValueError:
            raise typer.BadParameter(f"Invalid page spec {spec!r} (use 1-5 or single integer)")
    try:
        start_s, end_s = spec.split("-", 1)
        start, end = int(start_s), int(end_s)
        if start < 1 or end < start:
            raise ValueError
        return (start, end)
    except ValueError:
        raise typer.BadParameter(f"Invalid page range {spec!r}. Examples: 1-5, 3")


def _render_pdf(path: Path, page_range: tuple[int, int], dpi: int) -> list[bytes]:
    import fitz  # PyMuPDF

    doc = fitz.open(str(path))
    try:
        total = doc.page_count
        start, end = page_range
        start = max(1, start)
        end = total if end < 0 else min(end, total)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pngs: list[bytes] = []
        for i in range(start - 1, end):
            pix = doc[i].get_pixmap(matrix=matrix, alpha=False)
            pngs.append(pix.tobytes("png"))
        return pngs
    finally:
        doc.close()


def _render_docx(path: Path, page_range: tuple[int, int], dpi: int) -> list[bytes]:
    """DOCX → PDF via LibreOffice headless → PDF → PNGs via PyMuPDF.

    Requires the `libreoffice` (or `soffice`) binary on PATH. Open-source,
    available on every Linux distro / macOS / Windows — no proprietary deps
    and no rendering watermark. Install:
      Debian/Ubuntu: sudo apt-get install -y libreoffice-writer
      RHEL/Fedora:   sudo dnf install -y libreoffice-writer
      macOS:         brew install --cask libreoffice
    """
    import shutil
    import subprocess
    import tempfile

    libreoffice_bin = shutil.which("libreoffice") or shutil.which("soffice")
    if not libreoffice_bin:
        raise FileNotFoundError(
            "LibreOffice not on PATH — required for DOCX rendering. "
            "Install with: sudo apt-get install -y libreoffice-writer "
            "(Debian/Ubuntu) or `brew install --cask libreoffice` (macOS)."
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        proc = subprocess.run(
            [
                libreoffice_bin,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", tmpdir,
                str(path),
            ],
            capture_output=True,
            timeout=180,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode(errors="replace")[:500]
            raise RuntimeError(f"LibreOffice DOCX→PDF failed: {stderr}")

        pdf_path = Path(tmpdir) / f"{path.stem}.pdf"
        if not pdf_path.exists():
            raise RuntimeError(
                f"LibreOffice ran but did not produce {pdf_path.name}. "
                f"tmpdir contents: {[p.name for p in Path(tmpdir).iterdir()]}"
            )

        # PyMuPDF already does PDF → PNG rendering — reuse it.
        return _render_pdf(pdf_path, page_range, dpi)
    return pngs


@app.command()
def convert(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to a .pdf or .docx file.",
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        "-o",
        help="Output directory (default: ./<basename>-pages/). Created if missing.",
    ),
    dpi: int = typer.Option(
        144,
        "--dpi",
        "-d",
        min=72,
        max=300,
        help="Rendering resolution in DPI.",
    ),
    pages: Optional[str] = typer.Option(
        None,
        "--pages",
        "-p",
        help="Page range (e.g. 1-5) or single page (e.g. 3). Default: all pages.",
    ),
) -> None:
    """Render each page of INPUT_FILE as a PNG. Prints absolute output paths on stdout."""
    suffix = input_file.suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        typer.secho(
            f"Error: unsupported file type {suffix!r}. Supported: {sorted(_SUPPORTED_SUFFIXES)}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    if out is None:
        out = input_file.parent / f"{input_file.stem}-pages"
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    page_range = _parse_pages(pages)

    try:
        if suffix == ".pdf":
            rendered = _render_pdf(input_file, page_range, dpi)
        else:
            rendered = _render_docx(input_file, page_range, dpi)
    except ImportError as e:
        typer.secho(
            f"Error: pymupdf not installed. Reinstall doc-to-image. Details: {e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=3)
    except FileNotFoundError as e:
        # Raised by _render_docx when LibreOffice is missing from PATH.
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=3)
    except Exception as e:
        typer.secho(
            f"Error rendering {input_file.name}: {e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=4)

    if not rendered:
        typer.secho(
            f"Warning: page range {pages!r} produced no pages from {input_file.name}",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(code=0)

    start_page = max(1, page_range[0])
    base = input_file.stem
    for i, png_bytes in enumerate(rendered):
        page_num = start_page + i
        out_path = out / f"{base}-page-{page_num:03d}.png"
        out_path.write_bytes(png_bytes)
        # stdout: one absolute path per line — chainable with `xargs view_file`
        typer.echo(str(out_path))

    typer.secho(
        f"Rendered {len(rendered)} page(s) from {input_file.name} into {out}",
        fg=typer.colors.GREEN,
        err=True,
    )


def main() -> None:  # console_scripts entry point
    app()


if __name__ == "__main__":
    main()
