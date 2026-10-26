"""Streamlit app with a few PDF tools: merge, add a password, remove a password.

The PDF logic lives in pdf_tools.py; this file is only the UI.
(The file keeps its original name because the Streamlit deployment points at it.)
"""

from pathlib import Path

import streamlit as st

from pdf_tools import (
    ALGORITHMS,
    DEFAULT_ALGORITHM,
    DEFAULT_FILENAME,
    PERMISSION_LABELS,
    PdfToolError,
    PermissionSet,
    build_filename,
    decrypt_pdf,
    encrypt_pdf,
    inspect_pdf,
    merge_pdfs,
)


def stem(file_name: str) -> str:
    return Path(file_name).stem


def show_file_status(uploaded) -> None:
    """Tell the user whether the uploaded PDF is already protected."""
    try:
        info = inspect_pdf(uploaded.getvalue())
    except PdfToolError as e:
        st.error(str(e))
        return
    if info.needs_password:
        st.info("🔒 This PDF needs a password to open.")
    elif info.encrypted and info.restricted:
        st.info("🔒 This PDF opens without a password but has permission restrictions.")
    elif info.encrypted:
        st.info("🔒 This PDF is encrypted.")
    else:
        st.caption("This PDF is not password protected.")


def merge_tab() -> None:
    st.write("Upload your PDFs, set custom page ranges, and merge them.")
    uploaded_files = st.file_uploader(
        "Choose PDF files", type="pdf", accept_multiple_files=True, key="merge_files"
    )
    if not uploaded_files:
        return

    st.subheader("Configure Your PDFs")
    configs = []
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
        configs.append((file.name, file.getvalue(), page_range))

    st.divider()
    st.subheader("Final Output Settings")
    filename = build_filename(
        st.text_input("Name your merged PDF file:", value=DEFAULT_FILENAME, key="merge_name")
    )

    if st.button("Merge & Download PDF", type="primary"):
        with st.spinner("Processing your PDFs..."):
            try:
                merged = merge_pdfs(configs)
            except PdfToolError as e:
                st.error(str(e))
            else:
                st.success("🎉 Merging complete!")
                st.download_button(
                    label="⬇️ Download Combined PDF",
                    data=merged,
                    file_name=filename,
                    mime="application/pdf",
                )


def add_password_tab() -> None:
    st.write("Lock a PDF so it needs a password to open.")
    uploaded = st.file_uploader("Choose a PDF", type="pdf", key="lock_file")
    if not uploaded:
        return
    show_file_status(uploaded)

    open_pw = st.text_input("Open password", type="password", key="lock_pw")
    confirm_pw = st.text_input("Confirm open password", type="password", key="lock_pw_confirm")

    with st.expander("Advanced: restrict what readers can do"):
        st.caption(
            "Restrictions only hold if you set a separate permissions password. "
            "Anyone with the permissions password gets full access. Note that "
            "restrictions are honoured by well-behaved PDF readers but aren't real "
            "protection on their own; the open password is what keeps content private."
        )
        perms_pw = st.text_input("Permissions password (optional)", type="password", key="lock_owner_pw")
        st.markdown("**Allow readers to:**")
        cols = st.columns(2)
        allowed = {
            name: cols[i % 2].checkbox(label, value=True, key=f"perm_{name}")
            for i, (name, label) in enumerate(PERMISSION_LABELS.items())
        }
        algorithm = st.selectbox(
            "Encryption", list(ALGORITHMS), index=list(ALGORITHMS).index(DEFAULT_ALGORITHM)
        )

    permissions = PermissionSet(**allowed)
    if permissions.restricted and not perms_pw:
        st.warning("You've set restrictions without a permissions password, so they won't take effect.")

    filename = build_filename(
        st.text_input("Name the protected file:", value=f"{stem(uploaded.name)}_protected", key="lock_name")
    )

    if st.button("Add Password", type="primary"):
        if open_pw != confirm_pw:
            st.error("The open passwords don't match.")
            return
        if not open_pw and not perms_pw:
            st.error("Enter an open password.")
            return
        with st.spinner("Encrypting..."):
            try:
                locked = encrypt_pdf(uploaded.getvalue(), open_pw, perms_pw, permissions, algorithm)
            except PdfToolError as e:
                st.error(str(e))
                return
        st.success("🔒 Password added. Keep the password somewhere safe; it can't be recovered.")
        st.download_button(
            label="⬇️ Download Protected PDF",
            data=locked,
            file_name=filename,
            mime="application/pdf",
        )


def remove_password_tab() -> None:
    st.write(
        "Save an unlocked copy of a PDF you have the password for. "
        "The correct password is required; this tool can't bypass or recover one."
    )
    uploaded = st.file_uploader("Choose a protected PDF", type="pdf", key="unlock_file")
    if not uploaded:
        return
    show_file_status(uploaded)

    password = st.text_input(
        "Password",
        type="password",
        key="unlock_pw",
        help="The open password. If the file has editing or printing restrictions, "
        "use its permissions password instead.",
    )
    filename = build_filename(
        st.text_input("Name the unlocked file:", value=f"{stem(uploaded.name)}_unlocked", key="unlock_name")
    )

    if st.button("Remove Password", type="primary"):
        with st.spinner("Unlocking..."):
            try:
                unlocked = decrypt_pdf(uploaded.getvalue(), password)
            except PdfToolError as e:
                st.error(str(e))
                return
        st.success("🔓 Password removed.")
        st.download_button(
            label="⬇️ Download Unlocked PDF",
            data=unlocked,
            file_name=filename,
            mime="application/pdf",
        )


st.set_page_config(page_title="Levon's PDF Tools", page_icon="📄", layout="centered")
st.title("📄 Levon's PDF Tools")
st.caption("Files are processed in memory and never saved on the server.")

merge, add_pw, remove_pw = st.tabs(["Merge PDFs", "Add Password", "Remove Password"])
with merge:
    merge_tab()
with add_pw:
    add_password_tab()
with remove_pw:
    remove_password_tab()
