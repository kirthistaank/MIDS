"""
src/pdf_utils.py

document_extractor.py lives in the src package alongside this file.
Cache writes to RAG_ingest/cache/.
Data folder is RAG_ingest/data/.
"""
from pathlib import Path
from src.document_extractor import process_pdf, json_to_plaintext
from src.logging_utils import get_logger
from src.epub_to_html import epub_to_cached_html, html_file_to_plain_text

# RAG_ingest/ — one level up from this file (ingest/pdf_utils.py)
_WORKING_ROOT = Path(__file__).resolve().parent.parent
log = get_logger(__name__)


def find_cbt_pdf(data_dir: Path) -> Path:
    """Auto-detect the CBT PDF in data_dir, falling back to the first PDF found."""
    pdfs = list(data_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found in {data_dir}")
    for p in pdfs:
        if "cognitive behavior therapy" in p.name.lower() or "cbt" in p.name.lower():
            return p
    return pdfs[0]


def load_or_extract_text(pdf_path: Path, cache_dir: Path = None) -> str:
    """
    Return cached plaintext if available, otherwise extract and cache it.
    Cache: RAG_ingest/cache/<stem>.txt

    PDFs go through Docling directly. EPUBs are merged to HTML (cache/epub_html/<stem>.html),
    then Docling; if that yields no text, plain text is taken from the merged HTML.

    On failure returns "".
    """
    if cache_dir is None:
        cache_dir = _WORKING_ROOT / "cache"

    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / f"{pdf_path.stem}.txt"

    if cache_file.exists():
        try:
            text = cache_file.read_text(encoding="utf-8")
            log.info(f"Loaded cached text ({len(text):,} chars) from {cache_file}.")
            return text
        except OSError as e:
            log.warning("Could not read cache file %s: %s. Will re-extract.", cache_file, e)

    # EPUB: Docling usually lacks EPUB support — merge to HTML, then Docling; fallback to plain HTML text.
    if pdf_path.suffix.lower() == ".epub":
        try:
            html_path = epub_to_cached_html(pdf_path, cache_dir)
        except Exception as e:
            log.warning("EPUB → HTML failed for %s: %s. Returning empty text.", pdf_path.name, e)
            return ""
        log.info("Extracting EPUB (via HTML): %s ...", pdf_path.name)
        try:
            data = process_pdf(str(html_path))
        except Exception as e:
            log.warning("Docling failed on EPUB-derived HTML for %s: %s.", pdf_path.name, e)
            data = []
        text = ""
        if data:
            text = json_to_plaintext(data)
        if not (text and text.strip()):
            log.warning(
                "Docling produced no usable text from EPUB HTML for %s; using direct HTML text extraction.",
                pdf_path.name,
            )
            try:
                text = html_file_to_plain_text(html_path)
            except Exception as e:
                log.warning("Plain HTML fallback failed for %s: %s.", pdf_path.name, e)
                return ""
        if not (text and text.strip()):
            log.warning("EPUB plaintext is empty for %s. Returning empty text.", pdf_path.name)
            return ""
    else:
        log.info(f"Extracting PDF: {pdf_path} ...")
        try:
            data = process_pdf(str(pdf_path))
            if not data:
                log.warning("PDF produced no extracted content for %s. Returning empty text.", pdf_path.name)
                return ""
            text = json_to_plaintext(data)
            if not (text and text.strip()):
                log.warning("PDF plaintext is empty for %s. Returning empty text.", pdf_path.name)
                return ""
        except Exception as e:
            log.warning("Extraction failed for %s: %s. Returning empty text.", pdf_path.name, e)
            return ""
    try:
        cache_file.write_text(text, encoding="utf-8")
        log.info(f"Cached extracted text → {cache_file}")
    except OSError as e:
        log.warning(f"Could not write cache: {e}")
    return text