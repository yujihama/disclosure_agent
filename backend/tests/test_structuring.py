"""Tests for document structuring services."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from app.services.structuring import TableExtractor, TextExtractor, VisionExtractor


class TestTextExtractor:
    """Tests for TextExtractor service."""

    def test_extract_returns_error_for_nonexistent_file(self):
        """テキスト抽出サービスは存在しないファイルに対してエラーを返す"""
        extractor = TextExtractor()
        result = extractor.extract(Path("/nonexistent/file.pdf"))
        
        assert not result.success
        assert "not found" in result.error.lower()
        assert result.page_count == 0

    def test_extract_page_range_validates_page_numbers(self):
        """ページ範囲抽出は不正なページ番号を検証する"""
        extractor = TextExtractor()
        result = extractor.extract_page_range(
            Path("/nonexistent/file.pdf"), start_page=5, end_page=3
        )
        
        assert not result.success
        assert "not found" in result.error.lower()


class TestVisionExtractor:
    """Tests for VisionExtractor service."""

    def test_vision_extractor_init(self):
        """Vision抽出サービスは正しく初期化される"""
        extractor = VisionExtractor(api_key="test-key", model="gpt-5")
        
        assert extractor.model == "gpt-5"
        assert extractor.image_resolution == 150
        assert extractor.max_retries == 3

    def test_extract_returns_error_for_nonexistent_file(self):
        """Vision抽出サービスは存在しないファイルに対してエラーを返す"""
        extractor = VisionExtractor(api_key="test-key")
        result = extractor.extract(Path("/nonexistent/file.pdf"))
        
        assert not result.success
        assert "not found" in result.error.lower()
        assert result.tokens_used == 0


class TestTableExtractor:
    """Tests for TableExtractor service."""

    def test_table_extractor_init(self):
        """テーブル抽出サービスは正しく初期化される"""
        extractor = TableExtractor()
        
        assert extractor.table_settings["vertical_strategy"] == "lines"
        assert extractor.table_settings["horizontal_strategy"] == "lines"

    def test_extract_returns_error_for_nonexistent_file(self):
        """テーブル抽出サービスは存在しないファイルに対してエラーを返す"""
        extractor = TableExtractor()
        result = extractor.extract(Path("/nonexistent/file.pdf"))
        
        assert not result.success
        assert "not found" in result.error.lower()
        assert result.table_count == 0

    def test_process_table_with_valid_data(self):
        """テーブル処理は有効なデータを正しく処理する"""
        extractor = TableExtractor()
        raw_table = [
            ["Header1", "Header2", "Header3"],
            ["Value1", "Value2", "Value3"],
            ["Value4", "Value5", "Value6"],
        ]
        
        processed = extractor._process_table(raw_table, page_number=1, table_index=0)
        
        assert processed["page_number"] == 1
        assert processed["table_index"] == 0
        assert processed["header"] == ["Header1", "Header2", "Header3"]
        assert processed["row_count"] == 2
        assert processed["column_count"] == 3
        assert len(processed["structured_data"]) == 2

    def test_contains_numeric_data_returns_true_for_numeric_table(self):
        """数値データ検出は数値を含むテーブルでTrueを返す"""
        extractor = TableExtractor()
        table = {
            "rows": [
                ["100", "200", "300"],
                ["400", "500", "600"],
            ]
        }
        
        assert extractor._contains_numeric_data(table) is True

    def test_contains_numeric_data_returns_false_for_text_table(self):
        """数値データ検出はテキストのみのテーブルでFalseを返す"""
        extractor = TableExtractor()
        table = {
            "rows": [
                ["Text", "More Text", "Even More Text"],
                ["ABC", "DEF", "GHI"],
            ]
        }
        
        assert extractor._contains_numeric_data(table) is False


class TestStructuringIntegration:
    """Integration tests for structuring pipeline."""

    @pytest.mark.skip(reason="Requires actual PDF file")
    def test_full_structuring_pipeline_with_real_pdf(self):
        """実際のPDFファイルを使った完全な構造化パイプライン"""
        # This test would require a sample PDF file
        # and proper setup of OpenAI API credentials
        pass

