"""
EPUB → merged HTML for Docling, plus plain-text fallback when Docling yields nothing.

Docling often does not support EPUB directly; we expand the EPUB spine to one UTF-8 HTML
file, then run the same `process_pdf` / `extract_relevant_content` path on that file.
"""
from __future__ import annotations

import ebooklib
from ebooklib import epub
from pathlib import Path

from bs4 import BeautifulSoup

from src.logging_utils import get_logger

log = get_logger(__name__)


def _iter_epub_document_items(book: epub.EpubBook):
    """Yield ITEM_DOCUMENT items in spine order; fall back to all documents if spine is empty."""
    if book.spine:
        for tup in book.spine:
            idref = tup[0] if isinstance(tup, (list, tuple)) else tup
            item = book.get_item_with_id(idref)
            if item is None:
                log.debug("Spine idref %r not found in manifest; skipping.", idref)
                continue
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                yield item
    else:
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                yield item


def _decode_item_content(raw: bytes) -> str:
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def epub_to_merged_html(epub_path: Path, out_html: Path) -> None:
    """
    Read an EPUB and write a single HTML file (ordered spine) for Docling.

    Strips scripts; keeps body content from each XHTML/HTML document.
    """
    book = epub.read_epub(str(epub_path))
    bodies: list[str] = []

    for item in _iter_epub_document_items(book):
        raw = item.get_content()
        if not raw:
            continue
        html = _decode_item_content(raw)
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        body = soup.body
        if body:
            bodies.append(body.decode_contents())
        else:
            bodies.append(soup.get_text("\n\n", strip=False))

    if not bodies:
        raise ValueError(f"No HTML content extracted from EPUB: {epub_path}")

    merged = (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head><meta charset="utf-8"/>'
        f"<title>{epub_path.stem}</title></head><body>\n"
        + "\n<hr/>\n".join(bodies)
        + "\n</body></html>"
    )
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(merged, encoding="utf-8")


def epub_to_cached_html(epub_path: Path, cache_dir: Path) -> Path:
    """
    Return path to merged HTML for this EPUB. Rebuild if the EPUB is newer than the cache.
    """
    out_dir = cache_dir / "epub_html"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_html = out_dir / f"{epub_path.stem}.html"

    need_build = True
    if out_html.exists():
        try:
            need_build = epub_path.stat().st_mtime > out_html.stat().st_mtime
        except OSError:
            need_build = True

    if need_build:
        log.info("Converting EPUB → HTML: %s → %s", epub_path.name, out_html.name)
        epub_to_merged_html(epub_path, out_html)
    else:
        log.info("Using cached EPUB→HTML: %s", out_html)

    return out_html


def html_file_to_plain_text(html_path: Path) -> str:
    """
    Strip tags and return readable plain text (fallback when Docling returns no structure).
    """
    raw = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw, "lxml")
    for tag in soup(["script", "style", "nav"]):
        tag.decompose()
    text = soup.get_text("\n\n", strip=True)
    return text
