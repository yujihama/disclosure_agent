# 開示資料比較・分析ツールの追加

## Why

企業の開示資料（有価証券報告書、統合報告書、決算短信、計算書類など）の作成・レビュープロセスにおいて、複数資料間の整合性チェックや競合他社との比較分析は、膨大な工数と専門知識を要する課題となっている。AIを活用した自動化により、開示情報の品質向上、作成工数の削減、競合他社分析の高度化を実現する必要がある。

## What Changes

- **書類アップロード機能**: PDFファイルの複数同時アップロード、ドラッグ&ドロップUI、書類種別の自動判定
- **構造化・分析機能**: 非構造データ（PDF）を構造化データに変換、LLMによる項目抽出とページマッピング
- **比較・照合エンジン**: 整合性チェックモード、差分分析モード、数値・テキストデータの詳細比較ロジック
- **結果表示・レポート機能**: サマリーダッシュボード、サイド・バイ・サイドビュー、差分リスト、レポート出力

## Impact

- **Affected specs**: 新規capability 4つ
  - document-upload
  - document-structuring
  - comparison-engine
  - result-reporting
  
- **Affected code**: 新規プロジェクト全体
  - フロントエンド: React/Next.js（UI/UX）
  - バックエンド: Python/FastAPI（PDF解析、LLM統合）
  - LLM統合: OpenAI gpt-5
  - データ処理: PDF解析ライブラリ、テキスト類似度分析

## Dependencies

- OpenAI gpt-5 API
- PDF解析ライブラリ（PyMuPDF、pdfplumber等）
- テキスト類似度分析ライブラリ（sentence-transformers等）


