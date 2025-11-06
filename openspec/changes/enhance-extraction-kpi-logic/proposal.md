# 情報抽出の拡張提案：KPI時系列と論理関係の追加

## Why

現在の情報抽出では、以下の重要な情報が不足しており、比較処理の精度と有用性が制限されています：

1. **定量的な情報の不足**
   - KPIや財務指標の時系列推移が体系的に抽出されていない
   - 単年度の数値のみで、複数年度の推移が比較できない
   - セグメント別の時系列データが不足

2. **定性情報の論理構造の不足**
   - 因果関係、前提条件、結論などの論理関係が抽出されていない
   - 事実とメッセージの関係性が不明確
   - 変化の理由や根拠が追跡できない

これらの情報を構造化して抽出することで、年度間比較の精度が向上し、変化の要因分析が可能になります。

## What Changes

### 1. セクション内容抽出の拡張

`backend/app/services/structuring/section_content_extractor.py`に以下のカテゴリを追加：

#### 1.1 時系列財務データ（kpi_time_series）

複数年度の財務指標を**原文に記載されているまま**構造化して抽出：

**重要原則**: 
- ✅ 原文に記載されている情報のみを抽出
- ❌ 自動計算や推測は一切行わない
- ❌ CAGR、トレンド、達成率等の自動計算は禁止
- ✅ 原文に明記されている場合のみ抽出

```json
{
  "kpi_time_series": [
    {
      "indicator": "売上高",
      "unit": "百万円",
      "time_series": [
        {"period": "2020年3月期", "value": 1000000, "note": null},
        {"period": "2021年3月期", "value": 1050000, "note": null},
        {"period": "2022年3月期", "value": 1100000, "note": null},
        {"period": "2023年3月期", "value": 1200000, "note": null},
        {"period": "2024年3月期", "value": 1320000, "note": "新製品効果"}
      ],
      "stated_metrics": {
        "cagr_stated": "年平均成長率7.2%（原文に記載がある場合のみ）",
        "trend_stated": "増加傾向（原文に記載がある場合のみ）",
        "comment": "原文のコメントをそのまま記載"
      },
      "target_stated": {
        "target_description": "2025年度に1,400億円を目指す（原文の表現をそのまま）",
        "target_value": 1400000,
        "target_period": "2025年3月期"
      }
    }
  ]
}
```

#### 1.2 論理関係（logical_relationships）

因果関係、前提条件、結論などの論理構造を**原文に明記されているもののみ**抽出：

**重要原則**:
- ✅ 原文に明確に記載されている論理関係のみを抽出
- ❌ 推測や解釈は行わない
- ✅ 原文の該当箇所を引用する

```json
{
  "logical_relationships": [
    {
      "relationship_type": "causality",
      "subject": "売上高の増加",
      "subject_category": "financial_result",
      "reason": "新製品の販売好調および海外市場での拡販",
      "reason_category": "business_driver",
      "evidence": "新製品Aの売上高が前年比150%、北米市場での売上が同120%",
      "original_text": "売上高が前年比10%増加したのは、新製品Aの販売が好調だったことと、海外市場での拡販が進んだことが主な要因です。",
      "confidence": "high",
      "source_section": "事業の状況 - 経営成績の分析"
    },
    {
      "relationship_type": "condition_consequence",
      "condition": "為替相場が1ドル=140円を超える円安で推移",
      "condition_category": "external_factor",
      "consequence": "営業利益が約30億円増加する見込み",
      "consequence_category": "financial_impact",
      "original_text": "為替相場が1ドル=140円を超える円安で推移した場合、営業利益が約30億円増加する見込みです。",
      "confidence": "medium",
      "source_section": "事業の状況 - 経営成績の分析"
    },
    {
      "relationship_type": "problem_solution",
      "problem": "サイバーセキュリティリスクの高まり",
      "problem_category": "risk",
      "solution": "CSIRT体制の構築と多層防御の実施",
      "solution_category": "mitigation_measure",
      "effectiveness": "リスクレベルを中程度に低減（原文に記載がある場合のみ）",
      "original_text": "サイバーセキュリティリスクに対応するため、当社はCSIRT体制を構築し、多層防御を実施しています。",
      "source_section": "事業の状況 - 事業等のリスク"
    },
    {
      "relationship_type": "premise_conclusion",
      "premise": "中長期的な企業価値向上を目指す",
      "premise_category": "management_policy",
      "conclusion": "ROE 10%以上を目標とする",
      "conclusion_category": "target_indicator",
      "reasoning": "株主資本の効率的活用と持続的成長の両立",
      "original_text": "中長期的な企業価値向上を目指し、株主資本の効率的活用と持続的成長の両立を図るため、ROE 10%以上を目標としています。",
      "source_section": "事業の状況 - 経営方針"
    }
  ]
}
```

#### 1.3 セグメント別時系列データ（segment_time_series）

セグメントごとの財務指標の推移を**原文に記載されているまま**抽出：

**重要原則**: 
- ✅ 原文に記載されている時系列データのみを抽出
- ❌ 構成比率、成長率等の自動計算は禁止
- ✅ 原文に記載がある場合のみ抽出

