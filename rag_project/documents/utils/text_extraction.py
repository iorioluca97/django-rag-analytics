
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import Any, Dict, List, Optional
import fitz
from rag_project.settings import OPENAI_API_KEY
from .logger import logger
from PIL import Image
import io
import re
from collections import defaultdict, Counter
import base64
import pdfplumber
import json
import re
import ast

class DocumentExtractor:
    def __init__(self, document_bytes: bytes):
        """
        Initializes the DocumentExtractor class.
        This class is responsible for extracting text, images, and metadata from PDF documents.
        """
        self.fitz_doc = fitz.open(stream=document_bytes, filetype="pdf")
        self.page_count = self.fitz_doc.page_count

    def get_words_count(self, text: str) -> int:
        """
        Counts the number of words in a given text.

        Args:
            text (str): The input text to be processed.

        Returns:
            int: The number of words in the text.
        """
        if not text:
            return 0
        words = text.split()
        return len(words)

    def extract_tables(self) -> List[Dict[str, Any]]:
        """
        Extracts tables from the document.
        Currently, this method is a placeholder and does not implement actual table extraction.
        
        Returns:
            List[Dict[str, Any]]: An empty list as a placeholder for future table extraction logic.
        """
        # Crea un file temporaneo

        with pdfplumber.open(io.BytesIO(self.fitz_doc.write())) as pdf:
            logger.debug(f"Extracting tables from {len(pdf.pages)} pages.")
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        logger.debug(row)
            return []
        
    def extract_text(self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200) -> List[Document]:
        full_text = ""

        for page in self.fitz_doc:
            full_text += page.get_text()
            full_text += "\n"  # separatore opzionale tra pagine

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        return text_splitter.create_documents([full_text])
       
    def extract_images(self):
        """
        Given raw bytes, extracts images from the document.
        Args:
            raw_bytes (bytes): The raw bytes of the document.
        Returns:
            List[bytes]: A list of bytes representing the extracted images.
        """
        images = []
        try:
            for page_num, page in enumerate(self.fitz_doc):
                page_images = self._process_page_images(self.fitz_doc, page, page_num)
                images.extend(page_images)
        except Exception as e:
            logger.error(f"Error extracting images: {str(e)}")
            return []

        logger.debug(f"Extracted {len(images)} images from the document.")
        logger.debug(f"Image Keys: {images[0].keys() if images else 'No images found'}")
        return images
    
    def extract_toc(self):
        toc = self.fitz_doc.get_toc()
        if toc:
            logger.debug(f" TOC {toc}.")
            return toc

        headings = self._extract_headings_heuristic(self.fitz_doc)
        structured_toc = self._generate_structured_toc(headings)
        return self._validate_with_llm(structured_toc)

    def _extract_headings_heuristic(self, doc):
        font_stats = []
        raw_headings = []

        # Start from the second page to avoid the first page which is often a cover
        for page_num in range(1, len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            size = round(span["size"], 1)
                            font_stats.append(size)
                            text = span["text"].strip()

                            if not text or len(text) < 4:
                                continue

                            is_bold = "bold" in span["font"].lower()
                            is_italic = "italic" in span["font"].lower() or "oblique" in span["font"].lower()
                            is_caps = text.isupper()
                            is_title_like = bool(re.match(r'^[A-Z].*', text)) and len(text.split()) < 12
                            # Determina la dimensione del font più usata (probabile corpo del testo)
                            common_font_size = Counter(font_stats).most_common(1)[0][0]

                            if self._is_valid_heading(text) and (is_bold or is_caps or size > common_font_size) and not is_italic:
                                raw_headings.append({
                                    "text": text,
                                    "page": page.number + 1,
                                    "size": size,
                                    "font": span["font"],
                                    "is_bold": is_bold,
                                    "is_italic": is_italic,
                                    "is_caps": is_caps,
                                    "is_title_like": is_title_like
                                })

        # Filtra titoli basati su euristica migliorafta
        headings = [
            h for h in raw_headings
            if (h["size"] > common_font_size or (h["is_bold"] and h["is_title_like"])) and not h["is_italic"]
        ]
        return headings

    def _is_valid_heading(self, text):
        if len(text.split()) > 12:
            return False
        if re.search(r'(www\.|http[s]?:)', text.lower()):
            return False
        if re.match(r'^[a-z]', text.strip()):
            return False
        return True

    def _generate_structured_toc(self, headings):
        if not headings:
            return []

        # Ordina per pagina e dimensione del font
        headings_sorted = sorted(headings, key=lambda h: (h["page"], -h["size"]))

        # Determina gerarchie di font (1-3 livelli) in base a dimensioni uniche
        unique_sizes = sorted({h["size"] for h in headings_sorted}, reverse=True)
        size_to_level = {size: idx + 1 for idx, size in enumerate(unique_sizes[:3])}

        toc = []
        for heading in headings_sorted:
            level = size_to_level.get(heading["size"], 3)
            toc.append({
                "level": level,
                "text": heading["text"],
                "page": heading["page"]
            })
        return toc
    
    def _validate_with_llm(self, toc: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validates the generated Table of Contents (TOC) with an LLM.
        
        Args:
            toc (List[Dict[str, Any]]): The generated TOC to validate.
        
        Returns:
            List[Dict[str, Any]]: The validated TOC.
        """
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        try:
            logger.debug(f"Validating TOC with LLM: {toc}")
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                {"role": "system", "content": "You are a helpful assistant that validates Table of Contents."},
                {"role": "user", "content": f"""
                Answer only with the validated Table of Contents without any additional text.
                Remove any duplicated entries.
                If the TOC is not correct, fix it.
                 
                For example, if the TOC contains 2 headers very similar, like:
                [{{'level': 1, 'text': 'First Header', 'page': 2}},
                ...
                {{'level': 2, 'text': 'First Header', 'page': 3}}]
                you should remove the second one, because it is a duplicate, indipendent of the level.
                 
                This is the output desired by the user:
                
                [{{'level': 1, 'text': 'First Header', 'page': 2}},...]

                This is the Table of Contents that may be incorrect:
                {toc}
                """}
                ],
                temperature=0
            )

            validated_raw = response.choices[0].message.content
            logger.debug(f"Raw Validated TOC: {validated_raw}")

            # Strip markdown ```json code block markers
            # Remove code block markers
            cleaned = re.sub(r"^```json\s*|\s*```$", "", validated_raw.strip())

            # Use `ast.literal_eval` to safely evaluate Python-style dict/list strings
            try:
                # Convert the cleaned Python-style list of dicts to actual Python objects
                toc_python = ast.literal_eval(cleaned)
                # Now serialize to proper JSON
                validated_toc = json.loads(json.dumps(toc_python))
            except (ValueError, SyntaxError) as e:
                logger.error(f"Error converting TOC to valid JSON: {e}")
                raise

            logger.debug(f"Validated TOC: {validated_toc}")
            return validated_toc

        except Exception as e:
            logger.error(f"Error validating TOC with LLM: {str(e)}")
            return toc

    def _process_page_images(self, doc, page, page_num: int) -> List[Dict]:
            """
            Process all images in a single page.

            Args:
                doc: The PyMuPDF document object.
                page: The page object.
                page_num (int): The page number.

            Returns:
                List[Dict]: A list of dictionaries containing image metadata.
            """
            page_images = []
            loaded_page = doc.load_page(page_num)
            page_dims = loaded_page.get_text("dict")
            page_area = round(float(page_dims["width"]) * float(page_dims["height"]))

            for img_idx, img_info in enumerate(
                page.get_image_info(hashes=True, xrefs=True)
            ):
                image_data = self._extract_single_image(
                    doc, img_info, page_num, img_idx, page_area, page
                )
                if image_data:
                    page_images.append(image_data)

            return page_images

    def _extract_single_image(
        self, doc, img_info, page_num: int, img_idx: int, page_area: float, page
    ) -> Optional[Dict]:
        """
        Extract and process a single image if it meets criteria.

        Args:
            doc: The PyMuPDF document object.
            img_info: The image information dictionary.
            page_num (int): The page number.
            img_idx (int): The image index.
            page_area (float): The area of the page.
            page: The page object.
        """
        try:
            xref = img_info["xref"]
            if xref == 0:
                return None

            base_image = doc.extract_image(xref)
            if not base_image:
                return None

            if self._is_all_black(base_image["image"]):
                return None

            bbox = fitz.Rect(img_info["bbox"])
            image_area = round(bbox.width * bbox.height)

            # Skip images that don't meet size criteria
            if not self._is_valid_image(image_area, page_area, page, bbox):
                return None

            return {
                "base64_data": base64.b64encode(base_image["image"]).decode(),
                "filename": f"page{page_num}_img{img_idx}.{base_image['ext']}",
                "format": base_image["ext"],
                "page_number": page_num,
                "size": f"{base_image['width']}x{base_image['height']}"
           }


        except Exception as e:
            logger.error(
                f"Error processing image {img_idx} on page {page_num}: {str(e)}"
            )
            return None
    
    def _is_all_black(self, img_bytes: bytes, threshold: float = 0.98) -> bool:
        """
        Check if an image is all black or mostly black.

        Args:
            img_bytes (bytes): The image content in bytes.
            threshold (float): The threshold for determining if the image is black.

        Returns:
            True if the image is (mostly) black.
        """
        with Image.open(io.BytesIO(img_bytes)) as img:
            img = img.convert("L")  # Convert to grayscale
            pixels = list(img.getdata())
            total_pixels = len(pixels)

            black_pixels = sum(1 for p in pixels if p < 10)  # Tolerance for near-black
            black_ratio = black_pixels / total_pixels

            return black_ratio >= threshold

    def _is_valid_image(
        self,
        image_area: int,
        page_area: int,
        page,
        bbox: dict,
        percentage_threshold: float = 0.05,
        header_pct: float = 0.1,
        footer_pct: float = 0.1,
    ) -> bool:
        """
        Check if image area is greater than the threshold percentage of the page area
        and is not in the header/footer zones.

        Args:
            image_area: Area of the image.
            page_area: Area of the page.
            page: The page object.
            bbox: Bounding box of the image.
            percentage_threshold: Percentage threshold for image size.
            header_pct: Percentage of the page height for header zone.
            footer_pct: Percentage of the page height for footer zone.

        Returns:
            True if the image is valid (size and position).
        """
        threshold = page_area * percentage_threshold
        is_bigger_enough = image_area >= threshold

        page_height = page.rect.height
        header_limit = header_pct * page_height
        footer_limit = (1 - footer_pct) * page_height

        # TRUE if the image is NOT in header or footer
        is_in_the_middle = bbox.y0 >= header_limit and bbox.y1 <= footer_limit

        return is_bigger_enough and is_in_the_middle

    def estimate_reading_time(self, text: str, wpm: int = 200) -> int:
        """
        Calculates the estimated reading time for a given text.
        Args:
            text (str): The input text to be processed.
            wpm (int): Words per minute for reading speed. Default is 200.
        Returns:
            int: The estimated reading time in minutes.
        """
        if not text:
            return 0
        words = len(text.split())
        reading_time = words / wpm
        return max(1, round(reading_time))

    def detect_language(self, text: str) -> str:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0  # rende il risultato deterministico

        full_text = text.replace("\n", " ").replace("\r", " ").strip()
        if not full_text:
            logger.warning("Empty text provided for language detection.")
            return "???"
        
        mapping = {
            "en": "INGLESE",
            "it": "ITALIANO",
            "fr": "FRANCESE",
            "es": "SPAGNOLO",
            "de": "TEDESCO",
            "pt": "PORTOGHESE",
        }
        try:
            lang_code = detect(full_text)
            language = mapping.get(lang_code, "ALTRO")
            logger.debug(f"Detected language: {language} ({lang_code})")
            return language
        except Exception as e:
            logger.error(f"Error detecting language: {e}")
            return "???"
