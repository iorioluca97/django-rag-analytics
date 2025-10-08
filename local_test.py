from rag_project.documents.utils.text_extraction import DocumentExtractor
import time

doc_path = "CV_ITA_30092025.pdf"
with open(doc_path, "rb") as f:
    doc_bytes = f.read()

me = DocumentExtractor(document_bytes=doc_bytes)

results = me.extract(
    # extract_toc=True,
    # extract_images=True,
    # extract_tables=True,
    extract_others=True,
)

print(results.keys())

print(f"other info: {results.get('other_info')}")

# print(f"TOC: {results.get('toc')}")

