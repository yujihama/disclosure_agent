import type { DocumentMutationResponse, DocumentUploadResponse, DocumentListResponse } from "./types";
import { API_BASE_URL } from "./config";

export async function listDocuments(): Promise<DocumentListResponse> {
  const response = await fetch(`${API_BASE_URL}/documents/`, {
    method: "GET",
  });

  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))) as { detail?: string | string[] };
    const message = detail?.detail ?? "ドキュメント一覧の取得に失敗しました。";
    throw new Error(Array.isArray(message) ? message.join("\n") : String(message));
  }

  return (await response.json()) as DocumentListResponse;
}

export async function uploadDocuments(files: File[]): Promise<DocumentUploadResponse> {
  if (files.length === 0) {
    throw new Error("ファイルが選択されていません。");
  }

  const formData = new FormData();
  files.forEach((file) => {
    formData.append("files", file, file.name);
  });

  const response = await fetch(`${API_BASE_URL}/documents/`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))) as { detail?: string | string[] };
    const message = detail?.detail ?? "ファイルのアップロードに失敗しました。";
    throw new Error(Array.isArray(message) ? message.join("\n") : String(message));
  }

  return (await response.json()) as DocumentUploadResponse;
}

export async function getDocument(documentId: string): Promise<DocumentMutationResponse> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
    method: "GET",
  });

  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))) as { detail?: string | string[] };
    const message = detail?.detail ?? "ドキュメントの取得に失敗しました。";
    throw new Error(Array.isArray(message) ? message.join("\n") : String(message));
  }

  return (await response.json()) as DocumentMutationResponse;
}

export async function updateDocumentType(
  documentId: string,
  documentType: string | null,
): Promise<DocumentMutationResponse> {
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ document_type: documentType }),
  });

  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))) as { detail?: string | string[] };
    const message = detail?.detail ?? "書類種別の更新に失敗しました。";
    throw new Error(Array.isArray(message) ? message.join("\n") : String(message));
  }

  return (await response.json()) as DocumentMutationResponse;
}

export async function deleteDocument(documentId: string): Promise<void> {
  console.log("deleteDocument 関数呼び出し:", documentId);
  console.log("DELETE URL:", `${API_BASE_URL}/documents/${documentId}`);
  
  const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
    method: "DELETE",
  });

  console.log("DELETE レスポンス status:", response.status);
  console.log("DELETE レスポンス ok:", response.ok);

  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))) as { detail?: string | string[] };
    const message = detail?.detail ?? "ドキュメントの削除に失敗しました。";
    console.error("削除API エラー:", message);
    throw new Error(Array.isArray(message) ? message.join("\n") : String(message));
  }
  
  console.log("削除API 成功");
}

export async function listComparisons(): Promise<Array<{
  comparison_id: string;
  created_at: string;
  mode: string;
  doc1_filename: string;
  doc2_filename: string;
  section_count: number;
}>> {
  const response = await fetch(`${API_BASE_URL}/comparisons`, {
    method: "GET",
  });

  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))) as { detail?: string | string[] };
    const message = detail?.detail ?? "比較履歴の取得に失敗しました。";
    throw new Error(Array.isArray(message) ? message.join("\n") : String(message));
  }

  return await response.json();
}

export async function compareDocuments(
  documentIds: string[],
  iterativeSearchMode: "off" | "high_only" | "all" = "off"
): Promise<{comparison_id: string, status: string, message: string}> {
  console.log("=== compareDocuments 呼び出し ===");
  console.log("documentIds:", documentIds);
  console.log("iterativeSearchMode:", iterativeSearchMode);
  const payload = { 
    document_ids: documentIds,
    iterative_search_mode: iterativeSearchMode
  };
  console.log("送信ペイロード:", JSON.stringify(payload));
  
  const response = await fetch(`${API_BASE_URL}/comparisons`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))) as { detail?: string | string[] };
    const message = detail?.detail ?? "比較処理に失敗しました。";
    throw new Error(Array.isArray(message) ? message.join("\n") : String(message));
  }

  return await response.json();
}

export async function getComparisonStatus(comparisonId: string): Promise<{
  comparison_id: string;
  status: string;
  progress?: number;
  step?: string;
  current_section?: string;
  total_sections?: number;
  completed_sections?: number;
  error?: string;
}> {
  const response = await fetch(`${API_BASE_URL}/comparisons/${comparisonId}/status`, {
    method: "GET",
  });

  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))) as { detail?: string | string[] };
    const message = detail?.detail ?? "ステータスの取得に失敗しました。";
    throw new Error(Array.isArray(message) ? message.join("\n") : String(message));
  }

  return await response.json();
}

export async function getComparisonResult(comparisonId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/comparisons/${comparisonId}`, {
    method: "GET",
  });

  if (!response.ok) {
    const detail = (await response.json().catch(() => ({}))) as { detail?: string | string[] };
    const message = detail?.detail ?? "比較結果の取得に失敗しました。";
    throw new Error(Array.isArray(message) ? message.join("\n") : String(message));
  }

  return await response.json();
}
