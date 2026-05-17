#============================================================
# MODULE 1: Constants
# ============================================================


import re
import os
import json
import datetime
from pathlib import Path
from docling.document_converter import DocumentConverter
from docling.datamodel.document import DocItemLabel
from src.timing import format_duration
from src.logging_utils import get_logger

log = get_logger(__name__)

# Patterns that signal START of relevant content (matched against SECTION_HEADERs only)
START_HEADING_PATTERNS = [
    r"^chapter\s+1\b",
    r"^chapter\s+one\b",
    r"^introduction\b",
]

# Keywords that signal END of relevant content (matched against SECTION_HEADERs only)
END_HEADING_KEYWORDS = [
    "appendix",
    "references",
    "bibliography",
    "index",
    "glossary",
    "notes",
    "acknowledgments",
    "about the author",
    "about the book",
    "worksheets",
]

# Instead of whitelisting labels to keep, we blacklist labels to skip.
# Anything with a .text attribute that isn't in SKIP_LABELS gets extracted.
# This makes the code work generically across PDFs regardless of how
# Docling labels body text (TEXT vs PARAGRAPH varies by PDF).

SKIP_LABELS = {
    DocItemLabel.TABLE,
    DocItemLabel.PICTURE,
    #DocItemLabel.FIGURE,
    DocItemLabel.DOCUMENT_INDEX,  # index tables — also lack .text
    DocItemLabel.PAGE_HEADER,     # running headers (e.g. chapter name repeated)
    DocItemLabel.PAGE_FOOTER,     # page numbers, copyright lines
    DocItemLabel.FORM,            # form fields
}



# ============================================================
# MODULE 2: Heading matchers
# ============================================================

def _matches_start_heading(text: str) -> bool:
    """True if this SECTION_HEADER marks the start of relevant content."""
    lowered = text.lower().strip()
    return any(re.match(pattern, lowered) for pattern in START_HEADING_PATTERNS)


def _matches_end_heading(text: str) -> bool:
    """
    True if this SECTION_HEADER marks the end of relevant content.
    Only called on Docling SECTION_HEADER elements — never on body text.
    Uses startswith to avoid partial word matches inside a heading like
    'Index of Concepts' still triggers, but 'notes from last week' never will
    because that element won't be a SECTION_HEADER.
    """
    lowered = text.lower().strip()
    return any(lowered.startswith(kw) for kw in END_HEADING_KEYWORDS)



# ============================================================
# MODULE 3: Single-pass extraction (boundaries from headings only)
# ============================================================

def extract_relevant_content(
    pdf_path: str,
    min_paragraph_length: int = 40,
) -> list[dict]:
    """
    Single Docling pass that:
      1. Skips all elements until a START SECTION_HEADER is found
         (chapter 1 / chapter one / introduction)
      2. Extracts content, tracking section headers
      3. Hard-stops the moment an END SECTION_HEADER is found
         (appendix / references / index / etc.)

    Boundary detection is ONLY done on DocItemLabel.SECTION_HEADER elements,
    so body text like 'notes from last week?' never triggers a false stop.
    """
    log.info(f"[Docling] Converting: {os.path.basename(pdf_path)} ...")
    try:
        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        doc = result.document
    except Exception as e:
        log.warning("PDF conversion failed for %s: %s. Returning no content.", os.path.basename(pdf_path), e)
        return []

    relevant_data = []
    current_section = "Unknown"
    in_relevant_section = False   # gate: True only after start heading found
    stopped_early = False

    for element, _level in doc.iterate_items():
        if not element.prov:
            continue

        page_no = element.prov[0].page_no  # Docling: 1-indexed
        label   = element.label

        # ── Skip non-text elements BEFORE accessing .text ────────────────────
        # PictureItem, TableItem etc. have no .text attribute
        if label in SKIP_LABELS:
            continue

        # Safety net: some Docling item types (e.g. TableItem under
        # DocItemLabel.DOCUMENT_INDEX) also lack .text — skip them defensively
        if not hasattr(element, "text"):
            continue

        text = element.text.strip()

        if not text:
            continue

        # ── Only START/STOP logic runs on SECTION_HEADERs ────────────────────
        if label == DocItemLabel.SECTION_HEADER:

            # Not yet in relevant section — look for a start heading
            if not in_relevant_section:
                if _matches_start_heading(text):
                    in_relevant_section = True
                    current_section = text
                    log.info(f"[Boundary] START at page {page_no}: '{text}'")
                    # Fall through so this heading itself is added below
                else:
                    continue   # skip everything before the start heading

            # Already in relevant section — check for end heading
            else:
                if _matches_end_heading(text):
                    if 'notes and references' in text.lower():
                        in_relevant_section = False
                        continue #skip to next section

                    log.info(f"[Boundary] END (hard stop) at page {page_no}: '{text}'")
                    stopped_early = True
                    break      # stop processing entirely
                else:
                    current_section = text   # update section tracker

        # ── Gate: skip body content until start heading is found ─────────────
        if not in_relevant_section:
            continue

        # ── Skip unwanted element types ──────────────────────────────────────
        # Blocklist approach: skip known non-content labels, keep everything
        # else that has .text — works generically across different PDFs
        # regardless of whether body text is PARAGRAPH, TEXT, etc.
        if label in SKIP_LABELS:
            continue

        # ── Drop very short fragments (running headers/footers that slip through)
        if label not in (DocItemLabel.SECTION_HEADER, DocItemLabel.CAPTION) and len(text) < min_paragraph_length:
            continue

        relevant_data.append({
            "text":    text,
            "type":    str(label),
            "page":    page_no,
            "section": current_section,
        })

    log.info(f"[Extract] {len(relevant_data)} elements extracted. Early stop: {stopped_early}")
    return relevant_data


