/* eslint-disable jsx-a11y/label-has-associated-control */
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { listDocuments, getDocument, uploadDocuments, updateDocumentType, compareDocuments, getComparisonStatus, getComparisonResult } from "@/lib/api";
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
      <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10">
        <button
          type="button"
          onClick={() => toggleSection("summary")}
          className="flex w-full items-center justify-between px-4 py-3 text-left"
        >
          <h4 className="text-sm font-semibold text-emerald-200">構造化データ サマリー</h4>
          <span className="text-emerald-200">{expandedSections.summary ? "▼" : "▶"}</span>
        </button>
        {expandedSections.summary && (
          <div className="border-t border-emerald-500/40 px-4 py-3">
            <div className="grid gap-2 text-xs text-emerald-100 md:grid-cols-3">
              <div>
                <span className="font-medium">抽出方法:</span>{" "}
                {document.extraction_method === "text"
                  ? "テキスト抽出"
                  : document.extraction_method === "vision"
                    ? "画像解析"
                    : document.extraction_method === "hybrid"
                      ? "ハイブリッド"
                      : document.extraction_method ?? "不明"}
              </div>
              <div>
                <span className="font-medium">ページ数:</span> {pages.length} ページ
              </div>
              <div>
                <span className="font-medium">テーブル数:</span> {tables.length} 個
              </div>
              <div className="md:col-span-3">
                <span className="font-medium">全文字数:</span>{" "}
                {sd.full_text?.length?.toLocaleString() ?? 0} 文字
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ページ詳細 */}
      {pages.length > 0 && (
        <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10">
          <button
            type="button"
            onClick={() => toggleSection("pages")}
            className="flex w-full items-center justify-between px-4 py-3 text-left"
          >
            <h4 className="text-sm font-semibold text-emerald-200">
              ページ詳細 ({pages.length} ページ)
            </h4>
            <span className="text-emerald-200">{expandedSections.pages ? "▼" : "▶"}</span>
          </button>
          {expandedSections.pages && (
            <div className="max-h-96 overflow-y-auto border-t border-emerald-500/40 px-4 py-3">
              <div className="space-y-3">
                {pages.slice(0, 10).map((page, idx) => (
                  <details key={idx} className="rounded border border-emerald-500/30 bg-emerald-500/5">
                    <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-emerald-100 hover:bg-emerald-500/10">
                      ページ {page.page_number} - {page.char_count?.toLocaleString() ?? 0} 文字
                      {page.has_images && " 📷"}
                    </summary>
                    <div className="border-t border-emerald-500/30 px-3 py-2">
                      <pre className="max-h-40 overflow-auto whitespace-pre-wrap text-[10px] leading-relaxed text-emerald-50">
                        {page.text?.substring(0, 500) ?? ""}
                        {(page.text?.length ?? 0) > 500 && "..."}
                      </pre>
                    </div>
                  </details>
                ))}
                {pages.length > 10 && (
                  <p className="text-xs text-emerald-200/70">
                    ... 他 {pages.length - 10} ページ（最初の10ページのみ表示）
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* セクション検出結果 */}
      {sd.sections && Object.keys(sd.sections).length > 0 && (
        <div className="rounded-lg border border-blue-500/40 bg-blue-500/10">
          <button
            type="button"
            onClick={() => toggleSection("sections" as any)}
            className="flex w-full items-center justify-between px-4 py-3 text-left"
          >
            <h4 className="text-sm font-semibold text-blue-200">
              検出されたセクション ({Object.keys(sd.sections).length} 個)
            </h4>
            <span className="text-blue-200">{(expandedSections as any).sections ? "▼" : "▶"}</span>
          </button>
          {(expandedSections as any).sections && (
            <div className="max-h-96 overflow-y-auto border-t border-blue-500/40 px-4 py-3">
              <div className="space-y-2">
                {Object.entries(sd.sections).map(([sectionName, sectionInfo]: [string, any]) => (
                  <div key={sectionName} className="rounded border border-blue-500/30 bg-blue-500/5 px-3 py-2">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-xs font-medium text-blue-100">{sectionName}</p>
                        <p className="text-[10px] text-blue-100/60">
                          ページ {sectionInfo.start_page}-{sectionInfo.end_page}
                          {" "}
                          ({sectionInfo.char_count?.toLocaleString() ?? 0} 文字)
                          {" "}
                          信頼度: {((sectionInfo.confidence ?? 0) * 100).toFixed(0)}%
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* テーブル詳細 */}
      {tables.length > 0 && (
        <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10">
          <button
            type="button"
            onClick={() => toggleSection("tables")}
            className="flex w-full items-center justify-between px-4 py-3 text-left"
          >
            <h4 className="text-sm font-semibold text-emerald-200">
              テーブル詳細 ({tables.length} 個)
            </h4>
            <span className="text-emerald-200">{expandedSections.tables ? "▼" : "▶"}</span>
          </button>
          {expandedSections.tables && (
            <div className="max-h-96 overflow-y-auto border-t border-emerald-500/40 px-4 py-3">
              <div className="space-y-3">
                {tables.slice(0, 5).map((table, idx) => (
                  <details key={idx} className="rounded border border-emerald-500/30 bg-emerald-500/5">
                    <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-emerald-100 hover:bg-emerald-500/10">
                      テーブル {idx + 1} (ページ {table.page_number}) - {table.row_count} 行 ×{" "}
                      {table.column_count} 列
                    </summary>
                    <div className="border-t border-emerald-500/30 px-3 py-2">
                      <div className="overflow-x-auto">
                        <table className="w-full text-[10px] text-emerald-50">
                          <thead>
                            <tr className="border-b border-emerald-500/30">
                              {table.header?.map((h, i) => (
                                <th key={i} className="px-2 py-1 text-left font-medium">
                                  {h || `列${i + 1}`}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {table.rows?.slice(0, 5).map((row, i) => (
                              <tr key={i} className="border-b border-emerald-500/20">
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
                          <p className="mt-2 text-[10px] text-emerald-200/70">
                            ... 他 {(table.rows?.length ?? 0) - 5} 行
                          </p>
                        )}
                      </div>
                    </div>
                  </details>
                ))}
                {tables.length > 5 && (
                  <p className="text-xs text-emerald-200/70">
                    ... 他 {tables.length - 5} テーブル（最初の5個のみ表示）
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 抽出メタデータ */}
      {document.extraction_metadata && (
        <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10">
          <button
            type="button"
            onClick={() => toggleSection("metadata")}
            className="flex w-full items-center justify-between px-4 py-3 text-left"
          >
            <h4 className="text-sm font-semibold text-emerald-200">抽出メタデータ</h4>
            <span className="text-emerald-200">{expandedSections.metadata ? "▼" : "▶"}</span>
          </button>
          {expandedSections.metadata && (
            <div className="border-t border-emerald-500/40 px-4 py-3">
              <pre className="max-h-60 overflow-auto text-[10px] text-emerald-50">
                {JSON.stringify(document.extraction_metadata, null, 2)}
              </pre>
            </div>
          )}
        </div>
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
  const [isComparing, setIsComparing] = useState(false);
  const [comparisonResult, setComparisonResult] = useState<any>(null);
  const [comparisonError, setComparisonError] = useState<string | null>(null);
  const [comparisonProgress, setComparisonProgress] = useState<number>(0);
  const [comparisonStatus, setComparisonStatus] = useState<string>("");
  const [currentSection, setCurrentSection] = useState<string>("");
  const [sectionProgress, setSectionProgress] = useState<{completed: number, total: number} | null>(null);

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

  // ページロード時にドキュメント一覧を読み込む
  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);
  
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
      const task = await compareDocuments(Array.from(selectedDocIds));
      const comparisonId = task.comparison_id;
      
      // Step 2: ポーリングでステータスを確認
      const pollInterval = 1000; // 1秒ごと
      const maxAttempts = 300; // 最大5分
      let attempts = 0;
      
      const poll = async (): Promise<void> => {
        if (attempts >= maxAttempts) {
          throw new Error("タイムアウト: 比較処理に時間がかかりすぎています。");
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
          setIsComparing(false);
          setComparisonStatus("完了");
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
  }, [selectedDocIds]);

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

    const pendingDocuments = results.filter(
      (doc) =>
        doc.document_id &&
        doc.processing_status &&
        ["queued", "processing", "extracting_text", "extracting_vision", "extracting_tables", "detecting_sections"].includes(doc.processing_status),
    );

    if (pendingDocuments.length === 0) return;

    const interval = setInterval(async () => {
      const updates = await Promise.allSettled(
        pendingDocuments.map(async (doc) => {
          if (!doc.document_id) return null;
          try {
            const response = await getDocument(doc.document_id);
            return response.document;
          } catch {
            return null;
          }
        }),
      );

      let hasUpdates = false;
      setResults((prev) =>
        prev.map((item) => {
          const index = pendingDocuments.findIndex((p) => p.document_id === item.document_id);
          if (index === -1) return item;

          const result = updates[index];
          if (result.status === "fulfilled" && result.value) {
            hasUpdates = true;
            return result.value;
          }
          return item;
        }),
      );

      if (hasUpdates) {
        // すべてのドキュメントが完了またはエラーになったかチェック
        const stillPending = results.some(
          (doc) =>
            doc.document_id &&
            doc.processing_status &&
            ["queued", "processing", "extracting_text", "extracting_vision", "extracting_tables", "detecting_sections"].includes(doc.processing_status),
        );
        if (!stillPending) {
          clearInterval(interval);
        }
      }
    }, 5000); // 5秒ごとにポーリング

    return () => clearInterval(interval);
  }, [results]);

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col gap-10 px-6 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight text-white">開示文書アップロード</h1>
        <p className="text-base text-white/70">
          最大 {limits.max_files} 件の PDF をアップロードし、書類種別の自動判定と初期検証を開始します。
        </p>
        <div className="text-sm text-white/50">
          サイズ上限: {limits.max_file_size_mb}MB / FastAPI エンドポイント:
          <code className="mx-2 rounded bg-white/10 px-1.5 py-0.5 text-xs text-white">
            POST /api/documents/
          </code>
          <Link
            className="inline-flex items-center justify-center rounded-md border border-white/10 bg-white/10 px-3 py-1 text-xs font-medium text-white transition hover:bg-white/20"
            href="/api/docs"
          >
            API ドキュメントを見る
          </Link>
        </div>
      </header>

      <section>
        <div
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className={`relative flex min-h-[220px] flex-col items-center justify-center rounded-2xl border-2 border-dashed px-8 transition ${
            isDragging ? "border-emerald-400/60 bg-emerald-400/10" : "border-white/10 bg-white/5"
          }`}
        >
          <div className="pointer-events-none absolute inset-0 rounded-2xl bg-white/5 blur-xl" />
          <div className="relative z-10 flex flex-col items-center gap-4 text-center text-white">
            <p className="text-xl font-medium">ドラッグ＆ドロップ、またはファイルを選択</p>
            <p className="max-w-lg text-sm text-white/70">
              PDF 形式のみサポートしています。圧縮ファイルや他形式はアップロード前に変換してください。
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3 text-xs text-white/50">
              <span>最大 {limits.max_files} ファイル</span>
              <span>1 ファイル {limits.max_file_size_mb}MB まで</span>
              <span>
                現在選択: {selectedFiles.length} ファイル / {bytesToMegabytes(totalSelectedSize)}
              </span>
            </div>
            <label className="relative inline-flex cursor-pointer items-center justify-center gap-2 rounded-md border border-white/10 bg-white/10 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/20">
              ファイルを選択
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
          <p className="mt-3 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
            {errorMessage}
          </p>
        ) : null}
      </section>

      {selectedFiles.length > 0 ? (
        <section className="rounded-xl border border-white/10 bg-white/5 p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">選択中のファイル</h2>
            <button
              type="button"
              onClick={resetAll}
              className="text-xs text-white/60 underline hover:text-white"
            >
              リセット
            </button>
          </div>
          <ul className="space-y-3 text-sm text-white/80">
            {selectedFiles.map((file) => (
              <li
                key={getFileKey(file)}
                className="flex items-center justify-between gap-4 rounded-lg border border-white/10 bg-white/10 px-4 py-3"
              >
                <div className="flex flex-col">
                  <span className="font-medium text-white">{file.name}</span>
                  <span className="text-xs text-white/60">
                    {bytesToReadable(file.size)} / 更新日: {" "}
                    {new Date(file.lastModified).toLocaleDateString()}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemoveFile(file)}
                  className="text-xs text-white/70 underline hover:text-white"
                >
                  削除
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <button
              type="button"
              onClick={handleUpload}
              disabled={isUploading}
              className="inline-flex items-center justify-center rounded-md bg-emerald-500 px-5 py-2 text-sm font-semibold text-emerald-900 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-emerald-500/40"
            >
              {isUploading ? "アップロード中..." : "アップロードを開始"}
            </button>
            <p className="text-xs text-white/50">
              PDF はアップロード後にサーバー側で Celery タスクへ引き渡されます。
            </p>
          </div>
        </section>
      ) : null}

      {results.length > 0 ? (
        <section className="space-y-4">
          <header className="flex flex-col gap-3">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div>
                  <h2 className="text-xl font-semibold text-white">処理結果</h2>
                  <p className="text-sm text-white/60">
                  バッチ ID: {batchId ?? "N/A"} / タスク ID: {taskId ?? "未キューイング"}
                </p>
                <p className="text-xs text-white/50">
                  書類種別は暫定判定です。セレクトボックスで手動補正するとサーバー側に即時保存されます。
                </p>
              </div>
                <button
                  type="button"
                  onClick={loadDocuments}
                  className="ml-3 rounded-md border border-white/20 bg-white/5 px-3 py-1 text-xs font-medium text-white/80 hover:bg-white/10"
                  title="ドキュメント一覧を更新"
                >
                  🔄 更新
                </button>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm text-white/70">
                  {selectedDocIds.size} 件選択中
                </span>
                <button
                  type="button"
                  onClick={handleCompare}
                  disabled={selectedDocIds.size < 2 || isComparing}
                  className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isComparing ? "比較中..." : "比較実行"}
                </button>
              </div>
            </div>
            
            {comparisonError && (
              <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3">
                <p className="text-sm text-red-200">{comparisonError}</p>
              </div>
            )}
            
            {/* 比較進捗表示 */}
            {isComparing && (
              <div className="rounded-lg border border-blue-500/40 bg-blue-500/10 p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-blue-200">比較処理中...</h3>
                  <span className="text-sm font-bold text-blue-200">{comparisonProgress}%</span>
                </div>
                
                {/* プログレスバー */}
                <div className="w-full bg-blue-900/30 rounded-full h-2 mb-3">
                  <div 
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${comparisonProgress}%` }}
                  />
                </div>
                
                {/* ステータス情報 */}
                <div className="space-y-2 text-xs text-blue-100">
                  <p>
                    <span className="font-medium">ステータス:</span> {comparisonStatus}
                  </p>
                  
                  {currentSection && (
                    <p>
                      <span className="font-medium">現在のセクション:</span> {currentSection}
                    </p>
                  )}
                  
                  {sectionProgress && (
                    <p>
                      <span className="font-medium">セクション進捗:</span>{" "}
                      {sectionProgress.completed} / {sectionProgress.total} セクション完了
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
                  className={`rounded-xl border p-5 ${
                    isSelected
                      ? "border-emerald-500 bg-emerald-500/10"
                      : "border-white/10 bg-white/5"
                  }`}
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-start gap-3">
                      {canSelect && (
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleDocSelection(document.document_id!)}
                          className="mt-1 h-5 w-5 rounded border-white/20 bg-white/10 text-emerald-500 focus:ring-2 focus:ring-emerald-500"
                        />
                      )}
                      <div>
                        <h3 className="text-base font-semibold text-white">{document.filename}</h3>
                        <p className="text-xs text-white/60">
                          サイズ: {bytesToReadable(document.size_bytes)} / ドキュメント ID: {" "}
                          {document.document_id ?? "未割当"}
                        </p>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={statusClass}
                      >
                        {document.status === "accepted" ? "受理" : "拒否"}
                      </span>
                      <span className="inline-flex h-7 items-center rounded-full border border-white/10 px-3 text-xs font-medium text-white/70">
                        {processingLabel}
                      </span>
                    </div>
                  </div>
 
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    <label className="flex flex-col gap-1 text-xs text-white/70">
                      書類種別の選択
                      <select
                        value={selectValue}
                        onChange={(event) => handleOverrideChange(document, event.target.value)}
                        disabled={!document.document_id || isUpdating}
                        className="rounded-md border border-white/10 bg-white/10 px-3 py-2 text-sm text-white focus:border-emerald-400 focus:outline-none disabled:cursor-not-allowed"
                      >
                        <option value={AUTO_OPTION_VALUE}>自動判定を使用</option>
                        {DOCUMENT_TYPE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      {isUpdating ? (
                        <span className="text-[11px] text-white/50">更新しています…</span>
                      ) : null}
                    </label>
                    <div className="flex flex-col gap-1 text-xs text-white/70">
                      現在の表示ラベル
                      <span className="rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-white">
                        {selectedLabel ?? "未判定"}
                      </span>
                    </div>
                    <div className="flex flex-col gap-1 text-xs text-white/70">
                      信頼度
                      <span className="rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-white">
                        {document.detection_confidence != null
                          ? `${Math.round(document.detection_confidence * 100)}%`
                          : "-"}
                      </span>
                    </div>
                    <div className="flex flex-col gap-1 text-xs text-white/70">
                      判定根拠
                      <span className="rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-white">
                        {document.detection_reason
                          ? document.detection_reason
                          : "判定根拠なし"}
                      </span>
                    </div>
                  </div>

                  {document.errors.length > 0 ? (
                    <div className="mt-4 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3">
                      <h4 className="text-sm font-semibold text-red-200">エラー詳細</h4>
                      <ul className="mt-2 space-y-1 text-xs text-red-100">
                        {document.errors.map((error) => (
                          <li key={error}>・{error}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {document.processing_status === "pending_classification" && 
                   (!document.selected_type || document.selected_type === "unknown") ? (
                    <div className="mt-4 rounded-lg border border-yellow-500/40 bg-yellow-500/10 px-4 py-3">
                      <h4 className="text-sm font-semibold text-yellow-200">⚠️ 書類種別を選択してください</h4>
                      <p className="mt-2 text-xs text-yellow-100">
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
        </section>
      ) : null}
      
      {comparisonResult && (
        <section className="mt-8 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white">比較結果</h2>
            <button
              type="button"
              onClick={() => setComparisonResult(null)}
              className="text-sm text-white/70 hover:text-white"
            >
              閉じる
            </button>
          </div>
          
          <div className="rounded-xl border border-white/10 bg-white/5 p-5">
            <div className="space-y-4">
              {/* 基本情報 */}
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-4">
                  <h3 className="text-sm font-semibold text-emerald-200">ドキュメント1</h3>
                  <p className="mt-2 text-xs text-emerald-100">
                    ファイル名: {comparisonResult.doc1_info?.filename || "不明"}
                  </p>
                  <p className="text-xs text-emerald-100">
                    会社名: {comparisonResult.doc1_info?.company_name || "未抽出"}
                  </p>
                  <p className="text-xs text-emerald-100">
                    年度: {comparisonResult.doc1_info?.fiscal_year || "未抽出"}
                  </p>
                </div>
                <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-4">
                  <h3 className="text-sm font-semibold text-emerald-200">ドキュメント2</h3>
                  <p className="mt-2 text-xs text-emerald-100">
                    ファイル名: {comparisonResult.doc2_info?.filename || "不明"}
                  </p>
                  <p className="text-xs text-emerald-100">
                    会社名: {comparisonResult.doc2_info?.company_name || "未抽出"}
                  </p>
                  <p className="text-xs text-emerald-100">
                    年度: {comparisonResult.doc2_info?.fiscal_year || "未抽出"}
                  </p>
                </div>
              </div>
              
              {/* 比較モード */}
              <div className="rounded-lg border border-blue-500/40 bg-blue-500/10 p-4">
                <h3 className="text-sm font-semibold text-blue-200">比較モード</h3>
                <p className="mt-2 text-xs text-blue-100">
                  {comparisonResult.mode === "consistency_check" && "整合性チェックモード（同じ会社の異なる書類）"}
                  {comparisonResult.mode === "diff_analysis_company" && "差分分析モード（異なる会社の同じ書類）"}
                  {comparisonResult.mode === "diff_analysis_year" && "差分分析モード（同じ会社の異なる年度）"}
                  {comparisonResult.mode === "multi_document" && "多資料比較モード"}
                </p>
              </div>
              
              {/* セクションマッピング */}
              {comparisonResult.section_mappings && comparisonResult.section_mappings.length > 0 && (
                <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                  <h3 className="text-sm font-semibold text-white">セクションマッピング ({comparisonResult.section_mappings.length} 件)</h3>
                  <div className="mt-3 space-y-2">
                    {comparisonResult.section_mappings.slice(0, 5).map((mapping: any, idx: number) => (
                      <div key={idx} className="text-xs text-white/70">
                        <span className="font-medium">{mapping.doc1_section}</span>
                        {" ↔ "}
                        <span className="font-medium">{mapping.doc2_section}</span>
                        {" "}
                        <span className="text-white/50">
                          (信頼度: {(mapping.confidence_score * 100).toFixed(0)}%, 方法: {mapping.mapping_method})
                        </span>
                      </div>
                    ))}
                    {comparisonResult.section_mappings.length > 5 && (
                      <p className="text-xs text-white/50">... 他 {comparisonResult.section_mappings.length - 5} 件</p>
                    )}
                  </div>
                </div>
              )}
              
              {/* 数値差分 */}
              {comparisonResult.numerical_differences && comparisonResult.numerical_differences.length > 0 && (
                <div className="rounded-lg border border-yellow-500/40 bg-yellow-500/10 p-4">
                  <h3 className="text-sm font-semibold text-yellow-200">数値差分 ({comparisonResult.numerical_differences.length} 件)</h3>
                  <div className="mt-3 space-y-2">
                    {comparisonResult.numerical_differences.slice(0, 5).map((diff: any, idx: number) => (
                      <div key={idx} className="text-xs text-yellow-100">
                        <span className="font-medium">{diff.section} - {diff.item_name}:</span>
                        {" "}
                        {diff.value1} → {diff.value2}
                        {" "}
                        <span className="text-yellow-50">
                          (差: {diff.difference.toFixed(2)}, {diff.difference_pct?.toFixed(2)}%)
                        </span>
                      </div>
                    ))}
                    {comparisonResult.numerical_differences.length > 5 && (
                      <p className="text-xs text-yellow-50/50">... 他 {comparisonResult.numerical_differences.length - 5} 件</p>
                    )}
                  </div>
                </div>
              )}
              
              {/* テキスト差分 */}
              {comparisonResult.text_differences && comparisonResult.text_differences.length > 0 && (
                <div className="rounded-lg border border-purple-500/40 bg-purple-500/10 p-4">
                  <h3 className="text-sm font-semibold text-purple-200">テキスト差分 ({comparisonResult.text_differences.length} 件)</h3>
                  <div className="mt-3 space-y-2">
                    {comparisonResult.text_differences.map((diff: any, idx: number) => (
                      <div key={idx} className="text-xs text-purple-100">
                        <span className="font-medium">{diff.section}:</span>
                        {" "}
                        一致率 {(diff.match_ratio * 100).toFixed(1)}%
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* セクション別詳細差分 */}
              {comparisonResult.section_detailed_comparisons && comparisonResult.section_detailed_comparisons.length > 0 && (
                <div className="rounded-lg border border-cyan-500/40 bg-cyan-500/10 p-4">
                  <h3 className="text-sm font-semibold text-cyan-200">
                    セクション別詳細差分 ({comparisonResult.section_detailed_comparisons.length} 件)
                  </h3>
                  <div className="mt-3 space-y-4">
                    {comparisonResult.section_detailed_comparisons.map((detail: any, idx: number) => (
                      <div key={idx} className="rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-3">
                        {/* セクションヘッダー */}
                        <div className="mb-2 flex items-start justify-between">
                          <h4 className="font-semibold text-cyan-200">{detail.section_name}</h4>
                          <span
                            className={`rounded px-2 py-1 text-xs font-semibold ${
                              detail.importance === "high"
                                ? "bg-red-500/20 text-red-200"
                                : detail.importance === "medium"
                                  ? "bg-yellow-500/20 text-yellow-200"
                                  : "bg-gray-500/20 text-gray-200"
                            }`}
                          >
                            {detail.importance === "high" ? "重要度: 高" : detail.importance === "medium" ? "重要度: 中" : "重要度: 低"}
                          </span>
                        </div>
                        
                        <p className="mb-2 text-xs text-cyan-100/70">
                          Doc1: ページ {detail.doc1_page_range} | Doc2: ページ {detail.doc2_page_range}
                        </p>
                        
                        {/* サマリー */}
                        <div className="mb-3 rounded bg-cyan-500/10 p-2">
                          <p className="text-xs font-medium text-cyan-100">{detail.summary}</p>
                          {detail.importance_reason && (
                            <p className="mt-1 text-xs text-cyan-100/60">理由: {detail.importance_reason}</p>
                          )}
                        </div>
                        
                        {/* テキスト変更 */}
                        {detail.text_changes && Object.keys(detail.text_changes).length > 0 && (
                          <div className="mb-2 space-y-1">
                            {detail.text_changes.added && detail.text_changes.added.length > 0 && (
                              <details className="text-xs">
                                <summary className="cursor-pointer font-medium text-green-200">
                                  追加 ({detail.text_changes.added.length} 件)
                                </summary>
                                <ul className="ml-4 mt-1 space-y-1">
                                  {detail.text_changes.added.map((item: string, i: number) => (
                                    <li key={i} className="text-green-100/80">+ {item}</li>
                                  ))}
                                </ul>
                              </details>
                            )}
                            {detail.text_changes.removed && detail.text_changes.removed.length > 0 && (
                              <details className="text-xs">
                                <summary className="cursor-pointer font-medium text-red-200">
                                  削除 ({detail.text_changes.removed.length} 件)
                                </summary>
                                <ul className="ml-4 mt-1 space-y-1">
                                  {detail.text_changes.removed.map((item: string, i: number) => (
                                    <li key={i} className="text-red-100/80">- {item}</li>
                                  ))}
                                </ul>
                              </details>
                            )}
                            {detail.text_changes.modified && detail.text_changes.modified.length > 0 && (
                              <details className="text-xs">
                                <summary className="cursor-pointer font-medium text-yellow-200">
                                  変更 ({detail.text_changes.modified.length} 件)
                                </summary>
                                <div className="ml-4 mt-1 space-y-2">
                                  {detail.text_changes.modified.map((item: any, i: number) => (
                                    <div key={i} className="text-yellow-100/80">
                                      <div className="text-red-100/60">- {item.before}</div>
                                      <div className="text-green-100/60">+ {item.after}</div>
                                    </div>
                                  ))}
                                </div>
                              </details>
                            )}
                          </div>
                        )}
                        
                        {/* 数値変更 */}
                        {detail.numerical_changes && detail.numerical_changes.length > 0 && (
                          <details className="text-xs">
                            <summary className="cursor-pointer font-medium text-cyan-200">
                              数値変更 ({detail.numerical_changes.length} 件)
                            </summary>
                            <div className="ml-4 mt-1 space-y-1">
                              {detail.numerical_changes.map((change: any, i: number) => (
                                <div key={i} className="text-cyan-100/80">
                                  {change.item}: {change.value1} → {change.value2}
                                  {change.change_pct && ` (${change.change_pct > 0 ? "+" : ""}${change.change_pct.toFixed(1)}%)`}
                                </div>
                              ))}
                            </div>
                          </details>
                        )}
                        
                        {/* トーン分析 */}
                        {detail.tone_analysis && Object.keys(detail.tone_analysis).length > 0 && (
                          <div className="mt-2 text-xs text-cyan-100/70">
                            <span className="font-medium">トーン:</span>
                            {" "}
                            Doc1: {detail.tone_analysis.tone1}
                            {" vs "}
                            Doc2: {detail.tone_analysis.tone2}
                            {detail.tone_analysis.difference && (
                              <span className="ml-2 text-cyan-100/50">({detail.tone_analysis.difference})</span>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
