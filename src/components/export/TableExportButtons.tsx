import { useState } from 'react';
import { Download, FileSpreadsheet, FileText, Upload, Loader2, ExternalLink } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';
import {
  normalizeTableData,
  buildExcelBlob,
  buildPdfBlob,
  buildCsvBlob,
  downloadBlob,
  exportFilename,
  type TableRow,
} from '../../lib/tableExport';
import { isGoogleDriveConfigured, uploadToGoogleDrive } from '../../lib/googleDrive';

export interface ExportNotify {
  message: string;
  type: 'success' | 'error';
  link?: string;
}

interface TableExportButtonsProps {
  columns: string[];
  rows: TableRow[];
  fileBaseName: string;
  /** Show compact icon-only buttons */
  compact?: boolean;
  onNotify?: (n: ExportNotify) => void;
}

type ExportKind = 'csv' | 'excel' | 'pdf' | 'drive-excel' | 'drive-pdf';

const btnBase = 'flex items-center gap-1.5 text-2xs font-semibold px-2.5 py-1.5 rounded-lg transition-opacity disabled:opacity-50';

export default function TableExportButtons({
  columns,
  rows,
  fileBaseName,
  compact = false,
  onNotify,
}: TableExportButtonsProps) {
  const { isDark } = useTheme();
  const { user } = useAuth();
  const [busy, setBusy] = useState<ExportKind | null>(null);

  // Drive button always shown; if not configured, uploadToGoogleDrive shows helpful error.
  const driveReady = true;
  const { columns: cols, rows: dataRows } = normalizeTableData(columns, rows);
  const hasData = cols.length > 0 && dataRows.length > 0;

  const notify = (n: ExportNotify) => onNotify?.(n);

  const styleFor = (accent: string, bgAlpha = 0.1) => ({
    background: isDark ? `rgba(${accent}, ${bgAlpha})` : `rgba(${accent}, ${bgAlpha * 0.8})`,
    color: `rgb(${accent})`,
    border: `1px solid rgba(${accent}, 0.2)`,
  });

  const run = async (kind: ExportKind) => {
    if (!hasData || busy) return;
    setBusy(kind);
    try {
      if (kind === 'csv') {
        downloadBlob(buildCsvBlob(cols, dataRows), exportFilename(fileBaseName, 'csv'));
        notify({ message: 'CSV downloaded', type: 'success' });
        return;
      }

      if (kind === 'excel') {
        downloadBlob(buildExcelBlob(cols, dataRows), exportFilename(fileBaseName, 'xlsx'));
        notify({ message: 'Excel downloaded', type: 'success' });
        return;
      }

      if (kind === 'pdf') {
        downloadBlob(buildPdfBlob(cols, dataRows), exportFilename(fileBaseName, 'pdf'));
        notify({ message: 'PDF downloaded', type: 'success' });
        return;
      }

      if (kind === 'drive-excel') {
        const filename = exportFilename(fileBaseName, 'xlsx');
        const blob = buildExcelBlob(cols, dataRows);
        const result = await uploadToGoogleDrive(
          blob,
          filename,
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        );
        const who = user?.email ? ` (${user.email})` : '';
        notify({
          message: `Excel saved to Google Drive${who}`,
          type: 'success',
          link: result.webViewLink,
        });
        return;
      }

      if (kind === 'drive-pdf') {
        const filename = exportFilename(fileBaseName, 'pdf');
        const blob = buildPdfBlob(cols, dataRows);
        const result = await uploadToGoogleDrive(blob, filename, 'application/pdf');
        const who = user?.email ? ` (${user.email})` : '';
        notify({
          message: `PDF saved to Google Drive${who}`,
          type: 'success',
          link: result.webViewLink,
        });
      }
    } catch (e) {
      notify({
        message: e instanceof Error ? e.message : 'Export failed',
        type: 'error',
      });
    } finally {
      setBusy(null);
    }
  };

  const blue = '88, 130, 255';
  const green = '0, 230, 122';
  const amber = '255, 184, 0';
  const violet = '167, 139, 250';

  const Btn = ({
    kind,
    label,
    icon: Icon,
    accent,
    title,
  }: {
    kind: ExportKind;
    label: string;
    icon: typeof Download;
    accent: string;
    title?: string;
  }) => (
    <button
      type="button"
      disabled={!hasData || !!busy}
      title={title ?? label}
      onClick={() => void run(kind)}
      className={btnBase}
      style={styleFor(accent)}
    >
      {busy === kind ? <Loader2 size={11} className="animate-spin" /> : <Icon size={11} />}
      {!compact && label}
    </button>
  );

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Btn kind="csv" label="CSV" icon={Download} accent={blue} />
      <Btn kind="excel" label="Excel" icon={FileSpreadsheet} accent={green} title="Download Excel" />
      <Btn kind="pdf" label="PDF" icon={FileText} accent={amber} title="Download PDF" />
      {driveReady ? (
        <>
          <span className="w-px h-4 mx-0.5" style={{ background: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)' }} />
          <Btn
            kind="drive-excel"
            label="Drive Excel"
            icon={Upload}
            accent={violet}
            title="Save Excel to your Google Drive — Google sign-in required"
          />
          <Btn
            kind="drive-pdf"
            label="Drive PDF"
            icon={Upload}
            accent={violet}
            title="Save PDF to your Google Drive — Google sign-in required"
          />
        </>
      ) : null}
    </div>
  );
}

export function ExportToast({ notify, onClose }: { notify: ExportNotify | null; onClose: () => void }) {
  if (!notify) return null;
  const ok = notify.type === 'success';
  return (
    <div
      className="fixed bottom-6 right-6 z-[100] flex items-center gap-2 px-4 py-3 rounded-xl text-xs font-medium shadow-lg max-w-sm"
      style={{
        background: ok ? 'rgba(0,230,122,0.12)' : 'rgba(239,68,68,0.12)',
        border: ok ? '1px solid rgba(0,230,122,0.3)' : '1px solid rgba(239,68,68,0.3)',
        color: ok ? '#00e67a' : '#ef4444',
      }}
    >
      <span className="flex-1">{notify.message}</span>
      {notify.link && (
        <a
          href={notify.link}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 underline"
        >
          Open <ExternalLink size={10} />
        </a>
      )}
      <button type="button" onClick={onClose} className="opacity-70 hover:opacity-100 ml-1">
        ×
      </button>
    </div>
  );
}