# ============================================================
# MODULE 4: Orchestrator
# ============================================================

def process_pdf(
    pdf_path: str,
    min_paragraph_length: int = 40,
) -> list[dict]:
    """
    Full pipeline — single Docling pass, heading-only boundary detection.
    Returns list of dicts: text, type, page, section.
    On any failure returns [] so callers can handle gracefully.
    """
    log.info("=" * 60)
    log.info(f"Processing: {os.path.basename(pdf_path)}")
    log.info("=" * 60)
    try:
        return extract_relevant_content(
            pdf_path,
            min_paragraph_length=min_paragraph_length,
        )
    except Exception as e:
        log.warning("process_pdf failed for %s: %s. Returning empty list.", os.path.basename(pdf_path), e)
        return []


# ============================================================
# MODULE 5: Notebook inspection helpers
# ============================================================

def preview_results(data: list[dict], n: int = 10):
    """Print first n extracted elements."""
    log.info(f"--- Preview ({min(n, len(data))} of {len(data)} elements) ---")
    for item in data[:n]:
        label = item['type'].split('.')[-1]
        #print(f"  [p{item['page']}] [{label:16s}] [{item['section'][:30]:30s}]  {item['text'][:120]}")
        log.info(f"  [p{item['page']}] [{label:16s}] [{item['section'][:30]:30s}]  {item['text']}")


def summarize_results(data: list[dict]):
    """Print a count summary and section list."""
    from collections import Counter
    if not data:
        log.info("No data extracted.")
        return
    counts  = Counter(item['type'].split('.')[-1] for item in data)
    pages   = sorted({item['page'] for item in data})
    sections = list(dict.fromkeys(
        item['text'] for item in data if item['type'].endswith('SECTION_HEADER')
    ))
    log.info("--- Summary ---")
    log.info(f"  Total elements : {len(data)}")
    log.info(f"  Page range     : p{pages[0]} – p{pages[-1]}")
    log.info(f"  By type        : {dict(counts)}")
    log.info(f"  Sections found : {sections[:15]}{'...' if len(sections) > 15 else ''}")


def debug_all_labels(pdf_path: str, page_no_filter: int = None):
    """
    Dumps EVERY element Docling finds with its label, page, and text preview.
    Use page_no_filter to inspect a specific page (1-indexed).
    This tells you exactly what labels Docling assigns to body text in your PDF
    so you can tune EXTRACTABLE_LABELS correctly.

    Usage:
        debug_all_labels(pdf_path)                  # all pages
        debug_all_labels(pdf_path, page_no_filter=381)  # just page 381
    """
    from collections import Counter
    log.info(f"[Debug] Scanning all elements in: {os.path.basename(pdf_path)}")
    converter = DocumentConverter()
    result    = converter.convert(pdf_path)
    doc       = result.document
    label_counts = Counter()

    for element, _level in doc.iterate_items():
        if not element.prov:
            continue
        page = element.prov[0].page_no
        if page_no_filter and page != page_no_filter:
            continue
        label = element.label
        label_counts[str(label)] += 1
        text_preview = ""
        if hasattr(element, "text"):
            text_preview = element.text.strip()[:120]  # wider preview
        log.info(f"  [p{page:>3}] [{str(label):30s}]  '{text_preview}{'...' if len(text_preview) == 120 else ''}'")

    log.info("--- Label frequency ---")
    for label, count in label_counts.most_common():
        status = "✗ skipped (blocklist)" if any(
            str(l) == label for l in SKIP_LABELS
        ) else "✓ extracted"
        log.info(f"  {label:35s} {count:>4}x   {status}")


