"""比較エンジンのテスト"""

from __future__ import annotations

import sys
import types
from unittest.mock import Mock

import pytest

from app.services.comparison_engine import (
    ComparisonOrchestrator,
    ComparisonMode,
    DocumentInfo,
    SectionMapping,
    SectionDetailedComparison,
)


@pytest.fixture
def mock_settings():
    """モック設定"""
    settings = Mock()
    settings.openai_api_key = ""
    settings.openai_model = "gpt-4"
    settings.openai_timeout_seconds = 30.0
    return settings


@pytest.fixture(autouse=True)
def stub_pydantic_settings():
    """pydantic_settingsが未インストールの環境でもテストを実行できるようにスタブを登録"""

    module = types.SimpleNamespace(BaseSettings=object, SettingsConfigDict=dict)
    sys.modules.setdefault("pydantic_settings", module)
    yield


@pytest.fixture
def mock_openai_client():
    """モックOpenAIクライアント"""
    client = Mock()
    return client


@pytest.fixture
def orchestrator(mock_settings, mock_openai_client):
    """比較オーケストレータのインスタンス"""
    orchestrator = ComparisonOrchestrator(settings=mock_settings, max_workers=2)
    orchestrator.openai_client = mock_openai_client
    return orchestrator


def test_1_to_n_mapping_all_results_preserved(orchestrator, mock_openai_client):
    """1:Nマッピングですべての結果が保存されることを確認"""
    
    # モックのドキュメント情報
    doc1_info = DocumentInfo(
        document_id="doc1",
        filename="doc1.pdf",
        document_type="securities_report",
        document_type_label="有価証券報告書",
        company_name="テスト株式会社",
        fiscal_year=2023,
    )
    
    doc2_info = DocumentInfo(
        document_id="doc2",
        filename="doc2.pdf",
        document_type="integrated_report",
        document_type_label="統合報告書",
        company_name="テスト株式会社",
        fiscal_year=2023,
    )
    
    # 1:Nマッピング（同じdoc1セクションが複数のdoc2セクションにマッピング）
    section_mappings = [
        SectionMapping(
            doc1_section="財務情報",
            doc2_section="業績ハイライト",
            confidence_score=0.9,
            mapping_method="semantic",
        ),
        SectionMapping(
            doc1_section="財務情報",
            doc2_section="財務情報",
            confidence_score=0.95,
            mapping_method="semantic",
        ),
        SectionMapping(
            doc1_section="財務情報",
            doc2_section="経理の状況",
            confidence_score=0.85,
            mapping_method="semantic",
        ),
    ]
    
    # モックの構造化データ
    structured1 = {
        "sections": {
            "財務情報": {
                "start_page": 10,
                "end_page": 20,
                "pages": list(range(10, 21)),
            }
        },
        "pages": [{"page_number": i, "text": f"Page {i}"} for i in range(1, 21)],
        "tables": [],
    }
    
    structured2 = {
        "sections": {
            "業績ハイライト": {
                "start_page": 5,
                "end_page": 8,
                "pages": list(range(5, 9)),
            },
            "財務情報": {
                "start_page": 15,
                "end_page": 25,
                "pages": list(range(15, 26)),
            },
            "経理の状況": {
                "start_page": 30,
                "end_page": 40,
                "pages": list(range(30, 41)),
            },
        },
        "pages": [{"page_number": i, "text": f"Page {i}"} for i in range(1, 41)],
        "tables": [],
    }
    
    # OpenAI APIのモックレスポンス
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content='{"text_changes": {"added": [], "removed": [], "modified": []}, '
                       '"numerical_changes": [], '
                       '"tone_analysis": {"tone1": "neutral", "tone2": "neutral"}, '
                       '"importance": "medium", '
                       '"importance_reason": "テスト", '
                       '"summary": "テストサマリー"}'
            )
        )
    ]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    # セクション別詳細分析を実行
    result = orchestrator._compare_sections_detailed(
        doc1_info=doc1_info,
        doc2_info=doc2_info,
        structured1=structured1,
        structured2=structured2,
        section_mappings=section_mappings,
        progress_callback=None,
        comparison_mode=ComparisonMode.CONSISTENCY_CHECK,
    )
    
    # 検証：3つのマッピングすべてに対して結果が返されること
    assert len(result) == 3, f"Expected 3 results, got {len(result)}"
    
    # 各結果にマッピング情報が含まれていることを確認
    assert result[0].doc1_section_name == "財務情報"
    assert result[0].doc2_section_name == "業績ハイライト"
    assert result[0].mapping_confidence == 0.9
    assert result[0].mapping_method == "semantic"
    
    assert result[1].doc1_section_name == "財務情報"
    assert result[1].doc2_section_name == "財務情報"
    assert result[1].mapping_confidence == 0.95
    assert result[1].mapping_method == "semantic"
    
    assert result[2].doc1_section_name == "財務情報"
    assert result[2].doc2_section_name == "経理の状況"
    assert result[2].mapping_confidence == 0.85
    assert result[2].mapping_method == "semantic"