```json
{
  "segment_time_series": [
    {
      "segment_name": "医薬品事業",
      "revenue_time_series": [
        {"period": "2020年3月期", "value": 400000},
        {"period": "2021年3月期", "value": 420000},
        {"period": "2022年3月期", "value": 450000},
        {"period": "2023年3月期", "value": 480000},
        {"period": "2024年3月期", "value": 500000}
      ],
      "profit_time_series": [
        {"period": "2020年3月期", "value": 60000},
        {"period": "2021年3月期", "value": 65000},
        {"period": "2022年3月期", "value": 70000},
        {"period": "2023年3月期", "value": 75000},
        {"period": "2024年3月期", "value": 80000}
      ],
      "stated_metrics": {
        "revenue_composition_stated": "売上構成比37.9%（原文に記載がある場合のみ）",
        "growth_rate_stated": "前年比4.2%増（原文に記載がある場合のみ）",
        "comment": "原文のコメントをそのまま記載"
      }
    }
  ]
}
```

### 2. 比較処理の拡張

`backend/app/services/comparison_engine.py`に以下の機能を追加：

#### 2.1 時系列比較分析（原文記載ベース）

**重要**: 自動計算は行わず、原文に記載されている情報のみを比較

- 年度間のKPI推移の**記載内容**を比較
- 原文に記載されているトレンドの**表現の変化**を検出（「増加傾向」→「減少傾向」等）
- 原文に記載されている目標値と実績値の**記載内容**を比較
- 原文に記載されている成長率やコメントの変化を検出

#### 2.2 論理関係の変化分析

- 因果関係の追加・削除・変更を検出
- 問題-解決の対応関係の変化を追跡
- 経営方針と目標の**記載内容の変化**を検出
- 原文の引用箇所の変化を追跡

### 3. プロンプトの拡張

`section_content_extractor.py`の`_build_extraction_prompt()`を修正し、以下を追加：

```python
【抽出タスク】
以下の7種類の情報を抽出してください：

1. **財務指標・数値情報** (financial_data) - 既存
2. **会計処理上のコメント** (accounting_notes) - 既存
3. **事実情報** (factual_info) - 既存
4. **主張・メッセージ** (messages) - 既存

5. **時系列財務データ** (kpi_time_series) - 新規
   - 複数年度（通常5年分）の財務指標の推移を**原文に記載されているまま**抽出
   - 各指標には、指標名(indicator)、単位(unit)、時系列データ(time_series)を含める
   - **重要**: CAGR、トレンド、目標値は**原文に明記されている場合のみ**抽出（自動計算禁止）
   - 原文のコメントや注記もそのまま記載
   - 例: {{"indicator": "売上高", "unit": "百万円", "time_series": [{{"period": "2020年3月期", "value": 1000000}}, ...], "stated_metrics": {{"comment": "原文のコメント"}}}}

6. **論理関係** (logical_relationships) - 新規
   - 因果関係（causality）: 結果とその原因（**原文に明記されている因果関係のみ**）
   - 条件-結果（condition_consequence）: 前提条件と結果（**原文に明記されている条件のみ**）
   - 問題-解決（problem_solution）: 問題とその対応策（**原文に明記されている対応策のみ**）
   - 前提-結論（premise_conclusion）: 前提と結論（**原文に明記されている論理のみ**）
   - **重要**: 推測や解釈は行わず、原文の表現をそのまま抽出
   - 必ず原文の該当箇所を引用（original_text）
   - 例: {{"relationship_type": "causality", "subject": "売上高の増加", "reason": "新製品の販売好調", "original_text": "原文の該当箇所をそのまま引用"}}

7. **セグメント別時系列データ** (segment_time_series) - 新規
   - セグメントごとの財務指標の推移（通常5年分）を**原文に記載されているまま**抽出
   - セグメント名(segment_name)、指標の時系列(time_series)を含める
   - **重要**: 構成比、成長率等は**原文に記載がある場合のみ**抽出（自動計算禁止）
   - 例: {{"segment_name": "医薬品事業", "revenue_time_series": [{{"period": "2020年3月期", "value": 400000}}, ...], "stated_metrics": {{"comment": "原文のコメント"}}}}

【抽出の基本原則】★最重要★
- **要約禁止**: 原文の表現をできるだけそのまま保持してください
- **推測禁止**: 記載されていない情報を推測しないでください
- **計算禁止**: 成長率、構成比、達成率等の自動計算は行わないでください
- **引用重視**: 論理関係は必ず原文の該当箇所を引用（original_text）してください
- **記載のみ**: 原文に記載されている情報のみを抽出してください
```

## Impact

### Affected Specs
- `specs/document-structuring/spec.md` - セクション内容抽出の要件を追加
- `specs/document-comparison/spec.md` - 時系列比較と論理関係分析の要件を追加

### Affected Code
- `backend/app/services/structuring/section_content_extractor.py` - プロンプトとパース処理を拡張
- `backend/app/services/comparison_engine.py` - 時系列比較と論理関係分析を追加
- `backend/app/schemas/documents.py` - 構造化データのスキーマを拡張
- `backend/app/schemas/comparisons.py` - 比較結果のスキーマを拡張
- `backend/templates/*.yaml` - 抽出ポイントを追加

### Breaking Changes
なし（既存のデータ構造に新しいフィールドを追加するのみ）

### Migration
- 既存の構造化データは引き続き使用可能
- 新しい抽出処理は、再構造化時に適用される

