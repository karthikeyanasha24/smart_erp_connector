import * as XLSX from 'xlsx';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

export type TableRow = Record<string, unknown> | string[];

export function fmtExportCell(v: unknown): string {
  if (v == null) return '';
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return String(v);
    return v.toLocaleString('en-IN', { maximumFractionDigits: 4 });
  }
  if (v instanceof Date) return v.toISOString().slice(0, 19).replace('T', ' ');
  return String(v);
}

export function normalizeTableData(
  columns: string[],
  rows: TableRow[],
): { columns: string[]; rows: string[][] } {
  if (!rows.length) return { columns, rows: [] };
  if (Array.isArray(rows[0])) {
    return { columns, rows: rows as string[][] };
  }
  const recordRows = rows as Record<string, unknown>[];
  return {
    columns,
    rows: recordRows.map(r => columns.map(c => fmtExportCell(r[c]))),
  };
}

function safeFileBase(name: string): string {
  return name.replace(/[^\w\-]+/g, '_').replace(/_+/g, '_').slice(0, 80) || 'export';
}

export function buildExcelBlob(columns: string[], rows: string[][]): Blob {
  const sheet = XLSX.utils.aoa_to_sheet([columns, ...rows]);
  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, sheet, 'Data');
  const buffer = XLSX.write(book, { bookType: 'xlsx', type: 'array' });
  return new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
}

export function buildPdfBlob(columns: string[], rows: string[][]): Blob {
  const doc = new jsPDF({ orientation: columns.length > 6 ? 'landscape' : 'portrait', unit: 'pt' });
  autoTable(doc, {
    head: [columns],
    body: rows,
    styles: { fontSize: 8, cellPadding: 4 },
    headStyles: { fillColor: [88, 130, 255] },
    margin: { top: 36, left: 24, right: 24 },
    didDrawPage: (data) => {
      doc.setFontSize(9);
      doc.setTextColor(100);
      doc.text('SmarterPConnector export', data.settings.margin.left, 24);
    },
  });
  return doc.output('blob');
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function exportFilename(base: string, ext: string): string {
  const stamp = new Date().toISOString().slice(0, 10);
  return `${safeFileBase(base)}_${stamp}.${ext}`;
}

export function buildCsvBlob(columns: string[], rows: string[][]): Blob {
  const escape = (s: string) => (/[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
  const lines = [
    columns.join(','),
    ...rows.map(r => r.map(c => escape(c)).join(',')),
  ];
  return new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
}
