"""Small, offline PDF renderer shared by previews and device document windows."""

from pathlib import Path
import sys


def render_pdf(path, page_index=0, width=900):
    try:
        import pypdfium2 as pdfium
    except ImportError:
        development_runtime = Path(__file__).resolve().parent / ".build-tools" / "pdf-runtime"
        if development_runtime.is_dir():
            sys.path.append(str(development_runtime))
        import pypdfium2 as pdfium
    document = pdfium.PdfDocument(str(path))
    try:
        page = document[page_index]
        try:
            bitmap = page.render(scale=width / page.get_width())
            try:
                return bitmap.to_pil().copy(), len(document)
            finally:
                bitmap.close()
        finally:
            page.close()
    finally:
        document.close()
