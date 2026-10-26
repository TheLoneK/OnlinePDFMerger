"""PDF logic for the Streamlit app, kept free of UI code so it can be tested.

Everything works on bytes in memory; nothing is written to disk.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import pikepdf
from pypdf import PdfReader, PdfWriter

DEFAULT_FILENAME = "combined_document"

# Display name -> (security handler revision, use AES). Strongest first.
ALGORITHMS: dict[str, tuple[int, bool]] = {
    "AES-256 (recommended)": (6, True),
    "AES-128": (4, True),
    "RC4-128 (legacy, for very old readers)": (3, False),
}
DEFAULT_ALGORITHM = next(iter(ALGORITHMS))


class PdfToolError(ValueError):
    """A problem the user can act on, with a message suitable for display."""


# --------------------------------------------------------------------------- merge


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


def build_filename(name: str, default: str = DEFAULT_FILENAME) -> str:
    """Return a safe download name that ends in .pdf."""
    name = name.strip().replace("/", "_").replace("\\", "_") or default
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def merge_pdfs(configs: list[tuple[str, bytes, str]]) -> bytes:
    """Merge (file_name, data, range_str) entries into one PDF.

    Raises PdfToolError with a user-facing message on the first failure.
    """
    writer = PdfWriter()
    try:
        for name, data, range_str in configs:
            try:
                reader = PdfReader(io.BytesIO(data))
            except Exception as e:
                raise PdfToolError(f"Could not read {name}: {e}") from e

            # Encrypted files (including ones that open without a password but
            # carry permission restrictions) must be unlocked by their owner first.
            if reader.is_encrypted:
                raise PdfToolError(
                    f"{name} is password protected. Remove its password on the "
                    "Remove Password tab first, then merge the unlocked copy."
                )

            try:
                pages = parse_range(range_str, len(reader.pages))
            except ValueError as e:
                raise PdfToolError(f"Invalid page range for {name}: {e}") from e

            try:
                writer.append(reader, pages=pages)
            except Exception as e:
                raise PdfToolError(f"Error processing {name}: {e}") from e

        output = io.BytesIO()
        writer.write(output)
    finally:
        writer.close()

    return output.getvalue()


# ------------------------------------------------------------------------ security


@dataclass
class PermissionSet:
    """What a reader may do when they open the file with the open password."""

    print: bool = True
    copy: bool = True
    modify: bool = True
    annotate: bool = True
    fill_forms: bool = True
    assemble: bool = True

    def to_pikepdf(self) -> pikepdf.Permissions:
        return pikepdf.Permissions(
            print_lowres=self.print,
            print_highres=self.print,
            extract=self.copy,
            # Screen readers need text access; never block it.
            accessibility=True,
            modify_other=self.modify,
            modify_annotation=self.annotate,
            modify_form=self.fill_forms,
            modify_assembly=self.assemble,
        )

    @classmethod
    def from_pikepdf(cls, allow: pikepdf.Permissions) -> PermissionSet:
        return cls(
            print=allow.print_lowres or allow.print_highres,
            copy=allow.extract,
            modify=allow.modify_other,
            annotate=allow.modify_annotation,
            fill_forms=allow.modify_form,
            assemble=allow.modify_assembly,
        )

    @property
    def restricted(self) -> bool:
        return not all(vars(self).values())


PERMISSION_LABELS: dict[str, str] = {
    "print": "Print",
    "copy": "Copy text and images",
    "modify": "Edit the document",
    "annotate": "Add comments",
    "fill_forms": "Fill in forms",
    "assemble": "Insert, rotate or delete pages",
}


@dataclass
class PdfInfo:
    encrypted: bool
    needs_password: bool
    restricted: bool = False


def _open(data: bytes, password: str = "") -> pikepdf.Pdf:
    try:
        return pikepdf.open(io.BytesIO(data), password=password)
    except pikepdf.PasswordError:
        if password:
            raise PdfToolError("The password is incorrect.") from None
        raise PdfToolError("This PDF is password protected. Enter its password.") from None
    except pikepdf.PdfError as exc:
        raise PdfToolError(f"Could not read the PDF: {exc}") from None


def inspect_pdf(data: bytes) -> PdfInfo:
    """Report whether a PDF is encrypted, without needing its password."""
    try:
        pdf = _open(data)
    except PdfToolError as exc:
        if "password protected" in str(exc):
            return PdfInfo(encrypted=True, needs_password=True)
        raise
    with pdf:
        if not pdf.is_encrypted:
            return PdfInfo(encrypted=False, needs_password=False)
        return PdfInfo(
            encrypted=True,
            needs_password=False,
            restricted=PermissionSet.from_pikepdf(pdf.allow).restricted,
        )


def _save(pdf: pikepdf.Pdf, encryption: pikepdf.Encryption | bool) -> bytes:
    out = io.BytesIO()
    try:
        pdf.save(out, encryption=encryption)
    except (pikepdf.PdfError, ValueError) as exc:
        raise PdfToolError(f"Could not save the PDF: {exc}") from None
    return out.getvalue()


def encrypt_pdf(
    data: bytes,
    open_password: str,
    permissions_password: str = "",
    permissions: PermissionSet | None = None,
    algorithm: str = DEFAULT_ALGORITHM,
) -> bytes:
    """Return an encrypted copy of an unprotected PDF.

    ``open_password`` is needed to view the file. ``permissions_password``
    unlocks full access regardless of ``permissions``; if blank, the open
    password is reused so restrictions can't be lifted with an empty password.
    """
    if not open_password and not permissions_password:
        raise PdfToolError("Enter an open password, a permissions password, or both.")
    if algorithm not in ALGORITHMS:
        raise PdfToolError(f"Unknown encryption type: {algorithm}")

    if inspect_pdf(data).encrypted:
        raise PdfToolError(
            "This PDF is already password protected. Remove its current password "
            "on the Remove Password tab first, then add a new one."
        )

    revision, aes = ALGORITHMS[algorithm]
    encryption = pikepdf.Encryption(
        user=open_password,
        owner=permissions_password or open_password,
        R=revision,
        aes=aes,
        # pikepdf can only encrypt the XMP metadata stream with AES.
        metadata=aes,
        allow=(permissions or PermissionSet()).to_pikepdf(),
    )
    with _open(data) as pdf:
        return _save(pdf, encryption)


def decrypt_pdf(data: bytes, password: str) -> bytes:
    """Return an unlocked copy of a protected PDF, given its real password.

    This never bypasses protection:
    - an empty or wrong password is rejected;
    - if the file has permission restrictions (no printing, no copying, ...),
      only its permissions (owner) password may remove them. The open password
      alone is accepted only when there are no restrictions to lift.
    """
    info = inspect_pdf(data)
    if not info.encrypted:
        raise PdfToolError("This PDF isn't password protected, so there's nothing to remove.")
    if not password:
        raise PdfToolError("Enter the PDF's password.")

    with _open(data, password) as pdf:
        if not pdf.owner_password_matched:
            if PermissionSet.from_pikepdf(pdf.allow).restricted:
                raise PdfToolError(
                    "That password opens the PDF, but the file also has permission "
                    "restrictions set by a separate permissions password. Enter the "
                    "permissions password to remove its protection."
                )
            if not info.needs_password:
                # The file opens with no password, so the one entered proved nothing.
                raise PdfToolError("The password is incorrect.")
        return _save(pdf, False)
