"""Vision-based PDF extraction using OpenAI Vision API for scanned documents."""

from __future__ import annotations

import base64
import io
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

import pymupdf  # PyMuPDF for rendering pages
from openai import OpenAI
from PIL import Image

logger = logging.getLogger(__name__)


class VisionExtractionResult:
    """Result of vision-based extraction from a PDF document."""

    def __init__(
        self,
        success: bool,
        text: str = "",
        page_count: int = 0,
        pages: Optional[list[dict[str, Any]]] = None,
        error: Optional[str] = None,
        tokens_used: int = 0,
    ):
        self.success = success
        self.text = text
        self.page_count = page_count
        self.pages = pages or []
        self.error = error
        self.tokens_used = tokens_used

    def to_dict(self) -> dict:
        """Convert extraction result to dictionary format."""
        return {
            "success": self.success,
            "text": self.text,
            "page_count": self.page_count,
            "pages": self.pages,
            "error": self.error,
            "tokens_used": self.tokens_used,
        }


class VisionExtractor:
    """Service for extracting text from scanned PDFs using OpenAI Vision API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5",
        image_resolution: int = 150,
        max_retries: int = 3,
        batch_size: int = 10,
        max_workers: int = 10,
    ):
        """
        Initialize vision extractor.

        Args:
            api_key: OpenAI API key
            model: OpenAI model to use (must support vision)
            image_resolution: DPI for PDF-to-image conversion
            max_retries: Maximum retry attempts for API calls
            batch_size: Number of pages to process in parallel
            max_workers: Maximum number of parallel workers
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.image_resolution = image_resolution
        self.max_retries = max_retries
        self.batch_size = batch_size
        self.max_workers = max_workers

    def _pdf_page_to_image_base64(
        self, pdf_path: Path, page_num: int
    ) -> Optional[str]:
        """
        Convert a PDF page to base64-encoded PNG image.

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (0-indexed)

        Returns:
            Base64-encoded PNG image or None on failure
        """
        try:
            doc = pymupdf.open(pdf_path)
            page = doc[page_num]
            
            # Render page to pixmap
            mat = pymupdf.Matrix(self.image_resolution / 72, self.image_resolution / 72)
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # Encode to base64
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
            
            doc.close()
            return base64_image

        except Exception as exc:
            logger.exception(
                "Failed to convert page %s to image from %s: %s",
                page_num,
                pdf_path,
                exc,
            )
            return None

    def _extract_text_from_image(
        self, base64_image: str, page_number: int, context: str = ""
    ) -> tuple[Optional[str], int]:
        """
        Extract text from a base64-encoded image using Vision API.

        Args:
            base64_image: Base64-encoded image
            page_number: Page number for context
            context: Previous page context for continuity

        Returns:
            Tuple of (extracted_text, tokens_used)
        """
        attempt = 1
        wait_seconds = 1.0

        system_prompt = (
            "あなたは日本語の企業開示資料(有価証券報告書、統合報告書、決算短信等)から"
            "正確にテキストを抽出するアシスタントです。画像から全ての文字を読み取り、"
            "元のレイアウトや表構造を可能な限り保持してください。"
        )

        user_prompt = f"ページ {page_number} の内容を抽出してください。"
        if context:
            user_prompt += f"\n\n直前のページの文脈: {context[:500]}"

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                    },
                ],
            },
        ]

        while attempt <= self.max_retries:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=4096,
                )

                extracted_text = response.choices[0].message.content
                tokens_used = response.usage.total_tokens

                return extracted_text, tokens_used

            except Exception as exc:  # pragma: no cover - network/SDK errors
                status_code = getattr(exc, "status_code", None)
                if status_code is None:
                    response_obj = getattr(exc, "response", None)
                    status_code = getattr(response_obj, "status_code", None)

                should_retry = False
                if attempt < self.max_retries:
                    if isinstance(status_code, int) and (status_code == 429 or status_code >= 500):
                        should_retry = True

                if should_retry:
                    logger.warning(
                        "Vision API extraction attempt %s/%s failed with status %s: %s. Retrying in %.1f seconds.",
                        attempt,
                        self.max_retries,
                        status_code,
                        exc,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    attempt += 1
                    wait_seconds = min(wait_seconds * 2, 30)
                    continue

                logger.exception(
                    "Failed to extract text from image (page %s) after %s attempts: %s",
                    page_number,
                    attempt,
                    exc,
                )
                return None, 0

        logger.error(
            "Vision API extraction exceeded retry limit for page %s (attempted %s times)",
            page_number,
            self.max_retries,
        )
        return None, 0

    def _process_single_page(
        self, pdf_path: Path, page_num: int, previous_context: str = ""
    ) -> dict:
        """
        Process a single page (convert to image and extract text).
        
        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (0-indexed)
            previous_context: Context from previous page
            
        Returns:
            Dictionary with page data
        """
        page_number = page_num + 1
        
        try:
            # Convert page to image
            base64_image = self._pdf_page_to_image_base64(pdf_path, page_num)
            if base64_image is None:
                return {
                    "page_number": page_number,
                    "text": "",
                    "error": "Image conversion failed",
                    "tokens_used": 0,
                }

            # Extract text using Vision API
            extracted_text, tokens_used = self._extract_text_from_image(
                base64_image, page_number, previous_context
            )

            if extracted_text is None:
                return {
                    "page_number": page_number,
                    "text": "",
                    "error": "Vision API extraction failed",
                    "tokens_used": 0,
                }

            return {
                "page_number": page_number,
                "text": extracted_text,
                "char_count": len(extracted_text),
                "tokens_used": tokens_used,
            }
            
        except Exception as exc:
            logger.exception("Failed to process page %s: %s", page_number, exc)
            return {
                "page_number": page_number,
                "text": "",
                "error": str(exc),
                "tokens_used": 0,
            }

    def _process_batch_parallel(
        self, pdf_path: Path, page_nums: list[int], batch_context: str = ""
    ) -> list[dict]:
        """
        Process multiple pages in parallel.
        
        Args:
            pdf_path: Path to the PDF file
            page_nums: List of page numbers (0-indexed)
            batch_context: Context from previous batch
            
        Returns:
            List of page data dictionaries
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all pages in the batch
            future_to_page = {
                executor.submit(
                    self._process_single_page, 
                    pdf_path, 
                    page_num,
                    batch_context if i == 0 else ""  # Only first page gets context
                ): page_num
                for i, page_num in enumerate(page_nums)
            }
            
            # Collect results as they complete
            page_results = {}
            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    page_data = future.result()
                    page_results[page_num] = page_data
                except Exception as exc:
                    logger.exception(
                        "Page %s processing raised an exception: %s",
                        page_num + 1,
                        exc,
                    )
                    page_results[page_num] = {
                        "page_number": page_num + 1,
                        "text": "",
                        "error": str(exc),
                        "tokens_used": 0,
                    }
            
            # Sort results by page number to maintain order
            results = [page_results[page_num] for page_num in sorted(page_results.keys())]
        
        return results

    def extract(self, pdf_path: Path) -> VisionExtractionResult:
        """
        Extract text from a PDF file using Vision API with batch parallel processing.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            VisionExtractionResult containing extracted text and metadata
        """
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return VisionExtractionResult(
                success=False, error=f"File not found: {pdf_path}"
            )

        try:
            doc = pymupdf.open(pdf_path)
            page_count = len(doc)
            doc.close()

            full_text = []
            pages_data = []
            total_tokens = 0
            batch_context = ""

            # Process pages in batches
            for batch_start in range(0, page_count, self.batch_size):
                batch_end = min(batch_start + self.batch_size, page_count)
                page_nums = list(range(batch_start, batch_end))
                
                logger.info(
                    f"Processing batch: pages {batch_start + 1}-{batch_end}/{page_count} "
                    f"of {pdf_path.name} (parallel)"
                )

                # Process batch in parallel
                batch_results = self._process_batch_parallel(
                    pdf_path, page_nums, batch_context
                )
                
                # Collect results
                for page_data in batch_results:
                    pages_data.append(page_data)
                    
                    page_text = page_data.get("text", "")
                    if page_text:
                        full_text.append(page_text)
                        total_tokens += page_data.get("tokens_used", 0)
                        
                        # Update context for next batch (last 500 chars of batch)
                        batch_context = page_text[-500:] if len(page_text) > 500 else page_text

            full_text_str = "\n".join(full_text)

            return VisionExtractionResult(
                success=True,
                text=full_text_str,
                page_count=page_count,
                pages=pages_data,
                tokens_used=total_tokens,
            )

        except Exception as exc:
            logger.exception(
                "Failed to extract text using Vision API from %s: %s",
                pdf_path,
                exc,
            )
            return VisionExtractionResult(
                success=False,
                error=f"Vision extraction failed: {str(exc)}",
            )

    def extract_page_range(
        self, pdf_path: Path, start_page: int, end_page: int
    ) -> VisionExtractionResult:
        """
        Extract text from a specific page range using Vision API with batch parallel processing.

        Args:
            pdf_path: Path to the PDF file
            start_page: Starting page number (1-indexed)
            end_page: Ending page number (1-indexed, inclusive)

        Returns:
            VisionExtractionResult for the specified page range
        """
        if not pdf_path.exists():
            return VisionExtractionResult(
                success=False, error=f"File not found: {pdf_path}"
            )

        try:
            doc = pymupdf.open(pdf_path)
            total_pages = len(doc)
            doc.close()

            # Validate page range
            if start_page < 1 or end_page > total_pages or start_page > end_page:
                return VisionExtractionResult(
                    success=False,
                    error=f"Invalid page range: {start_page}-{end_page} (total: {total_pages})",
                )

            full_text = []
            pages_data = []
            total_tokens = 0
            batch_context = ""

            # Process pages in batches
            page_range = range(start_page - 1, end_page)
            for batch_start in range(0, len(page_range), self.batch_size):
                batch_end = min(batch_start + self.batch_size, len(page_range))
                page_nums = [page_range[i] for i in range(batch_start, batch_end)]
                
                logger.info(
                    f"Processing batch: pages {page_nums[0] + 1}-{page_nums[-1] + 1}/{end_page} "
                    f"of {pdf_path.name} (parallel)"
                )

                # Process batch in parallel
                batch_results = self._process_batch_parallel(
                    pdf_path, page_nums, batch_context
                )
                
                # Collect results
                for page_data in batch_results:
                    pages_data.append(page_data)
                    
                    page_text = page_data.get("text", "")
                    if page_text:
                        full_text.append(page_text)
                        total_tokens += page_data.get("tokens_used", 0)
                        
                        # Update context for next batch (last 500 chars of batch)
                        batch_context = page_text[-500:] if len(page_text) > 500 else page_text

            full_text_str = "\n".join(full_text)
            page_count = end_page - start_page + 1

            return VisionExtractionResult(
                success=True,
                text=full_text_str,
                page_count=page_count,
                pages=pages_data,
                tokens_used=total_tokens,
            )

        except Exception as exc:
            logger.exception(
                "Failed to extract page range %s-%s using Vision API from %s: %s",
                start_page,
                end_page,
                pdf_path,
                exc,
            )
            return VisionExtractionResult(
                success=False,
                error=f"Vision extraction failed: {str(exc)}",
            )

