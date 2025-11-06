export type DocumentStatus = "accepted" | "rejected";
export type ProcessingStatus = 
  | "queued" 
  | "pending_classification"
  | "processing" 
  | "extracting_text" 
  | "extracting_vision" 
  | "extracting_tables" 
  | "detecting_sections"
  | "structured" 
  | "completed" 
  | "failed" 
  | "rejected" 
  | null;

export type ExtractionMethod = "text" | "vision" | "hybrid" | null;

export interface DocumentUploadLimits {
  max_files: number;
  max_file_size_mb: number;
}

export interface StructuredData {
  full_text: string;
  pages: Array<{
    page_number: number;
    text: string;
    char_count: number;
    has_images?: boolean;
  }>;
  tables: Array<{
    page_number: number;
    table_index: number;
    header: string[];
    rows: string[][];
    structured_data: Array<Record<string, string>>;
    row_count: number;
    column_count: number;
  }>;
}

export interface DocumentUploadResult {
  document_id: string | null;
  filename: string;
  size_bytes: number;
  status: DocumentStatus;
  errors: string[];
  detected_type: string | null;
  detected_type_label: string | null;
  detection_confidence: number | null;
  matched_keywords: string[];
  detection_reason?: string | null;
  processing_status: ProcessingStatus;
  manual_type: string | null;
  manual_type_label: string | null;
  selected_type: string | null;
  selected_type_label: string | null;
  // 構造化データ関連フィールド
  structured_data?: StructuredData | null;
  extraction_method?: ExtractionMethod;
  extraction_metadata?: Record<string, any> | null;
}

export interface DocumentUploadResponse {
  batch_id: string;
  task_id: string | null;
  limits: DocumentUploadLimits;
  documents: DocumentUploadResult[];
}

export interface DocumentMutationResponse {
  document: DocumentUploadResult;
}

export interface DocumentListResponse {
  documents: DocumentUploadResult[];
  total: number;
}

export interface DocumentTypeOption {
  value: string;
  label: string;
}

// 比較関連の型定義

export interface DocumentInfo {
  document_id: string;
  filename: string;
  document_type: string | null;
  document_type_label: string | null;
  company_name: string | null;
  fiscal_year: number | null;
  extraction_confidence: number | null;
}

export interface SectionMapping {
  doc1_section: string;
  doc2_section: string;
  confidence_score: number;
  mapping_method: string;
}

export interface NumericalDifference {
  section: string;
  item_name: string;
  value1: number;
  value2: number;
  difference: number;
  difference_pct: number | null;
  unit1: string | null;
  unit2: string | null;
  normalized_unit: string | null;
  is_significant: boolean;
}

export interface TextDifference {
  section: string;
  match_ratio: number;
  added_text: string[];
  removed_text: string[];
  changed_text: Array<[string, string]>;
  semantic_similarity: number | null;
}

export interface AdditionalSearchResult {
  iteration: number;
  search_keywords: string[];
  found_sections: Array<{
    doc1_section: string;
    doc2_section: string;
    similarity: number;
  }>;
  analysis: Record<string, any>;
}

export interface SectionDetailedComparison {
  section_name: string;
  doc1_page_range: string;
  doc2_page_range: string;
  text_changes: Record<string, any>;
  numerical_changes: Array<Record<string, any>>;
  tone_analysis: Record<string, any>;
  importance: "high" | "medium" | "low";
  importance_reason: string;
  summary: string;
  // マッピング情報（1:Nマッピング対応）
  doc1_section_name: string;
  doc2_section_name: string;
  mapping_confidence: number;
  mapping_method: string;
  // 追加探索の結果
  additional_searches?: AdditionalSearchResult[];
  has_additional_context?: boolean;
}

export type ComparisonMode = 
  | "consistency_check"
  | "diff_analysis_company"
  | "diff_analysis_year"
  | "multi_document";

export interface ComparisonResult {
  comparison_id: string;
  mode: ComparisonMode;
  doc1_info: DocumentInfo;
  doc2_info: DocumentInfo;
  section_mappings: SectionMapping[];
  numerical_differences: NumericalDifference[];
  text_differences: TextDifference[];
  section_detailed_comparisons: SectionDetailedComparison[];
  priority: "high" | "medium" | "low";
  created_at: string;
}

