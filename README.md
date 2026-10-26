# Online PDF Tools

A small [Streamlit](https://streamlit.io) web app with a few everyday PDF tools.

## Features

- **Merge PDFs**: upload several PDFs and merge them in the order shown, picking pages per file
  with ranges like `1-3, 5` (leave blank to keep all pages) and naming the merged file
- **Add Password**: lock a PDF with an open password (AES-256 by default). Optionally set a separate
  permissions password and restrict printing, copying, editing, comments, form filling or page changes
- **Remove Password**: save an unlocked copy of a PDF *you have the password for*
- Files are processed in memory and never written to disk

### What Remove Password won't do

It never bypasses or guesses a password. The correct password is always required, and if a file
has permission restrictions (no printing, no copying, …) only its permissions password can remove
them; the open password alone is not enough. Protected PDFs can't be merged until they've been
unlocked this way.

### Notes on PDF security

- The **open password** encrypts the file contents; without it the PDF can't be read.
- The **permissions password** and restrictions are honoured by well-behaved PDF readers but aren't
  real protection on their own. Use an open password for anything confidential.
- If the permissions password is left blank, the open password is used for both, which means the
  restrictions won't take effect.

## Running locally

Requires Python 3.10+.

```bash
pip install -r requirements.txt
streamlit run PDFMergerOnline.py
```

The app then opens at <http://localhost:8501>.

## Code layout

- `PDFMergerOnline.py`: the Streamlit UI (keeps its original name because the Streamlit Cloud deployment points at it)
- `pdf_tools.py`: the PDF logic (merging with pypdf, encryption with [pikepdf](https://github.com/pikepdf/pikepdf))
- `tests/`: run with `python -m unittest discover -s tests` (or `python -m pytest`)
