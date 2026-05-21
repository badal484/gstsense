"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileSpreadsheet, X, CheckCircle, Loader2, AlertCircle } from "lucide-react";
import { useScanUpload } from "@/hooks/useScan";
import { useScanStore } from "@/store/scanStore";
import { MAX_FILE_SIZE_BYTES, ACCEPTED_FILE_TYPES } from "@/lib/constants";

const MAX_SIZE_MB = MAX_FILE_SIZE_BYTES / 1024 / 1024;

interface FileState {
  file: File | null;
  error: string | null;
}

function FileDropZone({
  label,
  description,
  fileState,
  onDrop,
  onRemove,
}: {
  label: string;
  description: string;
  fileState: FileState;
  onDrop: (files: File[]) => void;
  onRemove: () => void;
}) {
  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxFiles: 1,
    maxSize: MAX_FILE_SIZE_BYTES,
    onDropRejected: (rejections) => {
      const reason = rejections[0]?.errors[0]?.code;
      const msg =
        reason === "file-too-large"
          ? `File must be under ${MAX_SIZE_MB}MB`
          : reason === "file-invalid-type"
          ? "Only .xlsx and .xls files are accepted"
          : "Invalid file";
      onDrop([]);
    },
  });

  if (fileState.file) {
    return (
      <div
        className={`rounded-2xl border-2 p-6 ${
          fileState.error ? "border-red-300 bg-red-50" : "border-green-300 bg-green-50"
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {fileState.error ? (
              <AlertCircle className="w-8 h-8 text-red-500 shrink-0" />
            ) : (
              <CheckCircle className="w-8 h-8 text-green-600 shrink-0" />
            )}
            <div>
              <div className="font-semibold text-gray-900 text-sm">{label}</div>
              <div className="text-xs text-gray-500 mt-0.5 truncate max-w-48">
                {fileState.file.name}
              </div>
              {fileState.error && (
                <div className="text-xs text-red-600 mt-0.5">{fileState.error}</div>
              )}
            </div>
          </div>
          <button
            onClick={onRemove}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      {...getRootProps()}
      className={`rounded-2xl border-2 border-dashed p-8 text-center cursor-pointer transition-colors ${
        isDragReject
          ? "border-red-400 bg-red-50"
          : isDragActive
          ? "border-blue-500 bg-blue-50"
          : "border-gray-200 bg-gray-50 hover:border-blue-400 hover:bg-blue-50"
      }`}
    >
      <input {...getInputProps()} />
      <FileSpreadsheet
        className={`w-10 h-10 mx-auto mb-3 ${isDragActive ? "text-blue-600" : "text-gray-300"}`}
      />
      <div className="font-semibold text-gray-700 mb-1">{label}</div>
      <div className="text-sm text-gray-500 mb-3">{description}</div>
      <div className="text-xs text-gray-400">
        {isDragActive
          ? "Drop it here"
          : isDragReject
          ? "Invalid file type"
          : `Drag & drop or click · .xlsx, .xls · max ${MAX_SIZE_MB}MB`}
      </div>
    </div>
  );
}

export default function ScanPage() {
  const { upload } = useScanUpload();
  const { isUploading: isLoading, uploadError: error } = useScanStore();

  const [gstr1, setGstr1] = useState<FileState>({ file: null, error: null });
  const [gstr3b, setGstr3b] = useState<FileState>({ file: null, error: null });

  const handleGstr1Drop = useCallback((files: File[]) => {
    if (files.length === 0) {
      setGstr1({ file: null, error: "Invalid file — only .xlsx/.xls under 10MB accepted" });
    } else {
      setGstr1({ file: files[0], error: null });
    }
  }, []);

  const handleGstr3bDrop = useCallback((files: File[]) => {
    if (files.length === 0) {
      setGstr3b({ file: null, error: "Invalid file — only .xlsx/.xls under 10MB accepted" });
    } else {
      setGstr3b({ file: files[0], error: null });
    }
  }, []);

  const canSubmit = gstr1.file !== null && gstr3b.file !== null && !isLoading;

  async function handleSubmit() {
    if (!gstr1.file || !gstr3b.file) return;
    await upload(gstr1.file, gstr3b.file);
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">New GST Reconciliation Scan</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Upload your GSTR-1 and GSTR-3B Excel files. We&apos;ll reconcile them and surface every
          mismatch in under 60 seconds.
        </p>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
          <div className="text-sm text-red-700">{error}</div>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6 space-y-4">
        <FileDropZone
          label="GSTR-1 File"
          description="Your outward supplies return"
          fileState={gstr1}
          onDrop={handleGstr1Drop}
          onRemove={() => setGstr1({ file: null, error: null })}
        />

        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-gray-100" />
          <Upload className="w-4 h-4 text-gray-300" />
          <div className="flex-1 h-px bg-gray-100" />
        </div>

        <FileDropZone
          label="GSTR-3B File"
          description="Your summary return"
          fileState={gstr3b}
          onDrop={handleGstr3bDrop}
          onRemove={() => setGstr3b({ file: null, error: null })}
        />

        <div className="pt-2">
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="w-full flex items-center justify-center gap-2 bg-blue-700 hover:bg-blue-800 disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed text-white font-bold py-4 rounded-xl text-base transition-colors"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Uploading & Processing...
              </>
            ) : (
              <>
                <Upload className="w-5 h-5" />
                Start Reconciliation
              </>
            )}
          </button>
        </div>
      </div>

      <div className="mt-6 bg-blue-50 rounded-xl border border-blue-100 px-5 py-4">
        <h3 className="text-sm font-semibold text-blue-800 mb-2">What happens next?</h3>
        <ul className="space-y-1.5 text-sm text-blue-700">
          <li className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 shrink-0" />
            We validate your files (format, GSTIN, invoice numbers)
          </li>
          <li className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 shrink-0" />
            Our engine matches every invoice and flags discrepancies
          </li>
          <li className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 shrink-0" />
            AI generates plain-English explanations for each mismatch
          </li>
          <li className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 shrink-0" />
            You get a free preview, then unlock the full PDF report
          </li>
        </ul>
      </div>
    </div>
  );
}
