
import os
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import Any, Dict, List, Optional
import fitz
from openai import OpenAI
import yaml
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
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Union
import logging

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
        chunk_size: int = 500,
        chunk_overlap: int = 50) -> List[Document]:
        full_text = ""

        for i, page in enumerate(self.fitz_doc):
            full_text += page.get_text()
            full_text += "\n"  # separatore opzionale tra pagine

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        chunks = text_splitter.split_text(full_text)
        documents = []
        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk,
                metadata={"page": i + 1}
            )
            documents.append(doc)
        return documents

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
            return self._toc_list_to_json(toc)

        toc_text, toc_page_num = self._extract_possible_starting_toc(self.fitz_doc)
        logger.debug(f"Possible TOC at page: {toc_page_num}")
        return self._validate_with_llm(toc_text, toc_page_num)

    def _extract_possible_starting_toc(self, doc):
        toc_page_number = None
        toc_text = None

        # Start from the second page to avoid the first page which is often a cover
        for page_num in range(0, min(10, self.page_count)):
            # Search for a common start of TOC
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if not text.strip():
                continue
            lines = text.splitlines()
            for line in lines:
                if re.match(r'^(Indice|Sommario|Table of Contents|Capitolo)\s*$', line, re.IGNORECASE):
                    toc_page_number = page_num
                    logger.debug(f"Found possible TOC start on page {toc_page_number + 1}: {line.strip()}")
                    break
            if toc_page_number is not None:
                break
        if toc_page_number is None:
            logger.warning("No starting point for TOC found in the first 10 pages.")
            return None, None

        # Extract text from the TOC page
        toc_page = doc.load_page(toc_page_number)
        toc_text = toc_page.get_text("text") 

        return toc_text, toc_page_number
            
    def _toc_list_to_json(self, toc_list):
        return [{"level": level, "text": text.strip(), "page": page} for level, text, page in toc_list]

    def _validate_with_llm(self, toc_text: str, toc_page_num: int) -> List[Dict[str, Any]]:
        """
        Validates the generated Table of Contents (TOC) with an LLM.
        
        Args:
            toc (List[Dict[str, Any]]): The generated TOC to validate.
        
        Returns:
            List[Dict[str, Any]]: The validated TOC.
        """
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        prompt_config = {
            "task": "validate_table_of_contents",
            "output_format": "json_list",
            "output_instructions": [
                "Only return the cleaned Table of Contents as a list of dictionaries.",
                "Do not include any explanatory text, comments, or headings."
            ],
            "rules": [
                "Remove duplicated entries even if they have different levels.",
                "Consider headers duplicated if their text is nearly identical.",
                "Ensure ordering and page numbers are preserved.",
                "Do not generate new headers unless absolutely necessary."
            ],
            "example_input": [
                {"level": 1, "text": "First Header", "page": 2},
                {"level": 2, "text": "First Header", "page": 3}
            ],
            "expected_output": [
                {"level": 1, "text": "First Header", "page": 2}
            ],
            "toc_page_num": toc_page_num if toc_page_num is not None else "Not found",  # Use 0 if no TOC page found
            "toc_text": toc_text.strip() if toc_text else "No text found",

        }


        yaml_prompt = yaml.dump(prompt_config, sort_keys=False, default_flow_style=False)

        full_prompt = (
            "You are a helpful assistant that validates and cleans Table of Contents.\n"
            "You are provided both a structured TOC and images of the document pages where may be the TOC is located.\n"
            "Use both sources to ensure correctness.\n"
            "Please follow the instructions in the following YAML configuration:\n"
            f"```yaml\n{yaml_prompt}```"
        )


        if toc_page_num:
            page_ranges_to_search = range(toc_page_num-1, min(toc_page_num + 4, self.page_count))
        else:
            page_ranges_to_search = range(0, min(5, self.page_count))
        toc_images = self.get_first_n_pages_as_base64_images(n=len(page_ranges_to_search))

        prompt_config["toc_images"] = toc_images  # toc_images is the list of base64 images

        user_content = self.build_multimodal_message(full_prompt, toc_images)

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that validates Table of Contents."},
                {"role": "user", "content": user_content}
                
            ],
            temperature=0
        )

        # Parsing the string result to Python list (assuming model respects the format)
        cleaned_toc = response.choices[0].message.content.strip()        

        # Strip markdown ```json code block markers
        # Remove code block markers
        cleaned = re.sub(r"^```json\s*|\s*```$", "", cleaned_toc.strip())

        # Use `ast.literal_eval` to safely evaluate Python-style dict/list strings
        try:
            # Convert the cleaned Python-style list of dicts to actual Python objects
            toc_python = ast.literal_eval(cleaned)
            # Now serialize to proper JSON
            validated_toc = json.loads(json.dumps(toc_python))
        except (ValueError, SyntaxError) as e:
            logger.error(f"Error converting TOC to valid JSON: {e}")
            return {}

        logger.debug(f"Validated TOC: {validated_toc}")
        return validated_toc

    def get_first_n_pages_as_base64_images(self, n: int = 5) -> list:
        images_base64 = []

        for page_number in range(min(n, len(self.fitz_doc))):
            page = self.fitz_doc.load_page(page_number)
            pix = page.get_pixmap(dpi=150)  

            image_bytes = pix.tobytes("png")
            base64_image = base64.b64encode(image_bytes).decode("utf-8")
            images_base64.append(f"data:image/png;base64,{base64_image}")

        return images_base64

    def build_multimodal_message(self, text: str, base64_images: List[str]) -> List[dict]:
        content = [{"type": "text", "text": text}]
        
        for base64_image in base64_images:
            content.append({
                "type": "image_url",
                "image_url": {"url": base64_image}
            })

        return content

    def _clean_toc(self, toc_str: str) -> str:
        """
        Enhanced TOC cleaning function that handles common PDF extraction issues
        """
        # Parse JSON if it's in JSON format
        try:
            toc_data = json.loads(toc_str)
            if isinstance(toc_data, list):
                return self._clean_json_toc(toc_data)
        except json.JSONDecodeError:
            pass
        
        # Handle plain text TOC
        lines = toc_str.splitlines()
        cleaned = []
        seen = set()
        
        # Common patterns to remove
        garbage_patterns = [
            r'^(indice|sommario|table of contents|capitolo)\s*$',
            r'^information and communication technologies group policy\s*$',
            r'^[\d\.\-\s]*$',  # Only numbers, dots, dashes, spaces
            r'^\s*\.{3,}\s*\d*\s*$',  # Dotted lines with page numbers
            r'^\s*page\s*\d*\s*$',  # Page references
            r'^\.\.\.\.\.*\d*$',  # Multiple dots with optional page number
        ]
        
        for line in lines:
            original_line = line.strip()
            if not original_line:
                continue
                
            # Skip garbage patterns
            is_garbage = False
            for pattern in garbage_patterns:
                if re.match(pattern, original_line.lower()):
                    is_garbage = True
                    break
            
            if is_garbage:
                continue
                
            # Clean the line
            cleaned_line = self._clean_single_toc_line(original_line)
            
            if not cleaned_line:
                continue
                
            # Avoid duplicates
            norm_line = cleaned_line.lower().strip()
            if norm_line in seen or len(norm_line) < 3:
                continue
                
            seen.add(norm_line)
            cleaned.append(cleaned_line)
        
        return '\n'.join(cleaned)

    def _clean_json_toc(self, toc_data: list) -> str:
        """
        Clean TOC data that comes in JSON format
        """
        cleaned = []
        seen = set()
        
        for item in toc_data:
            if not isinstance(item, dict):
                continue
                
            text = item.get('text', '').strip()
            level = item.get('level', 1)
            page = item.get('page', '')
            
            if not text:
                continue
                
            # Skip common garbage entries
            if re.match(r'^information and communication technologies group policy\s*$', text.lower()):
                continue
                
            if re.match(r'^(indice|sommario|table of contents|capitolo)\s*$', text.lower()):
                continue
                
            if re.match(r'^[\d\.\-\s]*$', text):
                continue
                
            # Clean the text
            cleaned_text = self._clean_single_toc_line(text)
            
            if not cleaned_text or len(cleaned_text.strip()) < 3:
                continue
                
            # Avoid duplicates
            norm_text = cleaned_text.lower().strip()
            if norm_text in seen:
                continue
                
            seen.add(norm_text)
            
            # Format with level indentation
            indent = "  " * (level - 1) if level > 1 else ""
            page_info = f" (p. {page})" if page else ""
            cleaned.append(f"{indent}{cleaned_text}{page_info}")
        
        return '\n'.join(cleaned)

    def _clean_single_toc_line(self, line: str) -> str:
        """
        Clean a single TOC line
        """
        # Remove extra whitespace
        line = re.sub(r'\s+', ' ', line.strip())
        
        # Handle chapter numbering issues
        # Fix "2. 1 Title" -> "2.1 Title"
        line = re.sub(r'^(\d+)\.\s+(\d+)', r'\1.\2', line)
        
        # Fix "2 .1 Title" -> "2.1 Title"  
        line = re.sub(r'^(\d+)\s+\.(\d+)', r'\1.\2', line)
        
        # Standardize chapter numbering format
        line = re.sub(r'^(\d+(?:\.\d+)*)\s*\.?\s*', r'\1 ', line)
        
        # Remove trailing dots and page references at the end
        line = re.sub(r'\s*\.{2,}\s*\d*\s*$', '', line)
        
        # Remove standalone page numbers at the end
        line = re.sub(r'\s+\d+\s*$', '', line)
        
        # Fix broken words (common in PDF extraction)
        # Handle cases like "Reason for and Extent \nof Changes"
        line = re.sub(r'\s*\n\s*', ' ', line)
        
        # Remove multiple spaces
        line = re.sub(r'\s{2,}', ' ', line)
        
        return line.strip()

    def _normalize_for_comparison(self, text: str) -> str:
        """
        Normalize text for duplicate detection
        """
        # Remove punctuation and convert to lowercase
        normalized = re.sub(r'[^\w\s]', '', text.lower())
        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized.strip())
        return normalized

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
                "raw_bytes": base_image["image"],
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

    def extract_tables(
        self,
        doc_bytes: bytes,
        min_words_in_row: int = 1,
        table_settings: Optional[Dict] = None,
    ) -> Optional[List[pd.DataFrame]]:
        """
        Estrae tutte le tabelle da un file PDF con opzioni avanzate.
        
        Args:
            pdf_path: Percorso del file PDF
            min_words_in_row: Numero minimo di celle non vuote per considerare valida una riga
            table_settings: Impostazioni personalizzate per l'estrazione delle tabelle
        
        Returns:
            Lista di DataFrame se output_format è "dataframe", altrimenti None
        """

        
        # Impostazioni default per l'estrazione delle tabelle
        default_table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
            "snap_x_tolerance": 3,
            "snap_y_tolerance": 3,
            "join_tolerance": 3,
            "edge_min_length": 3,
            "min_words_vertical": 3,
            "min_words_horizontal": 3,
            "intersection_tolerance": 3,
            "text_tolerance": 3,
            "text_x_tolerance": 3,
            "text_y_tolerance": 3,
        }
        
        if table_settings:
            default_table_settings.update(table_settings)
        
        all_dataframes = []
        all_jsons = []
        total_tables = 0
        
        try:
            pdf_source = io.BytesIO(doc_bytes)  # Wrappa i bytes in BytesIO
            logger.info(f"Elaborazione PDF da bytes ({len(doc_bytes)} bytes)")
            with pdfplumber.open(pdf_source) as pdf:

                for page_num, page in enumerate(pdf.pages, 1):
                    logger.info(f"Analisi pagina {page_num}/{len(pdf.pages)}")
                    
                    # Estrai tabelle con impostazioni personalizzate
                    tables = page.extract_tables(table_settings=default_table_settings)
                    
                    if not tables:
                        logger.info(f"Nessuna tabella trovata nella pagina {page_num}")
                        continue
                    
                    for table_num, table in enumerate(tables, 1):
                        total_tables += 1
                        
                        # Filtra righe vuote e pulisci i dati
                        cleaned_table = self.clean_table_data(table, min_words_in_row)
                        
                        if not cleaned_table:
                            logger.warning(f"Tabella {table_num} nella pagina {page_num} è vuota dopo la pulizia")
                            continue
                        
                        # Crea DataFrame
                        df = self.create_dataframe_from_table(cleaned_table)
                        df_json = df.to_json(orient='records', force_ascii=False, indent=2)
                        all_jsons.append({
                            "table_id": f"pagina_{page_num}_tabella_{table_num}",
                            "data": json.loads(df_json)
                        })
                        
    
                        all_dataframes.append(df)
                        logger.info(f"Tabella {table_num} elaborata - Dimensioni: {df.shape}")
                
                logger.info(f"Elaborazione completata. Totale tabelle trovate: {total_tables}")                
                return all_dataframes, all_jsons
                    
        except Exception as e:
            logger.error(f"Errore durante l'elaborazione del PDF: {str(e)}")
            return None

    def is_table_significant(self, table, min_table_length=4, min_non_empty_cells=5):
        if len(table) < min_table_length:
            logger.warning(f"La tabella ha meno di {min_table_length} righe, non viene elaborata.")
            return False

        # Conta le celle non vuote (né None né stringhe vuote)
        non_empty_cells = sum(
            1 for row in table for cell in row if cell not in (None, '')
        )

        if non_empty_cells < min_non_empty_cells:
            logger.warning(f"La tabella ha solo {non_empty_cells} celle non vuote, non viene elaborata.")
            return False

        return True

    def clean_table_data(
            self, table: List[List], 
            min_words_in_row: int = 3,
            min_table_length: int = 4) -> List[List]:
        """
        Pulisce i dati della tabella rimuovendo righe vuote e normalizzando i valori.
        """
        
        if not self.is_table_significant(table, min_table_length=4, min_non_empty_cells=5):
            return None
        
        cleaned_table = []
        for row in table:
            # Converte None in stringhe vuote e pulisce gli spazi
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append("")
                else:
                    # Rimuove spazi extra e caratteri di controllo
                    cleaned_cell = str(cell).strip().replace('\n', ' ').replace('\r', '')
                    cleaned_row.append(cleaned_cell)
            
            # Conta celle non vuote
            non_empty_cells = sum(1 for cell in cleaned_row if cell.strip())
            
            # Mantieni la riga solo se ha abbastanza contenuto
            if non_empty_cells >= min_words_in_row:
                cleaned_table.append(cleaned_row)
        
        return cleaned_table

    def create_dataframe_from_table(self, table: List[List]) -> pd.DataFrame:
        """
        Crea un DataFrame pandas da una tabella pulita.
        """
        if not table:
            return pd.DataFrame()
        
        # Se la prima riga sembra essere un header (contiene più testo)
        if len(table) > 1:
            first_row_text_length = sum(len(str(cell)) for cell in table[0])
            avg_row_text_length = sum(sum(len(str(cell)) for cell in row) for row in table[1:]) / len(table[1:])
            
            if first_row_text_length > avg_row_text_length * 0.8:  # Prima riga probabilmente è header
                headers = [f"Col_{i}" if not str(cell).strip() else str(cell) for i, cell in enumerate(table[0])]
                df = pd.DataFrame(table[1:], columns=headers)
            else:
                df = pd.DataFrame(table)
        else:
            df = pd.DataFrame(table)
        
        # Rimuovi colonne completamente vuote
        df = df.dropna(axis=1, how='all')
        
        return df

    def save_table(self, df: pd.DataFrame, format_type: str, output_dir: Path, 
                   base_name: str, table_id: Optional[str] = None):
        """
        Salva la tabella nel formato specificato.
        """
        if table_id:
            filename = f"{base_name}_{table_id}"
        else:
            filename = f"{base_name}_all_tables"
        
        filepath = output_dir / f"{filename}.{format_type}"
        
        try:
            if format_type == "csv":
                df.to_csv(filepath, index=False, encoding='utf-8')
            elif format_type == "excel":
                df.to_excel(filepath, index=False)
            elif format_type == "json":
                df.to_json(filepath, orient='records', indent=2, force_ascii=False)
            
            logging.info(f"Tabella salvata: {filepath}")
        except Exception as e:
            logging.error(f"Errore nel salvataggio di {filepath}: {str(e)}")
