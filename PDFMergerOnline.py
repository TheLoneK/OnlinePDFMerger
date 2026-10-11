"""Streamlit app for merging PDFs with optional per-file page ranges."""

import io

import streamlit as st
from pypdf import PdfReader, PdfWriter

DEFAULT_FILENAME = "combined_document"


def parse_range(range_str: str, page_count: int) -> list[int] | None:
    """Convert a 1-based range string like "1-3, 5" into 0-based page indices.

    Returns None for a blank string (meaning all pages).
    Raises ValueError for malformed or out-of-bounds input.
    """
    if not range_str.strip():
        return None

    pages: list[int] = []
    for part in range_str.split(","):
        part = part.strip()
        if not part:
            continue
        start_str, sep, end_str = part.partition("-")
        try:
            start = int(start_str)
            end = int(end_str) if sep else start
        except ValueError:
            raise ValueError(f"'{part}' is not a page number or range") from None

        if start < 1 or end > page_count or start > end:
            raise ValueError(f"'{part}' is outside 1-{page_count}")
        pages.extend(range(start - 1, end))

    if not pages:
        raise ValueError("no pages selected")
    return pages


def build_filename(name: str) -> str:
    """Return a safe download name that ends in .pdf."""
    name = name.strip().replace("/", "_").replace("\\", "_") or DEFAULT_FILENAME
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def merge_pdfs(configs: list[tuple]) -> io.BytesIO:
    """Merge (uploaded_file, range_str) pairs into a single PDF buffer.

    Raises ValueError with a user-facing message on the first failure.
    """
    writer = PdfWriter()
    try:
        for file, range_str in configs:
            try:
                reader = PdfReader(io.BytesIO(file.getvalue()))
            except Exception as e:
                raise ValueError(f"Could not read {file.name}: {e}") from e

            try:
                pages = parse_range(range_str, len(reader.pages))
            except ValueError as e:
                raise ValueError(f"Invalid page range for {file.name}: {e}") from e

            try:
                writer.append(reader, pages=pages)
            except Exception as e:
                raise ValueError(f"Error processing {file.name}: {e}") from e

        output = io.BytesIO()
        writer.write(output)
    finally:
        writer.close()

    output.seek(0)
    return output


st.set_page_config(page_title="Levon's PDF Merger", page_icon="📄", layout="centered")
st.title("📄 Levon's PDF Merger")
st.write("Upload your PDFs, set custom page ranges, and merge them securely.")

uploaded_files = st.file_uploader("Choose PDF files", type="pdf", accept_multiple_files=True)

if uploaded_files:
    st.subheader("Configure Your PDFs")

    pdf_configs = []
    for i, file in enumerate(uploaded_files, start=1):
        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown(f"**{i}. {file.name}**")
        with col2:
            page_range = st.text_input(
                "Page Range (e.g., 1-3, 5)",
                key=f"range_{i}",
                placeholder="Leave blank for ALL",
            )
        pdf_configs.append((file, page_range))

    st.divider()
    st.subheader("Final Output Settings")

    filename = build_filename(st.text_input("Name your merged PDF file:", value=DEFAULT_FILENAME))

    if st.button("Merge & Download PDF", type="primary"):
        with st.spinner("Processing your PDFs..."):
            try:
                merged_pdf = merge_pdfs(pdf_configs)
            except ValueError as e:
                st.error(str(e))
            else:
                st.success("🎉 Merging complete!")
                st.download_button(
                    label="⬇️ Download Combined PDF",
                    data=merged_pdf,
                    file_name=filename,
                    mime="application/pdf",
                )
