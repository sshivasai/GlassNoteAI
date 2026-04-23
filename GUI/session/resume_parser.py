import os
from pathlib import Path


def extract_text(file_path: str) -> str:
    """
    Extract plain text from PDF or DOCX file.
    Returns empty string on failure.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(path)
    elif suffix in (".docx", ".doc"):
        return _extract_docx(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Use PDF or DOCX.")


def _extract_pdf(path: Path) -> str:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))
        pages = []
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                pages.append(text.strip())
        doc.close()
        return "\n\n".join(pages)
    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: pip install pymupdf")
    except Exception as e:
        raise RuntimeError(f"Failed to extract PDF: {e}")


def _extract_docx(path: Path) -> str:
    try:
        from docx import Document
        doc = Document(str(path))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except ImportError:
        raise ImportError("python-docx not installed. Run: pip install python-docx")
    except Exception as e:
        raise RuntimeError(f"Failed to extract DOCX: {e}")