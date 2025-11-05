"""Table extraction service using pdfplumber for structured data extraction."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import pdfplumber

logger = logging.getLogger(__name__)


class TableExtractionResult:
    """Result of table extraction from a PDF document."""

    def __init__(
        self,
        success: bool,
        tables: Optional[list[dict[str, Any]]] = None,
        page_count: int = 0,
        table_count: int = 0,
        error: Optional[str] = None,
    ):
        self.success = success
        self.tables = tables or []
        self.page_count = page_count
        self.table_count = table_count
        self.error = error

    def to_dict(self) -> dict:
        """Convert extraction result to dictionary format."""
        return {
            "success": self.success,
            "tables": self.tables,
            "page_count": self.page_count,
            "table_count": self.table_count,
            "error": self.error,
        }


class TableExtractor:
    """Service for extracting tables from PDF documents using pdfplumber."""

    def __init__(
        self,
        table_settings: Optional[dict] = None,
        min_words_horizontal: int = 3,
        min_words_vertical: int = 3,
    ):
        """
        Initialize table extractor.

        Args:
            table_settings: Custom table detection settings for pdfplumber
            min_words_horizontal: Minimum number of words for horizontal edge detection
            min_words_vertical: Minimum number of words for vertical edge detection
        """
        self.table_settings = table_settings or {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "min_words_vertical": min_words_vertical,
            "min_words_horizontal": min_words_horizontal,
        }

    def extract(self, pdf_path: Path) -> TableExtractionResult:
        """
        Extract all tables from a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            TableExtractionResult containing extracted tables and metadata
        """
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return TableExtractionResult(
                success=False, error=f"File not found: {pdf_path}"
            )

        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)
                all_tables = []
                table_count = 0

                for page_num, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables(self.table_settings)

                    for table_index, table in enumerate(tables):
                        if table and len(table) > 0:
                            # Process table data
                            processed_table = self._process_table(
                                table, page_num, table_index
                            )
                            all_tables.append(processed_table)
                            table_count += 1

            return TableExtractionResult(
                success=True,
                tables=all_tables,
                page_count=page_count,
                table_count=table_count,
            )

        except Exception as exc:
            logger.exception("Failed to extract tables from %s", pdf_path)
            return TableExtractionResult(
                success=False,
                error=f"Table extraction failed: {str(exc)}",
            )

    def extract_from_page(
        self, pdf_path: Path, page_number: int
    ) -> TableExtractionResult:
        """
        Extract tables from a specific page.

        Args:
            pdf_path: Path to the PDF file
            page_number: Page number (1-indexed)

        Returns:
            TableExtractionResult for the specified page
        """
        if not pdf_path.exists():
            return TableExtractionResult(
                success=False, error=f"File not found: {pdf_path}"
            )

        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)

                if page_number < 1 or page_number > total_pages:
                    return TableExtractionResult(
                        success=False,
                        error=f"Invalid page number: {page_number} (total: {total_pages})",
                    )

                page = pdf.pages[page_number - 1]
                tables = page.extract_tables(self.table_settings)
                all_tables = []
                table_count = 0

                for table_index, table in enumerate(tables):
                    if table and len(table) > 0:
                        processed_table = self._process_table(
                            table, page_number, table_index
                        )
                        all_tables.append(processed_table)
                        table_count += 1

                return TableExtractionResult(
                    success=True,
                    tables=all_tables,
                    page_count=1,
                    table_count=table_count,
                )

        except Exception as exc:
            logger.exception(
                "Failed to extract tables from page %s of %s", page_number, pdf_path
            )
            return TableExtractionResult(
                success=False,
                error=f"Table extraction failed: {str(exc)}",
            )

    def _process_table(
        self, table: list[list[str]], page_number: int, table_index: int
    ) -> dict:
        """
        Process raw table data into structured format.

        Args:
            table: Raw table data from pdfplumber
            page_number: Page number where the table was found
            table_index: Index of the table on the page

        Returns:
            Processed table as dictionary
        """
        # Clean and normalize table data
        cleaned_table = []
        for row in table:
            cleaned_row = [cell.strip() if cell else "" for cell in row]
            cleaned_table.append(cleaned_row)

        # Detect header row (usually the first row)
        header = cleaned_table[0] if len(cleaned_table) > 0 else []
        data_rows = cleaned_table[1:] if len(cleaned_table) > 1 else []

        # Convert to list of dictionaries for easier manipulation
        structured_data = []
        for row_data in data_rows:
            row_dict = {}
            for col_index, cell_value in enumerate(row_data):
                col_name = header[col_index] if col_index < len(header) else f"column_{col_index}"
                row_dict[col_name] = cell_value
            structured_data.append(row_dict)

        return {
            "page_number": page_number,
            "table_index": table_index,
            "header": header,
            "rows": data_rows,
            "structured_data": structured_data,
            "row_count": len(data_rows),
            "column_count": len(header),
        }

    def extract_numeric_tables(self, pdf_path: Path) -> TableExtractionResult:
        """
        Extract tables containing numeric data (for financial statements).

        Args:
            pdf_path: Path to the PDF file

        Returns:
            TableExtractionResult containing only tables with numeric data
        """
        result = self.extract(pdf_path)

        if not result.success:
            return result

        # Filter tables that contain numeric data
        numeric_tables = []
        for table in result.tables:
            if self._contains_numeric_data(table):
                numeric_tables.append(table)

        return TableExtractionResult(
            success=True,
            tables=numeric_tables,
            page_count=result.page_count,
            table_count=len(numeric_tables),
        )

    def _contains_numeric_data(self, table: dict) -> bool:
        """
        Check if a table contains numeric data.

        Args:
            table: Processed table dictionary

        Returns:
            True if table contains numeric data
        """
        numeric_count = 0
        total_cells = 0

        for row in table["rows"]:
            for cell in row:
                if cell:
                    total_cells += 1
                    # Check if cell contains numbers
                    if any(char.isdigit() for char in cell):
                        numeric_count += 1

        # Consider a table numeric if >30% of cells contain numbers
        if total_cells == 0:
            return False

        numeric_ratio = numeric_count / total_cells
        return numeric_ratio > 0.3