def test_n_to_1_mapping_works_correctly(orchestrator, mock_openai_client):
    """N:1マッピングが正常に動作することを確認"""
    
    # モックのドキュメント情報
    doc1_info = DocumentInfo(
        document_id="doc1",
        filename="doc1.pdf",
        document_type="securities_report",
        document_type_label="有価証券報告書",
        company_name="テスト株式会社",
        fiscal_year=2023,
    )
    
    doc2_info = DocumentInfo(
        document_id="doc2",
        filename="doc2.pdf",
        document_type="securities_report",
        document_type_label="有価証券報告書",
        company_name="テスト株式会社",
        fiscal_year=2024,
    )
    
    # N:1マッピング（複数のdoc1セクションが同じdoc2セクションにマッピング）
    section_mappings = [
        SectionMapping(
            doc1_section="財務ハイライト",
            doc2_section="財務情報",
            confidence_score=0.85,
            mapping_method="semantic",
        ),
        SectionMapping(
            doc1_section="決算概要",
            doc2_section="財務情報",
            confidence_score=0.80,
            mapping_method="semantic",
        ),
    ]
    
    # モックの構造化データ
    structured1 = {
        "sections": {
            "財務ハイライト": {
                "start_page": 5,
                "end_page": 7,
                "pages": list(range(5, 8)),
            },
            "決算概要": {
                "start_page": 8,
                "end_page": 10,
                "pages": list(range(8, 11)),
            },
        },
        "pages": [{"page_number": i, "text": f"Page {i}"} for i in range(1, 21)],
        "tables": [],
    }
    
    structured2 = {
        "sections": {
            "財務情報": {
                "start_page": 10,
                "end_page": 20,
                "pages": list(range(10, 21)),
            },
        },
        "pages": [{"page_number": i, "text": f"Page {i}"} for i in range(1, 21)],
        "tables": [],
    }
    
    # OpenAI APIのモックレスポンス
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content='{"text_changes": {"added": [], "removed": [], "modified": []}, '
                       '"numerical_changes": [], '
                       '"tone_analysis": {"tone1": "neutral", "tone2": "neutral"}, '
                       '"importance": "medium", '
                       '"importance_reason": "テスト", '
                       '"summary": "テストサマリー"}'
            )
        )
    ]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    # セクション別詳細分析を実行
    result = orchestrator._compare_sections_detailed(
        doc1_info=doc1_info,
        doc2_info=doc2_info,
        structured1=structured1,
        structured2=structured2,
        section_mappings=section_mappings,
        progress_callback=None,
        comparison_mode=ComparisonMode.DIFF_ANALYSIS_YEAR,
    )
    
    # 検証：2つのマッピングすべてに対して結果が返されること
    assert len(result) == 2, f"Expected 2 results, got {len(result)}"
    
    # 各結果が異なるdoc1セクションを参照していることを確認
    assert result[0].doc1_section_name == "財務ハイライト"
    assert result[0].doc2_section_name == "財務情報"
    
    assert result[1].doc1_section_name == "決算概要"
    assert result[1].doc2_section_name == "財務情報"


