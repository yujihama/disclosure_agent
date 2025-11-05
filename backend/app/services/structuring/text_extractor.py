"""Text extraction service using PyMuPDF for PDF documents."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import pymupdf  # PyMuPDF

logger = logging.getLogger(__name__)


class TextExtractionResult:
    """Result of text extraction from a PDF document."""

    def __init__(
        self,
        success: bool,
        text: str = "",
        page_count: int = 0,
        pages: Optional[list[dict[str, Any]]] = None,
        error: Optional[str] = None,
    ):
        self.success = success
        self.text = text
        self.page_count = page_count
        self.pages = pages or []
        self.error = error

    def to_dict(self) -> dict:
        """Convert extraction result to dictionary format."""
        return {
            "success": self.success,
            "text": self.text,
            "page_count": self.page_count,
            "pages": self.pages,
            "error": self.error,
        }


class TextExtractor:
    """Service for extracting text from PDF documents using PyMuPDF."""

    def __init__(self, min_text_threshold: int = 50):
        """
        Initialize text extractor.

        Args:
            min_text_threshold: Minimum characters per page to consider text extraction successful
        """
        self.min_text_threshold = min_text_threshold

    def extract(self, pdf_path: Path) -> TextExtractionResult:
        """
        Extract text from a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            TextExtractionResult containing extracted text and metadata
        """
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return TextExtractionResult(
                success=False, error=f"File not found: {pdf_path}"
            )

        try:
            doc = pymupdf.open(pdf_path)
            page_count = len(doc)
            full_text = []
            pages_data = []

            for page_num in range(page_count):
                page = doc[page_num]
                page_text = page.get_text("text")
                
                pages_data.append({
                    "page_number": page_num + 1,
                    "text": page_text,
                    "char_count": len(page_text),
                    "has_images": len(page.get_images()) > 0,
                })
                
                full_text.append(page_text)

            doc.close()

            full_text_str = "\n".join(full_text)
            avg_chars_per_page = len(full_text_str) / page_count if page_count > 0 else 0

            # テキスト抽出が十分かどうかを判定
            is_sufficient = avg_chars_per_page >= self.min_text_threshold

            if not is_sufficient:
                logger.warning(
                    f"Text extraction may be insufficient for {pdf_path.name}: "
                    f"avg {avg_chars_per_page:.1f} chars/page (threshold: {self.min_text_threshold})"
                )

            return TextExtractionResult(
                success=is_sufficient,
                text=full_text_str,
                page_count=page_count,
                pages=pages_data,
                error=None if is_sufficient else "Insufficient text content detected",
            )

        except Exception as exc:
            logger.exception("Failed to extract text from %s", pdf_path)
            return TextExtractionResult(
                success=False,
                error=f"Text extraction failed: {str(exc)}",
            )

    def extract_page_range(
        self, pdf_path: Path, start_page: int, end_page: int
    ) -> TextExtractionResult:
        """
        Extract text from a specific page range.

        Args:
            pdf_path: Path to the PDF file
            start_page: Starting page number (1-indexed)
            end_page: Ending page number (1-indexed, inclusive)

        Returns:
            TextExtractionResult for the specified page range
        """
        if not pdf_path.exists():
            return TextExtractionResult(
                success=False, error=f"File not found: {pdf_path}"
            )

        try:
            doc = pymupdf.open(pdf_path)
            total_pages = len(doc)

            # Validate page range
            if start_page < 1 or end_page > total_pages or start_page > end_page:
                doc.close()
                return TextExtractionResult(
                    success=False,
                    error=f"Invalid page range: {start_page}-{end_page} (total: {total_pages})",
                )

            full_text = []
            pages_data = []

            for page_num in range(start_page - 1, end_page):
                page = doc[page_num]
                page_text = page.get_text("text")
                
                pages_data.append({
                    "page_number": page_num + 1,
                    "text": page_text,
                    "char_count": len(page_text),
                    "has_images": len(page.get_images()) > 0,
                })
                
                full_text.append(page_text)

            doc.close()

            full_text_str = "\n".join(full_text)
            page_count = end_page - start_page + 1
            avg_chars_per_page = len(full_text_str) / page_count if page_count > 0 else 0

            is_sufficient = avg_chars_per_page >= self.min_text_threshold

            return TextExtractionResult(
                success=is_sufficient,
                text=full_text_str,
                page_count=page_count,
                pages=pages_data,
                error=None if is_sufficient else "Insufficient text content detected",
            )

        except Exception as exc:
            logger.exception(
                "Failed to extract page range %s-%s from %s",
                start_page,
                end_page,
                pdf_path,
            )
            return TextExtractionResult(
                success=False,
                error=f"Page range extraction failed: {str(exc)}",
            )