def debug_headings(pdf_path: str, max_elements: int = 200):
    """
    Utility to inspect ALL section headings Docling finds in a PDF.
    Useful for tuning START_HEADING_PATTERNS and END_HEADING_KEYWORDS.
    Run this first on a new PDF to see what headings exist.
    """
    log.info(f"[Debug] Scanning headings in: {os.path.basename(pdf_path)}")
    converter = DocumentConverter()
    result    = converter.convert(pdf_path)
    doc       = result.document
    count     = 0
    for element, _level in doc.iterate_items():
        if element.label == DocItemLabel.SECTION_HEADER and element.prov:
            page = element.prov[0].page_no
            log.info(f"  [p{page:>3}] '{element.text.strip()}'")
            count += 1
            if count >= max_elements:
                log.info("  ... (limit reached)")
                break
    log.info(f"[Debug] {count} section headers found.")
    
# This function is called to extrcat raw text along with section info
def json_to_plaintext(data: list[dict]) -> str:
    lines = []
    seen_headers = set()

    for item in data:
        text    = item.get("text", "").strip()
        type_   = item.get("type", "")
        page    = item.get("page", "")

        if type_ == "section_header":
            if text in seen_headers:
                continue                          # skip duplicate headers
            seen_headers.add(text)
            lines.append(f"\n## {text} (p{page})\n")
        else:
            lines.append(text)

    return "\n".join(lines)

# Example usage
if __name__ == "__main__":
    # Initial config 
    pdf_folder = "/Users/kirthi/Documents/UCBerkeley/Capstone/localrag/RAG_ingest/data/"
    pdf_files = list(Path(pdf_folder).glob("*.pdf"))
    """
    pdf_files= ['/Users/kirthi/Documents/UCBerkeley/Capstone/localrag/data/Getting to Yes.pdf',
    '/Users/kirthi/Documents/UCBerkeley/Capstone/localrag/data/Motivational Interviewing - Helping People Change and Grow.pdf',
    '/Users/kirthi/Documents/UCBerkeley/Capstone/localrag/data/Space Framework.pdf',
    '/Users/kirthi/Documents/UCBerkeley/Capstone/localrag/data/Nonviolent Communication - A Language of Life.pdf',
    '/Users/kirthi/Documents/UCBerkeley/Capstone/localrag/data/~$Guide to Rational Living.pdf',
    '/Users/kirthi/Documents/UCBerkeley/Capstone/localrag/data/Difficult Conversations How to Discuss What Matters Most.pdf',
    '/Users/kirthi/Documents/UCBerkeley/Capstone/localrag/data/Cognitive Behavior Therapy - Basics and Beyond.pdf',
    '/Users/kirthi/Documents/UCBerkeley/Capstone/localrag/data/A Guide to Rational Living.pdf']
    """
    #pdf_files= ['/Users/kirthi/Documents/UCBerkeley/Capstone/localrag/data/Cognitive Behavior Therapy - Basics and Beyond.pdf']

    log.info(f"File list to process : {pdf_files}")
    start = datetime.datetime.now()
    log.info("*" * 50)
    log.info(f"Execution Start time: {start}")
    debug = True # Set to True to inspect headings before extraction
    if debug:
        pdf_files = [pdf_files[0]]  # Only debug the first file for speed
        #pdf_file = "data/Cognitive Behavior Therapy - Basics and Beyond.pdf"  # Change this to your PDF
        # # Step 1: inspect headings to tune keywords (optional but recommended)
        debug_headings(pdf_files[0],1000)
        # Inspect a specific page where you know text is missing
        debug_all_labels(pdf_files[0])
        #exit()  # Stop after debugging headings
    # Process a PDF
    
    for pdf_file in pdf_files:

        log.info(f"Processing File : {pdf_file}")
        data = process_pdf(pdf_file)
        
        # Save full texts to JSON file
        pdf_name = os.path.basename(pdf_file).rsplit('.', 1)[0]
        text_storage_path = f"./rawtext_json/{pdf_name}_texts.json"
        os.makedirs("./rawtext_json", exist_ok=True)
        with open(text_storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info(f"Successfully Saved extracted info as JSON file to : {text_storage_path}")
        # Save the sane data as plain text with section headers for easier human inspection
        plaintext = json_to_plaintext(data)
        plaintext_storage_path = f"./rawtext_plain/{pdf_name}_texts.txt"
        os.makedirs("./rawtext_plain", exist_ok=True)
        with open(plaintext_storage_path, 'w', encoding='utf-8') as f:
            f.write(plaintext)
        log.info(f"Successfully Saved extracted info as plain text file to : {plaintext_storage_path}")

        summarize_results(data)
        preview_results(data, n=5)
    end = datetime.datetime.now()
    log.info(f"Execution End time: {end}")
    total_seconds = (end - start).total_seconds()
    log.info(f"Total duration: {format_duration(total_seconds)}")
    log.info("*" * 50)