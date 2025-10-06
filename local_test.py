from rag_project.documents.utils.text_extraction import DocumentExtractor
import time

doc_path = "rag_project/media/docs/Bando_Ministero_della_giustizia_-_2970.pdf"
with open(doc_path, "rb") as f:
    doc_bytes = f.read()
doc_extractor = DocumentExtractor(doc_bytes)
#start_time = time.time()
#toc = doc_extractor.extract_toc()
#chunks = doc_extractor.extract_text()
#full_text = " ".join(chunk.page_content for chunk in chunks)
#
## Altri metadati
#language = doc_extractor.detect_language(full_text)
#reading_time = doc_extractor.estimate_reading_time(full_text)
#page_numbers = doc_extractor.page_count
#words_count = doc_extractor.get_words_count(full_text)
#images_extracted = doc_extractor.extract_images()
dfs_extracted, jsons_extracted = doc_extractor.extract_tables(doc_bytes, min_words_in_row=1, save_tables_to_csv=True)

print(jsons_extracted)
