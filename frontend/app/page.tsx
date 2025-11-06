/* eslint-disable jsx-a11y/label-has-associated-control */
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { listDocuments, getDocument, uploadDocuments, updateDocumentType, deleteDocument, listComparisons, compareDocuments, getComparisonStatus, getComparisonResult } from "@/lib/api";
import { DOCUMENT_TYPE_OPTIONS, findDocumentLabel } from "@/lib/document-types";
import { MAX_UPLOAD_FILES, MAX_UPLOAD_SIZE_MB } from "@/lib/config";
import type { DocumentUploadResult, DocumentUploadResponse } from "@/lib/types";

const AUTO_OPTION_VALUE = "__auto__";

// 構造化データ表示コンポーネント
function StructuredDataDisplay({ document }: { document: DocumentUploadResult }) {
  const [expandedSections, setExpandedSections] = useState({
    summary: true,
    sections: false,
    pages: false,
    tables: false,
    metadata: false,
  });

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  if (!document.structured_data) return null;

  const sd = document.structured_data;
  const pages = sd.pages || [];
  const tables = sd.tables || [];

  return (
    <div className="mt-4 space-y-2">
      {/* サマリー */}
      <details className="rounded-lg border border-white/20 bg-white/5" open>
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-white hover:bg-white/5">
          Structured Data Summary
        </summary>
        <div className="border-t border-white/10 px-4 py-3">
          <div className="grid gap-3 text-xs text-white/70 md:grid-cols-3">
            <div>
              <span className="font-medium text-white/90">Extraction:</span>{" "}
              {document.extraction_method === "text"
                ? "Text"
                : document.extraction_method === "vision"
                  ? "Vision"
                  : document.extraction_method === "hybrid"
                    ? "Hybrid"
                    : document.extraction_method ?? "Unknown"}
            </div>
            <div>
              <span className="font-medium text-white/90">Pages:</span> {pages.length}
            </div>
            <div>
              <span className="font-medium text-white/90">Tables:</span> {tables.length}
            </div>
            <div className="md:col-span-3">
              <span className="font-medium text-white/90">Characters:</span>{" "}
              {sd.full_text?.length?.toLocaleString() ?? 0}
            </div>
          </div>
        </div>
      </details>

      {/* ページ詳細 */}
      {pages.length > 0 && (
        <details className="rounded-lg border border-white/20 bg-white/5">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-white hover:bg-white/5">
            Pages ({pages.length})
          </summary>
          <div className="max-h-96 overflow-y-auto border-t border-white/10 px-4 py-3">
            <div className="space-y-2">
              {pages.slice(0, 10).map((page, idx) => (
                <details key={idx} className="rounded border border-white/10 bg-white/5">
                  <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-white/80 hover:bg-white/10">
                    Page {page.page_number} - {page.char_count?.toLocaleString() ?? 0} chars
                    {page.has_images && " (images)"}
                  </summary>
                  <div className="border-t border-white/10 px-3 py-2">
                    <pre className="max-h-40 overflow-auto whitespace-pre-wrap text-[10px] leading-relaxed text-white/70">
                      {page.text?.substring(0, 500) ?? ""}
                      {(page.text?.length ?? 0) > 500 && "..."}
                    </pre>
                  </div>
                </details>
              ))}
              {pages.length > 10 && (
                <p className="text-xs text-white/50">
                  ... {pages.length - 10} more pages
                </p>
              )}
            </div>
          </div>
        </details>
      )}

      {/* セクション検出結果 */}
      {(sd as any).sections && Object.keys((sd as any).sections).length > 0 && (
        <details className="rounded-lg border border-white/20 bg-white/5">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-white hover:bg-white/5">
            Detected Sections ({Object.keys((sd as any).sections).length})
          </summary>
          <div className="max-h-96 overflow-y-auto border-t border-white/10 px-4 py-3">
            <div className="space-y-3">
              {Object.entries((sd as any).sections).map(([sectionName, sectionInfo]: [string, any]) => (
                <details key={sectionName} className="rounded border border-white/10 bg-white/5">
                  <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-white/90 hover:bg-white/10">
                    {sectionName}
                    <span className="ml-2 text-white/50">
                      (p.{sectionInfo.start_page}-{sectionInfo.end_page} · {sectionInfo.char_count?.toLocaleString() ?? 0} chars · {((sectionInfo.confidence ?? 0) * 100).toFixed(0)}% confidence)
                    </span>
                  </summary>
                  <div className="border-t border-white/10 px-3 py-3">
                    {sectionInfo.extracted_content ? (
                      <div className="space-y-2">
                        {/* 財務指標・数値情報 */}
                        {sectionInfo.extracted_content.financial_data && sectionInfo.extracted_content.financial_data.length > 0 && (
                          <div className="rounded bg-blue-500/10 border border-blue-500/30 p-2">
                            <div className="text-[10px] font-semibold text-blue-200 mb-1">💰 財務指標・数値情報 ({sectionInfo.extracted_content.financial_data.length})</div>
                            <div className="space-y-1">
                              {sectionInfo.extracted_content.financial_data.map((item: any, idx: number) => (
                                <div key={idx} className="text-[10px] text-blue-100/80">
                                  • {item.item}: {typeof item.value === 'object' && item.value !== null ? (
                                    <span className="ml-2 block pl-2 border-l border-blue-500/30 mt-1">
                                      {Object.entries(item.value).map(([k, v]: [string, any]) => (
                                        <div key={k} className="text-[9px]">
                                          {k}: {String(v)}
                                        </div>
                                      ))}
                                    </span>
                                  ) : `${item.value ?? ''} ${item.unit || ''}`} {item.period && `(${item.period})`}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        {/* 会計処理上のコメント */}
                        {sectionInfo.extracted_content.accounting_notes && sectionInfo.extracted_content.accounting_notes.length > 0 && (
                          <div className="rounded bg-amber-500/10 border border-amber-500/30 p-2">
                            <div className="text-[10px] font-semibold text-amber-200 mb-1">📝 会計処理上のコメント ({sectionInfo.extracted_content.accounting_notes.length})</div>
                            <div className="space-y-1">
                              {sectionInfo.extracted_content.accounting_notes.map((item: any, idx: number) => (
                                <div key={idx} className="text-[10px] text-amber-100/80">
                                  • <span className="font-medium">{item.topic}:</span> {item.content}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        {/* 事実情報 */}
                        {sectionInfo.extracted_content.factual_info && sectionInfo.extracted_content.factual_info.length > 0 && (
                          <div className="rounded bg-emerald-500/10 border border-emerald-500/30 p-2">
                            <div className="text-[10px] font-semibold text-emerald-200 mb-1">📊 事実情報 ({sectionInfo.extracted_content.factual_info.length})</div>
                            <div className="space-y-1">
                              {sectionInfo.extracted_content.factual_info.map((item: any, idx: number) => (
                                <div key={idx} className="text-[10px] text-emerald-100/80">
                                  • <span className="font-medium">[{item.category}]</span> {item.item}: {typeof item.value === 'object' && item.value !== null ? (
                                    <span className="ml-2 block pl-2 border-l border-emerald-500/30 mt-1 space-y-0.5">
                                      {Object.entries(item.value).map(([k, v]: [string, any]) => (
                                        <div key={k} className="text-[9px]">
                                          {k}: {String(v)}
                                        </div>
                                      ))}
                                    </span>
                                  ) : (item.value ?? '')}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        {/* 主張・メッセージ */}
                        {sectionInfo.extracted_content.messages && sectionInfo.extracted_content.messages.length > 0 && (
                          <div className="rounded bg-purple-500/10 border border-purple-500/30 p-2">
                            <div className="text-[10px] font-semibold text-purple-200 mb-1">💬 主張・メッセージ ({sectionInfo.extracted_content.messages.length})</div>
                            <div className="space-y-1">
                              {sectionInfo.extracted_content.messages.map((item: any, idx: number) => (
                                <div key={idx} className="text-[10px] text-purple-100/80">
                                  • <span className="font-medium">[{item.type}]</span> {item.content}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        {!sectionInfo.extracted_content.financial_data?.length && 
                         !sectionInfo.extracted_content.accounting_notes?.length && 
                         !sectionInfo.extracted_content.factual_info?.length && 
                         !sectionInfo.extracted_content.messages?.length && (
                          <p className="text-[10px] text-white/40">抽出されたコンテンツがありません</p>
                        )}
                      </div>
                    ) : (
                      <p className="text-[10px] text-white/40">extracted_content が利用できません</p>
                    )}
                  </div>
                </details>
              ))}
            </div>
          </div>
        </details>
      )}

      {/* テーブル詳細 */}
      {tables.length > 0 && (
        <details className="rounded-lg border border-white/20 bg-white/5">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-white hover:bg-white/5">
            Tables ({tables.length})
          </summary>
          <div className="max-h-96 overflow-y-auto border-t border-white/10 px-4 py-3">
            <div className="space-y-2">
              {tables.slice(0, 5).map((table, idx) => (
                <details key={idx} className="rounded border border-white/10 bg-white/5">
                  <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-white/80 hover:bg-white/10">
                    Table {idx + 1} (Page {table.page_number}) - {table.row_count} × {table.column_count}
                  </summary>
                  <div className="border-t border-white/10 px-3 py-2">
                    <div className="overflow-x-auto">
                      <table className="w-full text-[10px] text-white/70">
                        <thead>
                          <tr className="border-b border-white/10">
                            {table.header?.map((h, i) => (
                              <th key={i} className="px-2 py-1 text-left font-medium text-white/90">
                                {h || `Col ${i + 1}`}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {table.rows?.slice(0, 5).map((row, i) => (
                            <tr key={i} className="border-b border-white/5">
                              {row.map((cell, j) => (
                                <td key={j} className="px-2 py-1">
                                  {cell}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {(table.rows?.length ?? 0) > 5 && (
                        <p className="mt-2 text-[10px] text-white/50">
                          ... {(table.rows?.length ?? 0) - 5} more rows
                        </p>
                      )}
                    </div>
                  </div>
                </details>
              ))}
              {tables.length > 5 && (
                <p className="text-xs text-white/50">
                  ... {tables.length - 5} more tables
                </p>
              )}
            </div>
          </div>
        </details>
      )}

      {/* 抽出メタデータ */}
      {document.extraction_metadata && (
        <details className="rounded-lg border border-white/20 bg-white/5">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-white hover:bg-white/5">
            Extraction Metadata
          </summary>
          <div className="border-t border-white/10 px-4 py-3">
            <pre className="max-h-60 overflow-auto text-[10px] text-white/70">
              {JSON.stringify(document.extraction_metadata, null, 2)}
            </pre>
          </div>
        </details>
      )}
    </div>
  );
}

const bytesToMegabytes = (bytes: number) => `${(bytes / (1024 * 1024)).toFixed(2)} MB`;

const bytesToReadable = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const getFileKey = (file: File) => `${file.name}::${file.lastModified}`;
const getDocumentKey = (document: DocumentUploadResult) => document.document_id ?? document.filename;

const getLabelForType = (value: string | null) =>
  value == null ? null : findDocumentLabel(value) ?? value;

const processingStatusLabel: Record<string, string> = {
  queued: "キュー待ち",
  pending_classification: "分類待ち",
  processing: "処理中",
  extracting_text: "テキスト抽出中",
  extracting_vision: "画像解析中",
  extracting_tables: "テーブル抽出中",
  detecting_sections: "セクション検出中",
  extracting_section_content: "セクション情報抽出中",
  structured: "構造化完了",
  completed: "完了",
  failed: "失敗",
  rejected: "対象外",
};

export default function HomePage() {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [limits, setLimits] = useState<DocumentUploadResponse["limits"]>({
    max_files: MAX_UPLOAD_FILES,
    max_file_size_mb: MAX_UPLOAD_SIZE_MB,
  });
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [results, setResults] = useState<DocumentUploadResult[]>([]);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [pendingOverrides, setPendingOverrides] = useState<Record<string, string>>({});
  const [updating, setUpdating] = useState<Record<string, boolean>>({});
  
  // 比較機能用のstate
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [iterativeSearchMode, setIterativeSearchMode] = useState<"off" | "high_only" | "all">("off");
  const [isComparing, setIsComparing] = useState(false);
  const [comparisonResult, setComparisonResult] = useState<any>(null);
  const [comparisonError, setComparisonError] = useState<string | null>(null);
  const [comparisonProgress, setComparisonProgress] = useState<number>(0);
  const [comparisonStatus, setComparisonStatus] = useState<string>("");
  const [currentSection, setCurrentSection] = useState<string>("");
  const [sectionProgress, setSectionProgress] = useState<{completed: number, total: number} | null>(null);
  
  // 比較結果フィルタリング用のstate
  const [importanceFilter, setImportanceFilter] = useState<"all" | "high" | "medium" | "low">("all");
  const [searchQuery, setSearchQuery] = useState("");
  
  // タブ切り替え用のstate
  const [activeTab, setActiveTab] = useState<"documents" | "comparison">("documents");
  
  // 比較履歴用のstate
  const [comparisonHistory, setComparisonHistory] = useState<Array<{
    comparison_id: string;
    created_at: string;
    mode: string;
    doc1_filename: string;
    doc2_filename: string;
    section_count: number;
  }>>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  
  // 削除機能用のstate
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const maxBytes = useMemo(() => limits.max_file_size_mb * 1024 * 1024, [limits.max_file_size_mb]);
  const totalSelectedSize = useMemo(
    () => selectedFiles.reduce((sum, file) => sum + file.size, 0),
    [selectedFiles],
  );

  const resetAll = useCallback(() => {
    setSelectedFiles([]);
    setResults([]);
    setBatchId(null);
    setTaskId(null);
    setPendingOverrides({});
    setUpdating({});
    setErrorMessage(null);
    setSelectedDocIds(new Set());
    setComparisonResult(null);
    setComparisonError(null);
    setComparisonProgress(0);
    setComparisonStatus("");
    setCurrentSection("");
    setSectionProgress(null);
  }, []);

  // ドキュメント一覧を読み込む
  const loadDocuments = useCallback(async () => {
    try {
      const response = await listDocuments();
      setResults(response.documents);
    } catch (error) {
      console.error("ドキュメント一覧の読み込みに失敗:", error);
    }
  }, []);

  // 比較履歴を読み込む
  const loadComparisonHistory = useCallback(async () => {
    try {
      const history = await listComparisons();
      setComparisonHistory(history);
    } catch (error) {
      console.error("比較履歴の読み込みに失敗:", error);
    }
  }, []);

  // ページロード時にドキュメント一覧を読み込む
  useEffect(() => {
    loadDocuments();
    loadComparisonHistory();
  }, [loadDocuments, loadComparisonHistory]);
  
  // ドキュメント削除処理
  const handleDelete = useCallback(async (documentId: string) => {
    console.log("削除処理開始:", documentId);
    setIsDeleting(true);
    setErrorMessage(null);
    
    try {
      console.log("deleteDocument API呼び出し中...");
      await deleteDocument(documentId);
      console.log("削除成功:", documentId);
      
      // 削除成功後、リストから削除
      setResults((prev) => prev.filter((doc) => doc.document_id !== documentId));
      // 選択リストからも削除
      setSelectedDocIds((prev) => {
        const next = new Set(prev);
        next.delete(documentId);
        return next;
      });
      setDeleteConfirmId(null);
    } catch (error) {
      console.error("削除エラー:", error);
      const message = error instanceof Error ? error.message : "削除に失敗しました";
      setErrorMessage(message);
      setDeleteConfirmId(null); // エラー時もダイアログを閉じる
    } finally {
      setIsDeleting(false);
    }
  }, []);
  
  // ドキュメント選択のトグル
  const toggleDocSelection = useCallback((docId: string) => {
    setSelectedDocIds((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) {
        next.delete(docId);
      } else {
        next.add(docId);
      }
      return next;
    });
  }, []);
  
  // 比較実行
  const handleCompare = useCallback(async () => {
    console.log("=== handleCompare 開始 ===");
    console.log("selectedDocIds:", Array.from(selectedDocIds));
    console.log("iterativeSearchMode:", iterativeSearchMode);
    
    if (selectedDocIds.size < 2) {
      setComparisonError("比較には最低2つのドキュメントを選択してください。");
      return;
    }
    
    setIsComparing(true);
    setComparisonError(null);
    setComparisonResult(null);
    setComparisonProgress(0);
    setComparisonStatus("開始中...");
    setCurrentSection("");
    setSectionProgress(null);
    
    try {
      // Step 1: 比較タスクを開始
      console.log("compareDocuments を呼び出します - iterativeSearchMode:", iterativeSearchMode);
      const task = await compareDocuments(Array.from(selectedDocIds), iterativeSearchMode);
      const comparisonId = task.comparison_id;
      
      // Step 2: ポーリングでステータスを確認
      const pollInterval = 2000; // 2秒ごと（サーバー負荷軽減のため）
      const maxAttempts = 1200; // 最大40分（2400秒 = 40分、初回のセクション抽出と詳細分析に対応）
      let attempts = 0;
      
      const poll = async (): Promise<void> => {
        if (attempts >= maxAttempts) {
          throw new Error("タイムアウト: 比較処理に時間がかかりすぎています（40分以上）。処理はバックグラウンドで継続中です。しばらく待ってから比較履歴を確認してください。");
        }
        
        attempts++;
        const status = await getComparisonStatus(comparisonId);
        
        // 進捗情報を更新
        setComparisonProgress(status.progress || 0);
        setComparisonStatus(status.step || status.status);
        
        if (status.current_section) {
          setCurrentSection(status.current_section);
        }
        
        if (status.total_sections && status.completed_sections !== undefined) {
          setSectionProgress({
            completed: status.completed_sections,
            total: status.total_sections
          });
        }
        
        if (status.status === "completed") {
          // Step 3: 結果を取得
          const result = await getComparisonResult(comparisonId);
          setComparisonResult(result);
          setSelectedHistoryId(comparisonId);
          setIsComparing(false);
          setComparisonStatus("完了");
          // 比較履歴を再読み込み
          await loadComparisonHistory();
          // 比較結果タブに自動切り替え
          setActiveTab("comparison");
        } else if (status.status === "failed") {
          throw new Error(status.error || "比較処理に失敗しました");
        } else {
          // まだ処理中、再度ポーリング
          setTimeout(poll, pollInterval);
        }
      };
      
      await poll();
      
    } catch (error) {
      setComparisonError(error instanceof Error ? error.message : "比較に失敗しました");
      setIsComparing(false);
    }
  }, [selectedDocIds, iterativeSearchMode, loadComparisonHistory]);

  const handleFiles = useCallback(
    (incomingList: FileList | File[]) => {
      const incoming = Array.from(incomingList);
      if (incoming.length === 0) return;

      const messages: string[] = [];

      setSelectedFiles((previous) => {
        const unique = new Map<string, File>();
        previous.forEach((file) => unique.set(getFileKey(file), file));

        incoming.forEach((file) => {
          if (file.size > maxBytes) {
            messages.push(
              `ファイル「${file.name}」はサイズ上限（${bytesToMegabytes(maxBytes)}）を超過しているため追加できません。`,
            );
            return;
          }
          unique.set(getFileKey(file), file);
        });

        const merged = Array.from(unique.values());
        if (merged.length > limits.max_files) {
          messages.push(`アップロードできるファイルは最大 ${limits.max_files} 件までです。`);
        }

        return merged.slice(0, limits.max_files);
      });

      setErrorMessage(messages.length > 0 ? messages.join("\n") : null);
    },
    [limits.max_file_size_mb, limits.max_files, maxBytes],
  );

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      event.stopPropagation();
      setIsDragging(false);
      handleFiles(event.dataTransfer.files);
    },
    [handleFiles],
  );

  const handleDragEnter = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
  }, []);

  const handleFileInput = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      if (event.target.files) {
        handleFiles(event.target.files);
        event.target.value = "";
      }
    },
    [handleFiles],
  );

  const handleUpload = useCallback(async () => {
    if (selectedFiles.length === 0) {
      setErrorMessage("アップロードする PDF を選択してください。");
      return;
    }

    setIsUploading(true);
    setErrorMessage(null);
    try {
      const response = await uploadDocuments(selectedFiles);
      setResults(response.documents);
      setBatchId(response.batch_id);
      setTaskId(response.task_id);
      setLimits(response.limits);
      setPendingOverrides({});
      setUpdating({});
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "アップロード中に不明なエラーが発生しました。";
      setErrorMessage(message);
    } finally {
      setIsUploading(false);
    }
  }, [selectedFiles]);

  const handleRemoveFile = useCallback((file: File) => {
    setSelectedFiles((prev) => prev.filter((candidate) => candidate !== file));
  }, []);

  const currentSelectionFor = useCallback(
    (document: DocumentUploadResult): string => {
      const key = getDocumentKey(document);
      if (pendingOverrides[key] !== undefined) {
        return pendingOverrides[key];
      }
      if (document.manual_type) {
        return document.manual_type;
      }
      if (document.selected_type) {
        return document.selected_type;
      }
      return "unknown";
    },
    [pendingOverrides],
  );

  const handleOverrideChange = useCallback(
    async (document: DocumentUploadResult, value: string) => {
      if (!document.document_id) {
        setErrorMessage("この書類はサーバーに保存されていないため、種別を更新できません。");
        return;
      }

      const key = getDocumentKey(document);
      setPendingOverrides((prev) => ({ ...prev, [key]: value }));
      setUpdating((prev) => ({ ...prev, [key]: true }));

      try {
        const payloadValue = value === AUTO_OPTION_VALUE ? null : value;
        const response = await updateDocumentType(document.document_id, payloadValue);
        setResults((prev) =>
          prev.map((item) => (item.document_id === document.document_id ? response.document : item)),
        );
        setPendingOverrides((prev) => {
          const next = { ...prev };
          delete next[key];
          return next;
        });
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "書類種別の更新に失敗しました。";
        setErrorMessage(message);
      } finally {
        setUpdating((prev) => {
          const next = { ...prev };
          delete next[key];
          return next;
        });
      }
    },
    [],
  );

  // ドキュメントの処理状況をポーリング
  useEffect(() => {
    if (results.length === 0) return;

    const interval = setInterval(async () => {
      // 毎回最新の results から pendingDocuments を計算
      const currentPendingDocuments = results.filter(
        (doc) =>
          doc.document_id &&
          doc.processing_status &&
          ["queued", "processing", "extracting_text", "extracting_vision", "extracting_tables", "detecting_sections"].includes(doc.processing_status),
      );

      // ポーリング対象がない場合はスキップ
      if (currentPendingDocuments.length === 0) {
        return;
      }

      console.log(`Polling ${currentPendingDocuments.length} documents:`, currentPendingDocuments.map(d => d.document_id));

      const updates = await Promise.allSettled(
        currentPendingDocuments.map(async (doc) => {
          if (!doc.document_id) return { doc_id: null, data: null, error: null };
          try {
            const response = await getDocument(doc.document_id);
            return { doc_id: doc.document_id, data: response.document, error: null };
          } catch (error) {
            // 404エラー（削除済み）の場合
            if (error instanceof Error && (error.message.includes("not found") || error.message.includes("404"))) {
              console.log(`Document ${doc.document_id} was deleted (404), removing from list`);
              return { doc_id: doc.document_id, data: null, error: "deleted" };
            }
            console.error(`Error polling document ${doc.document_id}:`, error);
            return { doc_id: doc.document_id, data: null, error: "fetch_error" };
          }
        }),
      );

      let hasChanges = false;
      setResults((prev) => {
        let updated = [...prev];
        
        updates.forEach((result, index) => {
          if (result.status !== "fulfilled") return;
          
          const updateInfo = result.value;
          if (!updateInfo || !updateInfo.doc_id) return;
          
          const docIndex = updated.findIndex(item => item.document_id === updateInfo.doc_id);
          if (docIndex === -1) return;
          
          if (updateInfo.error === "deleted") {
            // 削除されたドキュメントを除外
            console.log(`Removing deleted document from list: ${updateInfo.doc_id}`);
            updated = updated.filter(item => item.document_id !== updateInfo.doc_id);
            hasChanges = true;
          } else if (updateInfo.data) {
            // 更新されたデータで置き換え
            updated[docIndex] = updateInfo.data;
            hasChanges = true;
          }
        });
        
        return updated;
      });

      if (hasChanges) {
        console.log("Document list updated");
      }
    }, 5000); // 5秒ごとにポーリング

    return () => clearInterval(interval);
  }, [results]);

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col gap-10 px-6 py-16">
      <header className="space-y-3 border-b border-white/10 pb-6">
        <h1 className="text-3xl font-semibold tracking-tight text-white">Disclosure Document Agent</h1>
        <p className="text-sm leading-relaxed text-white/60">
          開示文書の自動判定、構造化、比較分析を行うGenAIベースのツールです。
        </p>
      </header>

      <section>
        <div
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className={`relative flex min-h-[220px] flex-col items-center justify-center rounded-lg border-2 border-dashed px-8 transition ${
            isDragging ? "border-white/40 bg-white/10" : "border-white/20 bg-white/5"
          }`}
        >
          <div className="relative z-10 flex flex-col items-center gap-4 text-center">
            <p className="text-xl font-medium text-white">Drag & Drop or Click to Select</p>
            <p className="max-w-lg text-sm text-white/60">
              PDF files only. Convert other formats before uploading.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3 text-xs text-white/50">
              <span>Max {limits.max_files} files</span>
              <span>·</span>
              <span>Up to {limits.max_file_size_mb}MB each</span>
              <span>·</span>
              <span>
                Selected: {selectedFiles.length} / {bytesToMegabytes(totalSelectedSize)}
              </span>
            </div>
            <label className="relative inline-flex cursor-pointer items-center justify-center gap-2 rounded-md border border-white/20 bg-white/10 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-white/20">
              Browse Files
              <input
                type="file"
                accept="application/pdf"
                multiple
                onChange={handleFileInput}
                className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
              />
            </label>
          </div>
        </div>
        {errorMessage ? (
          <p className="mt-3 rounded-md border border-white/20 bg-white/5 px-3 py-2 text-sm text-white/80">
            {errorMessage}
          </p>
        ) : null}
      </section>

      {selectedFiles.length > 0 ? (
        <section className="rounded-lg border border-white/20 bg-white/5 p-6">
          <div className="mb-4 flex items-center justify-between border-b border-white/10 pb-3">
            <h2 className="text-lg font-semibold text-white">Selected Files</h2>
            <button
              type="button"
              onClick={resetAll}
              className="text-xs text-white/60 transition-colors hover:text-white"
            >
              Clear All
            </button>
          </div>
          <ul className="space-y-2 text-sm">
            {selectedFiles.map((file) => (
              <li
                key={getFileKey(file)}
                className="flex items-center justify-between gap-4 rounded-md border border-white/10 bg-white/5 px-4 py-3"
              >
                <div className="flex flex-col">
                  <span className="font-medium text-white">{file.name}</span>
                  <span className="text-xs text-white/50">
                    {bytesToReadable(file.size)} · {new Date(file.lastModified).toLocaleDateString()}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveFile(file)}
                  className="text-xs text-white/60 transition-colors hover:text-white"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <button
              type="button"
              onClick={handleUpload}
              disabled={isUploading}
              className="inline-flex items-center justify-center rounded-md bg-white/20 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-white/30 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isUploading ? "Uploading..." : "Upload Files"}
            </button>
            <p className="text-xs text-white/50">
              Files will be processed via Celery after upload
            </p>
          </div>
        </section>
      ) : null}

      {results.length > 0 ? (
        <section className="space-y-4">
          {/* タブナビゲーション */}
          <div className="flex items-center gap-1 border-b border-white/10">
            <button
              type="button"
              onClick={() => setActiveTab("documents")}
              className={`relative px-5 py-3 text-sm font-medium transition-colors ${
                activeTab === "documents"
                  ? "text-white"
                  : "text-white/50 hover:text-white/70"
              }`}
            >
              Documents
              {activeTab === "documents" && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-white" />
              )}
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("comparison")}
              disabled={comparisonHistory.length === 0 && !comparisonResult}
              className={`relative px-5 py-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-30 ${
                activeTab === "comparison"
                  ? "text-white"
                  : "text-white/50 hover:text-white/70"
              }`}
            >
              Comparison
              {(comparisonHistory.length > 0 || comparisonResult) && (
                <span className="ml-1.5 text-xs text-white/50">
                  ({comparisonHistory.length})
                </span>
              )}
              {activeTab === "comparison" && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-white" />
              )}
            </button>
          </div>

          {/* ドキュメント一覧タブの内容 */}
          {activeTab === "documents" && (
            <>
          <header className="space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <div>
                <h2 className="text-2xl font-semibold text-white">Documents</h2>
                <p className="mt-1 text-xs text-white/50">
                  Batch ID: {batchId ?? "N/A"} · Task ID: {taskId ?? "未キューイング"}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={loadDocuments}
                  className="rounded-md border border-white/20 bg-white/5 px-3 py-2 text-xs text-white/80 transition-colors hover:bg-white/10"
                >
                  Refresh
                </button>
                <span className="text-sm text-white/50">
                  {selectedDocIds.size} selected
                </span>
                <div className="flex items-center gap-2">
                  <label className="text-xs text-white/70">追加探索:</label>
                  <select
                    value={iterativeSearchMode}
                    onChange={(e) => {
                      const newValue = e.target.value as "off" | "high_only" | "all";
                      console.log("=== select onChange ===");
                      console.log("旧値:", iterativeSearchMode);
                      console.log("新値:", newValue);
                      setIterativeSearchMode(newValue);
                      console.log("setIterativeSearchMode 呼び出し完了");
                    }}
                    disabled={isComparing}
                    className="rounded-md border border-white/20 bg-white/5 px-2 py-1 text-xs text-white/80 transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-30 [&>option]:bg-gray-800 [&>option]:text-white"
                  >
                    <option value="off">OFF: 追加探索なし（高速）</option>
                    <option value="high_only">重要度Highのみ: 重要なセクションのみ追加探索</option>
                    <option value="all">すべて: 全セクションで追加探索（時間がかかる）</option>
                  </select>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    console.log("=== Compareボタンクリック ===");
                    console.log("現在の iterativeSearchMode:", iterativeSearchMode);
                    handleCompare();
                  }}
                  disabled={selectedDocIds.size < 2 || isComparing}
                  className="rounded-md bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-100 transition-colors hover:bg-cyan-500/30 disabled:cursor-not-allowed disabled:opacity-30"
                >
                  {isComparing ? "Comparing..." : "Compare"}
                </button>
              </div>
            </div>
            
            {comparisonError && (
              <div className="rounded-lg border border-white/20 bg-white/5 px-4 py-3">
                <p className="text-sm text-white/80">{comparisonError}</p>
              </div>
            )}
            
            {/* 比較進捗表示 */}
            {isComparing && (
              <div className="rounded-lg border border-white/20 bg-white/5 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="text-sm font-medium text-white/90">Processing Comparison</h3>
                  <span className="text-sm font-semibold text-white">{comparisonProgress}%</span>
                </div>
                
                {/* プログレスバー */}
                <div className="mb-3 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                  <div 
                    className="h-1.5 rounded-full bg-white/60 transition-all duration-300"
                    style={{ width: `${comparisonProgress}%` }}
                  />
                </div>
                
                {/* ステータス情報 */}
                <div className="space-y-1.5 text-xs text-white/60">
                  <p>
                    <span className="font-medium text-white/80">Status:</span> {comparisonStatus}
                  </p>
                  
                  {currentSection && (
                    <p>
                      <span className="font-medium text-white/80">Current Section:</span> {currentSection}
                    </p>
                  )}
                  
                  {sectionProgress && (
                    <p>
                      <span className="font-medium text-white/80">Progress:</span>{" "}
                      {sectionProgress.completed} / {sectionProgress.total} sections
                    </p>
                  )}
                </div>
              </div>
            )}
          </header>
          <div className="space-y-4">
            {results.map((document) => {
              const key = getDocumentKey(document);
              const selectValue = currentSelectionFor(document);
              const isUpdating = Boolean(updating[key]);
              const selectedLabel =
                selectValue === AUTO_OPTION_VALUE
                  ? document.detected_type_label ?? "自動判定"
                  : getLabelForType(selectValue) ?? document.selected_type_label ?? "未判定";
              const processingLabel =
                document.processing_status != null
                  ? processingStatusLabel[document.processing_status] ?? document.processing_status
                  : "-";
              const statusClass =
                document.status === "accepted"
                  ? "inline-flex h-7 items-center rounded-full bg-emerald-500/20 px-3 text-xs font-semibold text-emerald-200"
                  : "inline-flex h-7 items-center rounded-full bg-red-500/20 px-3 text-xs font-semibold text-red-200";

              const isSelected = document.document_id ? selectedDocIds.has(document.document_id) : false;
              const canSelect = document.document_id && document.processing_status === "structured";

              return (
                <article
                  key={key}
                  className={`rounded-lg border p-5 transition-all ${
                    isSelected
                      ? "border-cyan-500/40 bg-cyan-500/10 shadow-lg shadow-cyan-500/10"
                      : "border-white/20 bg-white/5 hover:border-white/30 hover:bg-white/8"
                  }`}
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="flex items-start gap-3">
                      {canSelect && (
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleDocSelection(document.document_id!)}
                          className="mt-1 h-4 w-4 rounded border-white/30 bg-white/10 text-cyan-500 focus:ring-2 focus:ring-cyan-500/50"
                        />
                      )}
                      <div className="flex-1">
                        <h3 className="text-base font-semibold text-white">{document.filename}</h3>
                        <p className="mt-1 text-xs text-white/50">
                          {bytesToReadable(document.size_bytes)} · {document.document_id ?? "未割当"}
                        </p>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-md bg-white/10 px-2.5 py-1 text-xs font-medium text-white/80">
                        {document.status === "accepted" ? "Accepted" : "Rejected"}
                      </span>
                      <span className="rounded-md border border-white/20 bg-white/5 px-2.5 py-1 text-xs text-white/70">
                        {processingLabel}
                      </span>
                      {document.document_id && (
                        <button
                          type="button"
                          onClick={() => setDeleteConfirmId(document.document_id!)}
                          className="rounded-md border border-white/20 bg-white/5 px-2.5 py-1 text-xs text-white/70 transition-colors hover:bg-white/10 hover:text-white"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    <label className="flex flex-col gap-1.5 text-xs text-white/60">
                      Document Type
                      <select
                        value={selectValue}
                        onChange={(event) => handleOverrideChange(document, event.target.value)}
                        disabled={!document.document_id || isUpdating}
                        className="rounded-md border border-white/20 bg-white/5 px-3 py-2 text-sm text-white focus:border-white/40 focus:outline-none focus:ring-1 focus:ring-white/30 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <option value={AUTO_OPTION_VALUE}>Auto-detect</option>
                        {DOCUMENT_TYPE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      {isUpdating ? (
                        <span className="text-[11px] text-white/50">Updating...</span>
                      ) : null}
                    </label>
                    <div className="flex flex-col gap-1.5 text-xs text-white/60">
                      Current Label
                      <span className="rounded-md border border-white/20 bg-white/5 px-3 py-2 text-sm text-white">
                        {selectedLabel ?? "未判定"}
                      </span>
                    </div>
                    <div className="flex flex-col gap-1.5 text-xs text-white/60">
                      Confidence
                      <span className="rounded-md border border-white/20 bg-white/5 px-3 py-2 text-sm text-white">
                        {document.detection_confidence != null
                          ? `${Math.round(document.detection_confidence * 100)}%`
                          : "-"}
                      </span>
                    </div>
                    <div className="flex flex-col gap-1.5 text-xs text-white/60">
                      Detection Reason
                      <span className="rounded-md border border-white/20 bg-white/5 px-3 py-2 text-sm text-white/80">
                        {document.detection_reason
                          ? document.detection_reason
                          : "-"}
                      </span>
                    </div>
                  </div>

                  {document.errors.length > 0 ? (
                    <div className="mt-4 rounded-lg border border-white/20 bg-white/5 px-4 py-3">
                      <h4 className="text-sm font-medium text-white/90">Errors</h4>
                      <ul className="mt-2 space-y-1 text-xs text-white/70">
                        {document.errors.map((error) => (
                          <li key={error}>• {error}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {document.processing_status === "pending_classification" && 
                   (!document.selected_type || document.selected_type === "unknown") ? (
                    <div className="mt-4 rounded-lg border border-white/20 bg-white/5 px-4 py-3">
                      <h4 className="text-sm font-medium text-white/90">Document Type Required</h4>
                      <p className="mt-2 text-xs leading-relaxed text-white/60">
                        書類種別が未判定のため、構造化処理が開始されていません。
                        上記のプルダウンから適切な書類種別を選択すると、自動的に構造化処理が開始されます。
                      </p>
                    </div>
                  ) : null}

                  {document.processing_status === "structured" && document.structured_data ? (
                    <StructuredDataDisplay document={document} />
                  ) : null}
                </article>
              );
            })}
          </div>
            </>
          )}

          {/* 比較結果タブの内容 */}
          {activeTab === "comparison" && (
        <div className="flex gap-6">
          {/* 左側: 比較履歴リスト */}
          <div className="w-80 shrink-0 space-y-3">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-sm font-semibold text-white">Comparison History</h3>
              <span className="text-xs text-white/50">{comparisonHistory.length} items</span>
            </div>
            
            <div className="max-h-[calc(100vh-20rem)] space-y-2 overflow-y-auto pr-2">
              {comparisonHistory.length === 0 ? (
                <p className="py-8 text-center text-sm text-white/50">No comparison history</p>
              ) : (
                comparisonHistory.map((item) => (
                  <button
                    key={item.comparison_id}
                    type="button"
                    onClick={async () => {
                      try {
                        const result = await getComparisonResult(item.comparison_id);
                        setComparisonResult(result);
                        setSelectedHistoryId(item.comparison_id);
                      } catch (error) {
                        console.error("比較結果の読み込みに失敗:", error);
                      }
                    }}
                    className={`w-full rounded-lg border p-3 text-left transition-all ${
                      selectedHistoryId === item.comparison_id
                        ? "border-cyan-500/40 bg-cyan-500/10"
                        : "border-white/20 bg-white/5 hover:border-white/30 hover:bg-white/10"
                    }`}
                  >
                    <div className="mb-1.5 flex items-start justify-between gap-2">
                      <span className="text-xs font-medium text-white/90">
                        {item.doc1_filename} vs {item.doc2_filename}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-white/50">
                      <span>{item.section_count} sections</span>
                      <span>·</span>
                      <span>{new Date(item.created_at).toLocaleDateString()}</span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
          
          {/* 右側: 比較結果詳細 */}
          {comparisonResult ? (
        <div className="min-w-0 flex-1 space-y-6">
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <h2 className="text-2xl font-semibold text-white">比較結果</h2>
            <div className="flex gap-3">
              {/* <button
                type="button"
                onClick={() => setActiveTab("documents")}
                className="rounded-md border border-white/20 bg-white/5 px-4 py-2 text-sm text-white/90 transition-colors hover:bg-white/10"
              >
                ← 一覧に戻る
              </button>
              <button
                type="button"
                onClick={() => {
                  setComparisonResult(null);
                  setActiveTab("documents");
                }}
                className="rounded-md border border-white/20 bg-white/5 px-4 py-2 text-sm text-white/70 transition-colors hover:bg-white/10 hover:text-white"
              >
                × 閉じる
              </button> */}
            </div>
          </div>
          
          {/* サマリーダッシュボード */}
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-lg border border-white/20 bg-white/5 p-4">
              <div className="text-xs font-medium uppercase tracking-wider text-white/50">Total Sections</div>
              <div className="mt-1 text-2xl font-semibold text-white">
                {comparisonResult.section_detailed_comparisons?.length || 0}
              </div>
            </div>
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
              <div className="text-xs font-medium uppercase tracking-wider text-amber-200/70">High Priority</div>
              <div className="mt-1 text-2xl font-semibold text-amber-100">
                {comparisonResult.section_detailed_comparisons?.filter((s: any) => s.importance === "high").length || 0}
              </div>
            </div>
            <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-4">
              <div className="text-xs font-medium uppercase tracking-wider text-yellow-200/70">Medium Priority</div>
              <div className="mt-1 text-2xl font-semibold text-yellow-100">
                {comparisonResult.section_detailed_comparisons?.filter((s: any) => s.importance === "medium").length || 0}
              </div>
            </div>
            <div className="rounded-lg border border-blue-500/30 bg-blue-500/10 p-4">
              <div className="text-xs font-medium uppercase tracking-wider text-blue-200/70">Numerical Changes</div>
              <div className="mt-1 text-2xl font-semibold text-blue-100">
                {comparisonResult.numerical_differences?.length || 0}
              </div>
            </div>
          </div>
          
          <div className="space-y-5">
              {/* 基本情報 */}
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-lg border border-white/20 bg-white/5 p-4">
                  <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-white/70">Document 1</h3>
                  <div className="space-y-1.5">
                    <p className="text-sm text-white">
                      <span className="text-white/60">ファイル名:</span> {comparisonResult.doc1_info?.filename || "不明"}
                    </p>
                    <p className="text-sm text-white">
                      <span className="text-white/60">会社名:</span> {comparisonResult.doc1_info?.company_name || "未抽出"}
                    </p>
                    <p className="text-sm text-white">
                      <span className="text-white/60">年度:</span> {comparisonResult.doc1_info?.fiscal_year || "未抽出"}
                    </p>
                  </div>
                </div>
                <div className="rounded-lg border border-white/20 bg-white/5 p-4">
                  <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-white/70">Document 2</h3>
                  <div className="space-y-1.5">
                    <p className="text-sm text-white">
                      <span className="text-white/60">ファイル名:</span> {comparisonResult.doc2_info?.filename || "不明"}
                    </p>
                    <p className="text-sm text-white">
                      <span className="text-white/60">会社名:</span> {comparisonResult.doc2_info?.company_name || "未抽出"}
                    </p>
                    <p className="text-sm text-white">
                      <span className="text-white/60">年度:</span> {comparisonResult.doc2_info?.fiscal_year || "未抽出"}
                    </p>
                  </div>
                </div>
              </div>
              
              {/* 比較モード */}
              <div className="rounded-lg border border-white/20 bg-white/5 p-4">
                <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-white/70">Comparison Mode</h3>
                <p className="text-sm text-white">
                  {comparisonResult.mode === "consistency_check" && "整合性チェックモード（同じ会社の異なる書類）"}
                  {comparisonResult.mode === "diff_analysis_company" && "差分分析モード（異なる会社の同じ書類）"}
                  {comparisonResult.mode === "diff_analysis_year" && "差分分析モード（同じ会社の異なる年度）"}
                  {comparisonResult.mode === "multi_document" && "多資料比較モード"}
                </p>
              </div>
              
              {/* セクションマッピング */}
              {comparisonResult.section_mappings && comparisonResult.section_mappings.length > 0 && (
                <details className="rounded-lg border border-white/20 bg-white/5">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-white hover:bg-white/5">
                    Section Mappings ({comparisonResult.section_mappings.length})
                  </summary>
                  <div className="border-t border-white/10 px-4 py-3">
                    <div className="space-y-1.5">
                      {comparisonResult.section_mappings.map((mapping: any, idx: number) => (
                        <div key={idx} className="flex items-start justify-between border-b border-white/5 py-2 text-xs last:border-0">
                          <div className="flex-1">
                            <span className="text-white">{mapping.doc1_section}</span>
                            <span className="mx-2 text-white/40">↔</span>
                            <span className="text-white">{mapping.doc2_section}</span>
                          </div>
                          <div className="ml-4 flex gap-2 text-[10px] text-white/50">
                            <span>{(mapping.confidence_score * 100).toFixed(0)}%</span>
                            <span className="text-white/30">·</span>
                            <span>{mapping.mapping_method}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </details>
              )}
              
              {/* 数値差分 */}
              {comparisonResult.numerical_differences && comparisonResult.numerical_differences.length > 0 && (
                <details className="rounded-lg border border-white/20 bg-white/5">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-white hover:bg-white/5">
                    Numerical Differences ({comparisonResult.numerical_differences.length})
                  </summary>
                  <div className="border-t border-white/10 px-4 py-3">
                    <div className="space-y-1.5">
                      {comparisonResult.numerical_differences.map((diff: any, idx: number) => (
                        <div key={idx} className="border-b border-white/5 py-2 text-xs last:border-0">
                          <div className="font-medium text-white/90">{diff.section} - {diff.item_name}</div>
                          <div className="mt-1 flex items-center gap-2 text-white/60">
                            <span>{typeof diff.value1 === 'object' ? JSON.stringify(diff.value1) : (diff.value1 ?? "N/A")}</span>
                            <span className="text-white/30">→</span>
                            <span>{typeof diff.value2 === 'object' ? JSON.stringify(diff.value2) : (diff.value2 ?? "N/A")}</span>
                            {(typeof diff.difference === "number" || (diff.difference_pct != null && typeof diff.difference_pct === "number" && !isNaN(diff.difference_pct))) && (
                              <span className="ml-2 text-white/40">
                                (差: {typeof diff.difference === "number" ? diff.difference.toFixed(2) : "N/A"}
                                {diff.difference_pct != null && typeof diff.difference_pct === "number" && !isNaN(diff.difference_pct) && `, ${diff.difference_pct.toFixed(2)}%`})
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </details>
              )}
              
              {/* テキスト差分 */}
              {comparisonResult.text_differences && comparisonResult.text_differences.length > 0 && (
                <details className="rounded-lg border border-white/20 bg-white/5">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-white hover:bg-white/5">
                    Text Differences ({comparisonResult.text_differences.length})
                  </summary>
                  <div className="border-t border-white/10 px-4 py-3">
                    <div className="space-y-1.5">
                      {comparisonResult.text_differences.map((diff: any, idx: number) => (
                        <div key={idx} className="flex items-center justify-between border-b border-white/5 py-2 text-xs last:border-0">
                          <span className="text-white">{diff.section}</span>
                          <span className="ml-4 text-white/50">一致率 {(diff.match_ratio * 100).toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </details>
              )}
              
              {/* セクション別詳細差分 */}
              {comparisonResult.section_detailed_comparisons && comparisonResult.section_detailed_comparisons.length > 0 && (
                <div className="rounded-lg border border-white/20 bg-white/5 p-5">
                  <div className="mb-4 flex items-center justify-between">
                    <h3 className="text-base font-semibold text-white">
                      Detailed Comparisons ({(() => {
                        let filtered = comparisonResult.section_detailed_comparisons;
                        if (importanceFilter !== "all") {
                          filtered = filtered.filter((d: any) => d.importance === importanceFilter);
                        }
                        if (searchQuery) {
                          filtered = filtered.filter((d: any) => 
                            d.section_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            d.summary?.toLowerCase().includes(searchQuery.toLowerCase())
                          );
                        }
                        return filtered.length;
                      })()}/{comparisonResult.section_detailed_comparisons.length})
                    </h3>
                  </div>
                  
                  {/* フィルタリングUI */}
                  <div className="mb-4 flex flex-col gap-3 sm:flex-row">
                    <div className="flex-1">
                      <input
                        type="text"
                        placeholder="検索..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full rounded-md border border-white/20 bg-white/5 px-3 py-2 text-sm text-white placeholder-white/40 focus:border-white/40 focus:outline-none focus:ring-1 focus:ring-white/30"
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setImportanceFilter("all")}
                        className={`rounded-md px-3 py-2 text-xs font-medium transition-colors ${
                          importanceFilter === "all"
                            ? "bg-white/20 text-white"
                            : "bg-white/5 text-white/60 hover:bg-white/10 hover:text-white/80"
                        }`}
                      >
                        All
                      </button>
                      <button
                        type="button"
                        onClick={() => setImportanceFilter("high")}
                        className={`rounded-md px-3 py-2 text-xs font-medium transition-colors ${
                          importanceFilter === "high"
                            ? "bg-amber-500/20 text-amber-200 border border-amber-500/30"
                            : "bg-white/5 text-white/60 hover:bg-amber-500/10 hover:text-amber-300/80"
                        }`}
                      >
                        High
                      </button>
                      <button
                        type="button"
                        onClick={() => setImportanceFilter("medium")}
                        className={`rounded-md px-3 py-2 text-xs font-medium transition-colors ${
                          importanceFilter === "medium"
                            ? "bg-yellow-500/20 text-yellow-200 border border-yellow-500/30"
                            : "bg-white/5 text-white/60 hover:bg-yellow-500/10 hover:text-yellow-300/80"
                        }`}
                      >
                        Medium
                      </button>
                      <button
                        type="button"
                        onClick={() => setImportanceFilter("low")}
                        className={`rounded-md px-3 py-2 text-xs font-medium transition-colors ${
                          importanceFilter === "low"
                            ? "bg-white/20 text-white border border-white/30"
                            : "bg-white/5 text-white/60 hover:bg-white/10 hover:text-white/80"
                        }`}
                      >
                        Low
                      </button>
                    </div>
                  </div>
                  
                  <div className="mt-4 space-y-3">
                    {(() => {
                      let filtered = comparisonResult.section_detailed_comparisons;
                      if (importanceFilter !== "all") {
                        filtered = filtered.filter((d: any) => d.importance === importanceFilter);
                      }
                      if (searchQuery) {
                        filtered = filtered.filter((d: any) => 
                          d.section_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          d.summary?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          d.doc1_section_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          d.doc2_section_name?.toLowerCase().includes(searchQuery.toLowerCase())
                        );
                      }
                      // Doc1のページ番号でソート（昇順）、次にDoc2のページ番号でソート
                      filtered.sort((a: any, b: any) => {
                        const getStartPage = (pageRange: string) => {
                          if (!pageRange) return 0;
                          const match = pageRange.match(/^(\d+)/);
                          return match ? parseInt(match[1], 10) : 0;
                        };
                        const doc1Diff = getStartPage(a.doc1_page_range) - getStartPage(b.doc1_page_range);
                        if (doc1Diff !== 0) return doc1Diff;
                        // 同じdoc1ページの場合、doc2ページでソート
                        return getStartPage(a.doc2_page_range) - getStartPage(b.doc2_page_range);
                      });
                      
                      // 1:Nマッピング情報を計算
                      const doc1SectionCounts = new Map<string, number>();
                      const doc1SectionIndices = new Map<string, number>();
                      filtered.forEach((d: any) => {
                        const key = d.doc1_section_name || d.section_name;
                        doc1SectionCounts.set(key, (doc1SectionCounts.get(key) || 0) + 1);
                      });
                      
                      return filtered.map((detail: any, idx: number) => {
                        const doc1Key = detail.doc1_section_name || detail.section_name;
                        const currentIndex = (doc1SectionIndices.get(doc1Key) || 0) + 1;
                        doc1SectionIndices.set(doc1Key, currentIndex);
                        const totalCount = doc1SectionCounts.get(doc1Key) || 1;
                        const isMultiMapping = totalCount > 1;
                        
                        return { detail, idx, currentIndex, totalCount, isMultiMapping };
                      });
                    })().map(({ detail, idx, currentIndex, totalCount, isMultiMapping }) => (
                      <div key={idx} className={`rounded-lg border border-white/20 bg-white/5 p-4 transition-all hover:border-white/30 hover:bg-white/10 relative overflow-hidden ${
                        isMultiMapping ? 'pl-6' : ''
                      }`}>
                        {/* 1:Nマッピング用のカラーバー */}
                        {isMultiMapping && (
                          <div 
                            className={`absolute left-0 top-0 bottom-0 w-1 ${
                              currentIndex === 1 ? 'bg-blue-500' :
                              currentIndex === 2 ? 'bg-emerald-500' :
                              currentIndex === 3 ? 'bg-purple-500' :
                              currentIndex === 4 ? 'bg-pink-500' :
                              'bg-cyan-500'
                            }`}
                          />
                        )}
                        
                        {/* セクションヘッダー */}
                        <div className="mb-3 flex items-start justify-between gap-3">
                          <div className="flex-1">
                            <h4 className="text-base font-semibold text-white mb-1">
                              {detail.section_name}
                              {isMultiMapping && (
                                <span className="ml-2 text-xs font-normal text-white/50">
                                  ({currentIndex}/{totalCount})
                                </span>
                              )}
                            </h4>
                            
                            {/* マッピング情報（古い比較結果との互換性のためフォールバック付き） */}
                            {(detail.doc1_section_name || detail.doc2_section_name || detail.mapping_method) && (
                              <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 mt-1 text-xs text-white/60">
                                {(detail.doc1_section_name || detail.doc2_section_name) && (
                                  <div className="flex items-center gap-2">
                                    <span className="font-medium">{detail.doc1_section_name || detail.section_name}</span>
                                    <span>→</span>
                                    <span className="font-medium text-blue-300">{detail.doc2_section_name || detail.section_name}</span>
                                  </div>
                                )}
                                
                                {/* マッピング方法と信頼度 */}
                                {detail.mapping_method && (
                                  <div className="flex items-center gap-1 flex-wrap">
                                    {detail.mapping_method === "exact" ? (
                                      <span className="rounded px-1.5 py-0.5 bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-medium">
                                        完全一致 ✓
                                      </span>
                                    ) : (
                                      <>
                                        <span className="rounded px-1.5 py-0.5 bg-blue-500/20 text-blue-300 border border-blue-500/30 text-[10px] font-medium">
                                          {detail.mapping_method}
                                        </span>
                                        {detail.mapping_confidence != null && (
                                          <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                                            detail.mapping_confidence >= 0.9
                                              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                              : detail.mapping_confidence >= 0.7
                                                ? "bg-yellow-500/20 text-yellow-300 border border-yellow-500/30"
                                                : "bg-orange-500/20 text-orange-300 border border-orange-500/30"
                                          }`}>
                                            信頼度: {Math.round(detail.mapping_confidence * 100)}%
                                          </span>
                                        )}
                                      </>
                                    )}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                          
                          <span
                            className={`rounded-md px-2.5 py-1 text-xs font-medium flex-shrink-0 ${
                              detail.importance === "high"
                                ? "bg-amber-500/20 text-amber-200 border border-amber-500/30"
                                : detail.importance === "medium"
                                  ? "bg-yellow-500/20 text-yellow-200 border border-yellow-500/30"
                                  : "bg-white/10 text-white/70 border border-white/20"
                            }`}
                          >
                            {detail.importance === "high" ? "High" : detail.importance === "medium" ? "Medium" : "Low"}
                          </span>
                        </div>
                        
                        <div className="mb-3 flex items-center gap-4 text-xs text-white/50">
                          <span>Doc1: p.{detail.doc1_page_range}</span>
                          <span className="text-white/30">•</span>
                          <span>Doc2: p.{detail.doc2_page_range}</span>
                        </div>
                        
                        {/* サマリー */}
                        <div className={`mb-4 rounded-md border p-3 ${
                          detail.summary?.includes('失敗') || detail.importance_reason?.includes('失敗') 
                            ? 'border-red-500/30 bg-red-500/10' 
                            : 'border-white/10 bg-white/5'
                        }`}>
                          <p className="text-sm leading-relaxed text-white/90">
                            {detail.summary}
                          </p>
                          {detail.importance_reason && (
                            <p className="mt-2 border-t border-white/10 pt-2 text-xs leading-relaxed text-white/60">
                              {detail.importance_reason}
                            </p>
                          )}
                        </div>
                        
                        {/* 追加探索結果 */}
                        {detail.has_additional_context && detail.additional_searches && detail.additional_searches.length > 0 && (
                          <details className="mb-4 rounded-md border border-cyan-500/30 bg-cyan-500/10 p-3" open>
                            <summary className="cursor-pointer text-sm font-semibold text-cyan-200 hover:text-cyan-100">
                              追加探索結果 ({detail.additional_searches.length}回)
                            </summary>
                            <div className="mt-3 space-y-3 border-t border-cyan-500/20 pt-3">
                              {detail.additional_searches.map((search: any, searchIdx: number) => (
                                <div key={searchIdx} className="rounded-md border border-cyan-500/20 bg-cyan-500/5 p-3">
                                  <div className="mb-2 flex items-center gap-2">
                                    <span className="rounded px-2 py-1 bg-cyan-500/20 text-cyan-200 text-xs font-medium">
                                      第{search.iteration}回探索
                                    </span>
                                    {search.found_sections && search.found_sections.length > 0 && (
                                      <span className="text-xs text-cyan-200/70">
                                        {search.found_sections.length}個のセクションを発見
                                      </span>
                                    )}
                                  </div>
                                  
                                  {search.search_keywords && search.search_keywords.length > 0 && (
                                    <div className="mb-2">
                                      <div className="text-xs font-medium text-cyan-200/90 mb-1">検索フレーズ:</div>
                                      <div className="flex flex-wrap gap-1">
                                        {search.search_keywords.map((keyword: string, kwIdx: number) => (
                                          <span key={kwIdx} className="rounded px-2 py-0.5 bg-cyan-500/20 text-cyan-200 text-xs">
                                            {keyword}
                                          </span>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                  
                                  {search.found_sections && search.found_sections.length > 0 && (
                                    <div className="mb-2">
                                      <div className="text-xs font-medium text-cyan-200/90 mb-1">発見されたセクション:</div>
                                      <div className="space-y-1">
                                        {search.found_sections.map((found: any, foundIdx: number) => (
                                          <div key={foundIdx} className="flex items-center gap-2 text-xs text-cyan-200/80">
                                            <span>{found.doc1_section || found.doc2_section}</span>
                                            {found.similarity != null && (
                                              <span className="text-cyan-200/50">
                                                (類似度: {Math.round(found.similarity * 100)}%)
                                              </span>
                                            )}
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                  
                                  {search.analysis && Object.keys(search.analysis).length > 0 && (
                                    <div className="mt-2 border-t border-cyan-500/20 pt-2">
                                      {search.analysis.new_findings && search.analysis.new_findings.length > 0 && (
                                        <div className="mb-2">
                                          <div className="text-xs font-medium text-cyan-200/90 mb-1">新たに分かったこと:</div>
                                          <ul className="list-disc list-inside space-y-1 text-xs text-cyan-200/80">
                                            {search.analysis.new_findings.map((finding: string, findingIdx: number) => (
                                              <li key={findingIdx}>{finding}</li>
                                            ))}
                                          </ul>
                                        </div>
                                      )}
                                      {search.analysis.enhanced_understanding && (
                                        <div className="text-xs text-cyan-200/80">
                                          <span className="font-medium text-cyan-200/90">理解の深まり: </span>
                                          {search.analysis.enhanced_understanding}
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </details>
                        )}
                        
                        {/* 変更詳細 */}
                        {detail.text_changes && Object.keys(detail.text_changes).length > 0 && (() => {
                          const isCompanyComparison = comparisonResult?.mode === 'diff_analysis_company';
                          const company1Name = comparisonResult?.doc1_info?.company_name || '会社A';
                          const company2Name = comparisonResult?.doc2_info?.company_name || '会社B';
                          
                          return (
                            <div className="mb-3 space-y-1.5">
                              {/* 会社間比較の場合 */}
                              {isCompanyComparison && (
                                <>
                                  {detail.text_changes.only_in_company1 && detail.text_changes.only_in_company1.length > 0 && (
                                    <details className="rounded-md border border-blue-500/30 bg-blue-500/5">
                                      <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-blue-200 hover:bg-blue-500/10">
                                        {company1Name} のみ ({detail.text_changes.only_in_company1.length})
                                      </summary>
                                      <div className="border-t border-blue-500/20 px-3 py-2">
                                        <ul className="space-y-1">
                                          {detail.text_changes.only_in_company1.map((item: string, i: number) => (
                                            <li key={i} className="text-xs leading-relaxed text-blue-100/90">• {item}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    </details>
                                  )}
                                  {detail.text_changes.only_in_company2 && detail.text_changes.only_in_company2.length > 0 && (
                                    <details className="rounded-md border border-purple-500/30 bg-purple-500/5">
                                      <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-purple-200 hover:bg-purple-500/10">
                                        {company2Name} のみ ({detail.text_changes.only_in_company2.length})
                                      </summary>
                                      <div className="border-t border-purple-500/20 px-3 py-2">
                                        <ul className="space-y-1">
                                          {detail.text_changes.only_in_company2.map((item: string, i: number) => (
                                            <li key={i} className="text-xs leading-relaxed text-purple-100/90">• {item}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    </details>
                                  )}
                                  {detail.text_changes.different_approaches && detail.text_changes.different_approaches.length > 0 && (
                                    <details className="rounded-md border border-amber-500/30 bg-amber-500/5">
                                      <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-amber-200 hover:bg-amber-500/10">
                                        開示方針の違い ({detail.text_changes.different_approaches.length})
                                      </summary>
                                      <div className="border-t border-amber-500/20 px-3 py-2">
                                        <div className="space-y-2">
                                          {detail.text_changes.different_approaches.map((item: any, i: number) => (
                                            <div key={i} className="text-xs rounded bg-white/5 p-2">
                                              <div className="font-medium text-amber-100/90 mb-1">{item.aspect}</div>
                                              <div className="text-blue-200/80"><span className="font-medium">{company1Name}:</span> {item.company1_approach}</div>
                                              <div className="text-purple-200/80"><span className="font-medium">{company2Name}:</span> {item.company2_approach}</div>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    </details>
                                  )}
                                </>
                              )}
                              
                              {/* 年度間比較・整合性チェックの場合 */}
                              {!isCompanyComparison && (
                                <>
                                  {/* 整合性チェック専用の表示 */}
                                  {detail.text_changes.contradictions && detail.text_changes.contradictions.length > 0 && (
                                    <details className="rounded-md border border-rose-500/30 bg-rose-500/5">
                                      <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-rose-200 hover:bg-rose-500/10">
                                        ⚠️ 矛盾・不整合 ({detail.text_changes.contradictions.length})
                                      </summary>
                                      <div className="border-t border-rose-500/20 px-3 py-2">
                                        <div className="space-y-2">
                                          {detail.text_changes.contradictions.map((item: any, i: number) => (
                                            <div key={i} className="text-xs rounded bg-white/5 p-2">
                                              <div className="font-medium text-rose-100/90 mb-1">{item.type}</div>
                                              <div className="text-rose-200/80 mb-1">{item.description}</div>
                                              <div className="text-rose-300/70 text-[11px]">影響: {item.impact}</div>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    </details>
                                  )}
                                  
                                  {detail.text_changes.normal_differences && detail.text_changes.normal_differences.length > 0 && (
                                    <details className="rounded-md border border-blue-500/30 bg-blue-500/5">
                                      <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-blue-200 hover:bg-blue-500/10">
                                        📋 書類の性質による正常な違い ({detail.text_changes.normal_differences.length})
                                      </summary>
                                      <div className="border-t border-blue-500/20 px-3 py-2">
                                        <div className="space-y-2">
                                          {detail.text_changes.normal_differences.map((item: any, i: number) => (
                                            <div key={i} className="text-xs rounded bg-white/5 p-2">
                                              <div className="font-medium text-blue-100/90 mb-1">{item.aspect}</div>
                                              <div className="text-blue-200/80 mb-1">
                                                <span className="font-medium">{comparisonResult?.doc1_info?.document_type_label}:</span> {item.doc1_approach}
                                              </div>
                                              <div className="text-purple-200/80 mb-1">
                                                <span className="font-medium">{comparisonResult?.doc2_info?.document_type_label}:</span> {item.doc2_approach}
                                              </div>
                                              <div className="text-blue-300/70 text-[11px]">理由: {item.reason}</div>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    </details>
                                  )}
                                  
                                  {detail.text_changes.complementary_info && detail.text_changes.complementary_info.length > 0 && (
                                    <details className="rounded-md border border-emerald-500/30 bg-emerald-500/5">
                                      <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-emerald-200 hover:bg-emerald-500/10">
                                        🔄 相互補完関係 ({detail.text_changes.complementary_info.length})
                                      </summary>
                                      <div className="border-t border-emerald-500/20 px-3 py-2">
                                        <div className="space-y-2">
                                          {detail.text_changes.complementary_info.map((item: any, i: number) => (
                                            <div key={i} className="text-xs rounded bg-white/5 p-2">
                                              <div className="font-medium text-emerald-100/90 mb-1">{item.topic}</div>
                                              <div className="text-emerald-200/80 mb-1">
                                                <span className="font-medium">{comparisonResult?.doc1_info?.document_type_label}:</span> {item.doc1_contribution}
                                              </div>
                                              <div className="text-emerald-200/80 mb-1">
                                                <span className="font-medium">{comparisonResult?.doc2_info?.document_type_label}:</span> {item.doc2_contribution}
                                              </div>
                                              <div className="text-emerald-300/70 text-[11px]">{item.relationship}</div>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    </details>
                                  )}
                                  
                                  {detail.text_changes.consistency_score && (
                                    <div className="rounded-md border border-white/10 bg-white/5 px-3 py-2">
                                      <div className="flex items-center justify-between text-xs">
                                        <span className="text-white/70">整合性スコア:</span>
                                        <div className="flex items-center gap-2">
                                          <div className="flex gap-0.5">
                                            {[1, 2, 3, 4, 5].map((score) => (
                                              <div
                                                key={score}
                                                className={`w-6 h-6 rounded flex items-center justify-center text-[10px] font-bold ${
                                                  score <= detail.text_changes.consistency_score
                                                    ? score <= 2
                                                      ? 'bg-rose-500 text-white'
                                                      : score === 3
                                                        ? 'bg-amber-500 text-white'
                                                        : 'bg-emerald-500 text-white'
                                                    : 'bg-white/10 text-white/30'
                                                }`}
                                              >
                                                {score}
                                              </div>
                                            ))}
                                          </div>
                                          <span className={`font-medium ${
                                            detail.text_changes.consistency_score <= 2
                                              ? 'text-rose-300'
                                              : detail.text_changes.consistency_score === 3
                                                ? 'text-amber-300'
                                                : 'text-emerald-300'
                                          }`}>
                                            {detail.text_changes.consistency_score}/5
                                          </span>
                                        </div>
                                      </div>
                                      {detail.text_changes.consistency_reason && (
                                        <div className="mt-2 text-[11px] text-white/60 leading-relaxed">
                                          {detail.text_changes.consistency_reason}
                                        </div>
                                      )}
                                    </div>
                                  )}
                                  
                                  {/* 年度間比較の表示 */}
                                  {detail.text_changes.added && detail.text_changes.added.length > 0 && (
                                    <details className="rounded-md border border-emerald-500/30 bg-emerald-500/5">
                                      <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-emerald-200 hover:bg-emerald-500/10">
                                        Added ({detail.text_changes.added.length})
                                      </summary>
                                      <div className="border-t border-emerald-500/20 px-3 py-2">
                                        <ul className="space-y-1">
                                          {detail.text_changes.added.map((item: string, i: number) => (
                                            <li key={i} className="text-xs leading-relaxed text-emerald-100/90">+ {item}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    </details>
                                  )}
                                  {detail.text_changes.removed && detail.text_changes.removed.length > 0 && (
                                    <details className="rounded-md border border-rose-500/30 bg-rose-500/5">
                                      <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-rose-200 hover:bg-rose-500/10">
                                        Removed ({detail.text_changes.removed.length})
                                      </summary>
                                      <div className="border-t border-rose-500/20 px-3 py-2">
                                        <ul className="space-y-1">
                                          {detail.text_changes.removed.map((item: string, i: number) => (
                                            <li key={i} className="text-xs leading-relaxed text-rose-100/90">- {item}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    </details>
                                  )}
                                  {detail.text_changes.modified && detail.text_changes.modified.length > 0 && (
                                    <details className="rounded-md border border-blue-500/30 bg-blue-500/5">
                                      <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-blue-200 hover:bg-blue-500/10">
                                        Modified ({detail.text_changes.modified.length})
                                      </summary>
                                      <div className="border-t border-blue-500/20 px-3 py-2">
                                        <div className="space-y-2">
                                          {detail.text_changes.modified.map((item: any, i: number) => (
                                            <div key={i} className="text-xs">
                                              <div className="text-rose-200/80">- {item.before}</div>
                                              <div className="text-emerald-200/80">+ {item.after}</div>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    </details>
                                  )}
                                </>
                              )}
                            </div>
                          );
                        })()}
                        
                        {/* 数値変更 */}
                        {detail.numerical_changes && detail.numerical_changes.length > 0 && (() => {
                          const isCompanyComparison = comparisonResult?.mode === 'diff_analysis_company';
                          const company1Name = comparisonResult?.doc1_info?.company_name || '会社A';
                          const company2Name = comparisonResult?.doc2_info?.company_name || '会社B';
                          
                          return (
                            <details className="mb-3 rounded-md border border-white/10 bg-white/5">
                              <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-white/80 hover:bg-white/10">
                                {isCompanyComparison ? '数値指標の比較' : 'Numerical Changes'} ({detail.numerical_changes.length})
                              </summary>
                              <div className="border-t border-white/10 px-3 py-2">
                                <div className="space-y-1.5">
                                  {detail.numerical_changes.map((change: any, i: number) => (
                                    <div key={i} className="text-xs">
                                      <div className="font-medium text-white/80">
                                        {isCompanyComparison ? (change.metric || change.item) : change.item}
                                      </div>
                                      <div className="mt-0.5 flex items-center gap-2 text-white/60">
                                        {isCompanyComparison ? (
                                          <>
                                            <span className="text-blue-200/80">{company1Name}: {
                                              typeof change.company1_value === 'object' 
                                                ? JSON.stringify(change.company1_value) 
                                                : (change.company1_value ?? change.value1 ?? "N/A")
                                            }</span>
                                            <span className="text-white/30">•</span>
                                            <span className="text-purple-200/80">{company2Name}: {
                                              typeof change.company2_value === 'object' 
                                                ? JSON.stringify(change.company2_value) 
                                                : (change.company2_value ?? change.value2 ?? "N/A")
                                            }</span>
                                          </>
                                        ) : (
                                          <>
                                            <span>{
                                              typeof change.value1 === 'object' 
                                                ? JSON.stringify(change.value1) 
                                                : (change.value1 ?? "N/A")
                                            }</span>
                                            <span className="text-white/30">→</span>
                                            <span>{
                                              typeof change.value2 === 'object' 
                                                ? JSON.stringify(change.value2) 
                                                : (change.value2 ?? "N/A")
                                            }</span>
                                          </>
                                        )}
                                        {(change.change_pct != null || change.difference_pct != null) && (
                                          typeof (change.change_pct ?? change.difference_pct) === "number" && 
                                          !isNaN(change.change_pct ?? change.difference_pct) && (
                                            <span className="text-white/40">
                                              ({(change.change_pct ?? change.difference_pct) > 0 ? "+" : ""}
                                              {(change.change_pct ?? change.difference_pct).toFixed(1)}%)
                                            </span>
                                          )
                                        )}
                                      </div>
                                      {isCompanyComparison && change.context && (
                                        <div className="mt-1 text-white/50 italic">{change.context}</div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </details>
                          );
                        })()}
                        
                        {/* トーン分析 */}
                        {detail.tone_analysis && Object.keys(detail.tone_analysis).length > 0 && (() => {
                          const isCompanyComparison = comparisonResult?.mode === 'diff_analysis_company';
                          const company1Name = comparisonResult?.doc1_info?.company_name || '会社A';
                          const company2Name = comparisonResult?.doc2_info?.company_name || '会社B';
                          
                          return (
                            <div className="mt-3 rounded-md border border-white/10 bg-white/5 p-3 text-xs">
                              <div className="text-white/70">
                                <span className="font-medium text-white/90">
                                  {isCompanyComparison ? '開示トーン:' : 'Tone:'}
                                </span>
                                {" "}
                                {isCompanyComparison ? (
                                  <>
                                    <span className="text-blue-200/80">
                                      {company1Name}: {detail.tone_analysis.company1_tone || detail.tone_analysis.tone1}
                                    </span>
                                    {" • "}
                                    <span className="text-purple-200/80">
                                      {company2Name}: {detail.tone_analysis.company2_tone || detail.tone_analysis.tone2}
                                    </span>
                                  </>
                                ) : (
                                  <>
                                    <span>Doc1: {detail.tone_analysis.tone1}</span>
                                    {" • "}
                                    <span>Doc2: {detail.tone_analysis.tone2}</span>
                                  </>
                                )}
                              </div>
                              {isCompanyComparison && detail.tone_analysis.style_difference && (
                                <p className="mt-1.5 leading-relaxed text-white/60">{detail.tone_analysis.style_difference}</p>
                              )}
                              {!isCompanyComparison && detail.tone_analysis.difference && (
                                <p className="mt-1.5 leading-relaxed text-white/60">{detail.tone_analysis.difference}</p>
                              )}
                            </div>
                          );
                        })()}
                      </div>
                    ))}
                  </div>
                </div>
              )}
          </div>
        </div>
          ) : (
            <div className="flex min-w-0 flex-1 items-center justify-center rounded-lg border border-white/20 bg-white/5 p-12">
              <p className="text-sm text-white/50">Select a comparison from the history</p>
            </div>
          )}
        </div>
          )}
        </section>
      ) : null}

      {/* 削除確認ダイアログ */}
      {deleteConfirmId && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={(e) => {
            // 背景クリックでダイアログを閉じる（削除中は閉じない）
            if (e.target === e.currentTarget && !isDeleting) {
              setDeleteConfirmId(null);
            }
          }}
        >
          <div 
            className="mx-4 w-full max-w-md rounded-lg border border-white/20 bg-gray-900/95 p-6 shadow-2xl backdrop-blur-md"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-white">Delete Document</h3>
            <p className="mt-3 text-sm leading-relaxed text-white/70">
              このドキュメントとすべての関連データ（PDFファイル、メタデータ、比較結果）が完全に削除されます。
              この操作は取り消せません。
            </p>
            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={() => {
                  console.log("キャンセルボタンクリック");
                  setDeleteConfirmId(null);
                }}
                disabled={isDeleting}
                className="flex-1 rounded-md border border-white/20 bg-white/5 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  console.log("削除ボタンクリック, ID:", deleteConfirmId);
                  handleDelete(deleteConfirmId);
                }}
                disabled={isDeleting}
                className="flex-1 rounded-md bg-white/20 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-white/30 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isDeleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
