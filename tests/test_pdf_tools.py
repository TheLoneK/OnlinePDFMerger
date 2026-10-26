import io
import sys
import unittest
from pathlib import Path

import pikepdf
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pdf_tools import (  # noqa: E402
    ALGORITHMS,
    PdfToolError,
    PermissionSet,
    build_filename,
    decrypt_pdf,
    encrypt_pdf,
    inspect_pdf,
    merge_pdfs,
    parse_range,
)


def make_pdf(pages: int = 2) -> bytes:
    pdf = pikepdf.new()
    for _ in range(pages):
        pdf.add_blank_page()
    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue()


def page_count(data: bytes, password: str = "") -> int:
    with pikepdf.open(io.BytesIO(data), password=password) as pdf:
        return len(pdf.pages)


def is_encrypted(data: bytes) -> bool:
    return PdfReader(io.BytesIO(data)).is_encrypted


class MergeTests(unittest.TestCase):
    def test_parse_range(self):
        self.assertIsNone(parse_range("  ", 5))
        self.assertEqual(parse_range("1-3, 5", 5), [0, 1, 2, 4])
        for bad in ("0", "6", "3-2", "x"):
            with self.assertRaises(ValueError):
                parse_range(bad, 5)

    def test_build_filename(self):
        self.assertEqual(build_filename(""), "combined_document.pdf")
        self.assertEqual(build_filename("a/b"), "a_b.pdf")
        self.assertEqual(build_filename("x.PDF"), "x.PDF")

    def test_merge(self):
        merged = merge_pdfs([("a.pdf", make_pdf(3), "1-2"), ("b.pdf", make_pdf(2), "")])
        self.assertEqual(page_count(merged), 4)

    def test_merge_rejects_protected_files(self):
        locked = encrypt_pdf(make_pdf(), "secret")
        with self.assertRaisesRegex(PdfToolError, "password protected"):
            merge_pdfs([("a.pdf", make_pdf(), ""), ("locked.pdf", locked, "")])

        restricted = encrypt_pdf(make_pdf(), "", "owner", PermissionSet(copy=False))
        with self.assertRaisesRegex(PdfToolError, "password protected"):
            merge_pdfs([("restricted.pdf", restricted, "")])


class SecurityTests(unittest.TestCase):
    def test_round_trip_every_algorithm(self):
        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                locked = encrypt_pdf(make_pdf(), "open", "owner", algorithm=algorithm)
                info = inspect_pdf(locked)
                self.assertTrue(info.encrypted and info.needs_password)
                with self.assertRaises(pikepdf.PasswordError):
                    pikepdf.open(io.BytesIO(locked))

                unlocked = decrypt_pdf(locked, "open")
                self.assertFalse(is_encrypted(unlocked))
                self.assertEqual(page_count(unlocked), 2)

    def test_owner_password_defaults_to_open_password(self):
        locked = encrypt_pdf(make_pdf(), "secret", permissions=PermissionSet(print=False))
        with pikepdf.open(io.BytesIO(locked), password="secret") as pdf:
            self.assertTrue(pdf.owner_password_matched)
        self.assertFalse(is_encrypted(decrypt_pdf(locked, "secret")))

    def test_wrong_or_missing_password_is_rejected(self):
        locked = encrypt_pdf(make_pdf(), "right")
        with self.assertRaisesRegex(PdfToolError, "incorrect"):
            decrypt_pdf(locked, "wrong")
        with self.assertRaisesRegex(PdfToolError, "Enter"):
            decrypt_pdf(locked, "")

    def test_restrictions_need_permissions_password(self):
        perms = PermissionSet(print=False, copy=False)
        locked = encrypt_pdf(make_pdf(), "open", "owner", perms)

        # The open password alone must not lift restrictions it doesn't own.
        with self.assertRaisesRegex(PdfToolError, "permissions password"):
            decrypt_pdf(locked, "open")
        self.assertFalse(is_encrypted(decrypt_pdf(locked, "owner")))

    def test_restriction_only_file(self):
        locked = encrypt_pdf(make_pdf(), "", "owner", PermissionSet(modify=False))
        info = inspect_pdf(locked)
        self.assertTrue(info.encrypted and not info.needs_password and info.restricted)

        with self.assertRaises(PdfToolError):
            decrypt_pdf(locked, "")
        with self.assertRaisesRegex(PdfToolError, "incorrect"):
            decrypt_pdf(locked, "guess")
        self.assertFalse(is_encrypted(decrypt_pdf(locked, "owner")))

    def test_permissions_are_applied(self):
        perms = PermissionSet(print=False, copy=False, modify=True, annotate=False, fill_forms=True, assemble=False)
        locked = encrypt_pdf(make_pdf(), "open", "owner", perms)
        with pikepdf.open(io.BytesIO(locked), password="open") as pdf:
            self.assertEqual(PermissionSet.from_pikepdf(pdf.allow), perms)

    def test_unprotected_and_already_protected_inputs(self):
        with self.assertRaisesRegex(PdfToolError, "isn't password protected"):
            decrypt_pdf(make_pdf(), "anything")
        locked = encrypt_pdf(make_pdf(), "secret")
        with self.assertRaisesRegex(PdfToolError, "already password protected"):
            encrypt_pdf(locked, "new")
        with self.assertRaises(PdfToolError):
            encrypt_pdf(make_pdf(), "", "")

    def test_garbage_input(self):
        with self.assertRaisesRegex(PdfToolError, "Could not read"):
            inspect_pdf(b"not a pdf")


if __name__ == "__main__":
    unittest.main()
