import type { DocumentTypeOption } from "./types";

export const DOCUMENT_TYPE_OPTIONS: DocumentTypeOption[] = [
  { value: "securities_report", label: "有価証券報告書" },
  { value: "earnings_report", label: "決算短信" },
  { value: "integrated_report", label: "統合報告書" },
  { value: "financial_statements", label: "計算書類" },
  { value: "unknown", label: "未判定" },
];

export function findDocumentLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  const match = DOCUMENT_TYPE_OPTIONS.find((option) => option.value === value);
  return match?.label ?? value;
}
