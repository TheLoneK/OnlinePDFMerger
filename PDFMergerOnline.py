import streamlit as st
from pypdf import PdfWriter, PdfReader
import io

st.set_page_config(page_title="Pro PDF Merger", page_icon="📄", layout="centered")
st.title("📄 Pro PDF Joiner & Ranger")
st.write("Upload your PDFs, set custom page ranges, and merge them securely.")

# 1. File Upload Component
uploaded_files = st.file_uploader("Choose PDF files", type="pdf", accept_multiple_files=True)

def parse_range(range_str):
    if not range_str.strip(): 
        return None
    pages = []
    try:
        for part in range_str.split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                pages.extend(range(start, end + 1))
                # Streamlit UI uses 1-based index, convert to 0-based index for pypdf
                pages = [p - 1 for p in pages]
            else:
                pages.append(int(part) - 1)
        return pages
    except:
        return "Error"

if uploaded_files:
    st.subheader("Configure Your PDFs")
    
    # Store configurations
    pdf_configs = []
    
    # Display each uploaded file with a page range input field
    for i, file in enumerate(uploaded_files):
        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown(f"**{i+1}. {file.name}**")
        with col2:
            page_range = st.text_input(
                "Page Range (e.g., 1-3, 5)", 
                key=f"range_{i}", 
                placeholder="Leave blank for ALL"
            )
        pdf_configs.append({"file": file, "range_str": page_range})

    st.markdown("---")
    
    # 2. Merge Action Button
    if st.button("Merge & Download PDF", type="primary"):
        merger = PdfWriter()
        error_flag = False
        
        with st.spinner("Processing your PDFs..."):
            for config in pdf_configs:
                # Read file directly from browser memory buffer
                file_bytes = config["file"].read()
                pdf_reader = io.BytesIO(file_bytes)
                
                page_list = parse_range(config["range_str"])
                
                if page_list == "Error":
                    st.error(f"Invalid page range format for {config['file'].name}")
                    error_flag = True
                    break
                    
                try:
                    if page_list:
                        merger.append(pdf_reader, pages=page_list)
                    else:
                        merger.append(pdf_reader)
                except Exception as e:
                    st.error(f"Error processing {config['file'].name}: {e}")
                    error_flag = True
                    break
            
            if not error_flag:
                # Output merged file to a memory buffer for user download
                output_pdf = io.BytesIO()
                merger.write(output_pdf)
                merger.close()
                output_pdf.seek(0)
                
                st.success("🎉 Merging complete!")
                st.download_button(
                    label="⬇️ Download Combined PDF",
                    data=output_pdf,
                    file_name="combined_document.pdf",
                    mime="application/pdf"
                )