def test_mapping_info_included_in_results(orchestrator, mock_openai_client):
    """マッピング情報が結果に正しく含まれることを確認"""
    
    # モックのドキュメント情報
    doc1_info = DocumentInfo(
        document_id="doc1",
        filename="doc1.pdf",
        document_type="securities_report",
        document_type_label="有価証券報告書",
    )
    
    doc2_info = DocumentInfo(
        document_id="doc2",
        filename="doc2.pdf",
        document_type="securities_report",
        document_type_label="有価証券報告書",
    )
    
    # 完全一致マッピング
    section_mappings = [
        SectionMapping(
            doc1_section="企業情報",
            doc2_section="企業情報",
            confidence_score=1.0,
            mapping_method="exact",
        ),
    ]
    
    # モックの構造化データ
    structured1 = {
        "sections": {
            "企業情報": {
                "start_page": 1,
                "end_page": 5,
                "pages": list(range(1, 6)),
            },
        },
        "pages": [{"page_number": i, "text": f"Page {i}"} for i in range(1, 11)],
        "tables": [],
    }
    
    structured2 = {
        "sections": {
            "企業情報": {
                "start_page": 1,
                "end_page": 5,
                "pages": list(range(1, 6)),
            },
        },
        "pages": [{"page_number": i, "text": f"Page {i}"} for i in range(1, 11)],
        "tables": [],
    }
    
    # OpenAI APIのモックレスポンス
    mock_response = Mock()
    mock_response.choices = [
        Mock(
            message=Mock(
                content='{"text_changes": {"added": [], "removed": [], "modified": []}, '
                       '"numerical_changes": [], '
                       '"tone_analysis": {"tone1": "neutral", "tone2": "neutral"}, '
                       '"importance": "low", '
                       '"importance_reason": "変更なし", '
                       '"summary": "変更なし"}'
            )
        )
    ]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    # セクション別詳細分析を実行
    result = orchestrator._compare_sections_detailed(
        doc1_info=doc1_info,
        doc2_info=doc2_info,
        structured1=structured1,
        structured2=structured2,
        section_mappings=section_mappings,
        progress_callback=None,
        comparison_mode=ComparisonMode.DIFF_ANALYSIS_YEAR,
    )
    
    # 検証：マッピング情報が含まれていること
    assert len(result) == 1
    assert result[0].doc1_section_name == "企業情報"
    assert result[0].doc2_section_name == "企業情報"
    assert result[0].mapping_confidence == 1.0
    assert result[0].mapping_method == "exact"


def test_reassess_importance_escalates_with_new_contradictions(orchestrator):
    """追加探索で矛盾が増えた場合に重要度が引き上げられることを確認"""

    additional_searches = [
        {
            "analysis": {
                "additional_contradictions": ["矛盾A", "矛盾B"],
            }
        }
    ]

    importance, reason = orchestrator._reassess_importance(
        initial_importance="medium",
        initial_reason="初期判定",
        additional_searches=additional_searches,
    )

    assert importance == "high"
    assert "2件" in reason


def test_reassess_importance_respects_importance_update(orchestrator):
    """LLMの重要度更新提案が反映されることを確認"""

    additional_searches = [
        {
            "analysis": {
                "importance_update": "high",
                "enhanced_understanding": "業績見通しに重大な差異が見つかりました。",
            }
        }
    ]

    importance, reason = orchestrator._reassess_importance(
        initial_importance="medium",
        initial_reason="",
        additional_searches=additional_searches,
    )

    assert importance == "high"
    assert "重大な差異" in reason


def test_reassess_importance_downgrades_when_resolved(orchestrator):
    """矛盾が解消された場合に重要度が引き下げられることを確認"""

    additional_searches = [
        {
            "analysis": {
                "importance_update": "medium",
                "resolved_contradictions": ["矛盾が解消"],
            }
        }
    ]

    importance, reason = orchestrator._reassess_importance(
        initial_importance="high",
        initial_reason="矛盾が存在",
        additional_searches=additional_searches,
    )

    assert importance == "medium"
    assert "矛盾1件が解消されました" in reason

