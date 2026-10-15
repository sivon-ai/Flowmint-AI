import React, { useState, useRef } from 'react';
import {
  Upload,
  FileSpreadsheet,
  FileText,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  X,
  Trash2,
  RefreshCw,
  ArrowRight,
  Database,
  FileUp,
} from 'lucide-react';
import { api, ApiError } from '../../lib/api';
import type {
  ProductImportParseResponse,
  ProductImportRow,
  ProductImportResult,
} from '../../types';

interface ProductImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete: () => void;
}

type ModalStep = 'upload' | 'extracting' | 'preview' | 'importing' | 'complete' | 'error';

export default function ProductImportModal({
  isOpen,
  onClose,
  onImportComplete,
}: ProductImportModalProps) {
  const [step, setStep] = useState<ModalStep>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [parseResponse, setParseResponse] = useState<ProductImportParseResponse | null>(null);
  const [editableRows, setEditableRows] = useState<ProductImportRow[]>([]);
  const [selectedSheet, setSelectedSheet] = useState<string>('');
  const [duplicatePolicy, setDuplicatePolicy] = useState<'skip' | 'update'>('skip');
  const [importResult, setImportResult] = useState<ProductImportResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  };

  const handleFileSelected = (selectedFile: File) => {
    // 10MB limit check client-side for immediate feedback
    if (selectedFile.size > 10 * 1024 * 1024) {
      setErrorMessage('File size exceeds the 10MB limit. Please upload a smaller catalog file.');
      setStep('error');
      return;
    }

    const lower = selectedFile.name.toLowerCase();
    const validExts = ['.xlsx', '.csv', '.docx', '.pdf'];
    const hasValidExt = validExts.some(ext => lower.endsWith(ext));
    if (!hasValidExt) {
      setErrorMessage(
        'Unsupported file format. Please upload an Excel (.xlsx), CSV (.csv), Word (.docx), or PDF (.pdf) file.'
      );
      setStep('error');
      return;
    }

    setFile(selectedFile);
    setErrorMessage('');
    uploadAndParseFile(selectedFile);
  };

  const uploadAndParseFile = async (targetFile: File, sheet?: string) => {
    setStep('extracting');
    setErrorMessage('');

    try {
      const formData = new FormData();
      formData.append('file', targetFile);
      if (sheet) {
        formData.append('sheet_name', sheet);
      }

      const res = await api.upload<ProductImportParseResponse>('/products/import/parse', formData);
      if (res.data) {
        setParseResponse(res.data);
        setEditableRows(res.data.rows);
        setSelectedSheet(res.data.selected_sheet || (res.data.sheets[0] || ''));
        setStep('preview');
      } else {
        throw new Error('No catalog extraction data returned from server');
      }
    } catch (err) {
      let msg = 'Failed to extract product catalog.';
      if (err instanceof ApiError) {
        msg = err.message;
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setErrorMessage(msg);
      setStep('error');
    }
  };

  const handleSheetSwitch = (sheet: string) => {
    if (!file || sheet === selectedSheet) return;
    setSelectedSheet(sheet);
    uploadAndParseFile(file, sheet);
  };

  const handleRemoveRow = (indexToRemove: number) => {
    setEditableRows(prev => prev.filter((_, idx) => idx !== indexToRemove));
  };

  const handleRowChange = (
    index: number,
    field: keyof ProductImportRow,
    value: any
  ) => {
    setEditableRows(prev => {
      const updated = [...prev];
      const row = { ...updated[index], [field]: value };

      // Re-evaluate client-side validation for this row
      const errors: string[] = [];
      if (!row.name || !row.name.trim()) errors.push('Product name is required.');
      if (!row.sku || !row.sku.trim()) errors.push('SKU is required.');
      const numPrice = Number(row.price);
      if (row.price === null || row.price === undefined || isNaN(numPrice) || numPrice <= 0) {
        errors.push('Price must be greater than 0.');
      }
      if (row.stock !== undefined && row.stock !== null && (isNaN(Number(row.stock)) || Number(row.stock) < 0)) {
        errors.push('Stock cannot be negative.');
      }

      row.validation_errors = errors;
      if (errors.length > 0) {
        row.validation_status = 'invalid';
      } else if (row.is_existing) {
        row.validation_status = 'duplicate';
      } else {
        row.validation_status = 'valid';
      }

      updated[index] = row;
      return updated;
    });
  };

  const handleExecuteImport = async () => {
    if (!editableRows || editableRows.length === 0) return;

    // Filter to rows that have at least name, sku, price > 0
    const validRowsToSubmit = editableRows.filter(r => {
      return (
        r.name &&
        r.name.trim() &&
        r.sku &&
        r.sku.trim() &&
        r.price !== null &&
        Number(r.price) > 0
      );
    });

    if (validRowsToSubmit.length === 0) {
      setErrorMessage('No valid rows available to import. Please review and correct required fields.');
      return;
    }

    setStep('importing');
    setErrorMessage('');

    try {
      const payload = {
        duplicate_resolution: duplicatePolicy,
        rows: validRowsToSubmit.map(r => ({
          name: r.name.trim(),
          sku: r.sku.trim(),
          price: Number(r.price),
          compare_at_price: r.compare_at_price ? Number(r.compare_at_price) : null,
          stock: r.stock !== undefined && r.stock !== null ? Math.max(0, parseInt(String(r.stock), 10) || 0) : 0,
          description: r.description || null,
          category_name: r.category_name || null,
          status: r.status || 'active',
        })),
      };

      const res = await api.post<ProductImportResult>('/products/import/confirm', payload);
      if (res.data) {
        setImportResult(res.data);
        setStep('complete');
        onImportComplete();
      }
    } catch (err) {
      let msg = 'Failed to persist imported catalog to database.';
      if (err instanceof ApiError) {
        msg = err.message;
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setErrorMessage(msg);
      setStep('error');
    }
  };

  const resetAll = () => {
    setFile(null);
    setParseResponse(null);
    setEditableRows([]);
    setErrorMessage('');
    setImportResult(null);
    setStep('upload');
  };

  // Preview computations
  const totalCount = editableRows.length;
  const validCount = editableRows.filter(r => r.validation_status === 'valid').length;
  const duplicateCount = editableRows.filter(r => r.validation_status === 'duplicate').length;
  const invalidCount = editableRows.filter(r => r.validation_status === 'invalid' || r.validation_status === 'file_duplicate').length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-surface-900 border border-surface-700/80 rounded-2xl shadow-2xl w-full max-w-5xl my-8 overflow-hidden animate-slide-up flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-800 bg-surface-950/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-500/10 border border-brand-500/30 flex items-center justify-center text-brand-400">
              <FileUp className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                Import Product Catalog
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-brand-500/20 text-brand-300 border border-brand-500/30 uppercase">
                  Bulk Ingestion
                </span>
              </h2>
              <p className="text-xs text-surface-400">
                Upload existing catalog files, review extracted data, resolve duplicates, and commit verified products.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-surface-400 hover:text-white rounded-lg hover:bg-surface-800 transition"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {/* STEP 1: Upload Dropzone */}
          {step === 'upload' && (
            <div className="space-y-6">
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-2xl p-10 text-center transition flex flex-col items-center justify-center gap-4 ${
                  dragOver
                    ? 'border-brand-500 bg-brand-500/10'
                    : 'border-surface-700 hover:border-surface-600 bg-surface-950/40'
                }`}
              >
                <div className="w-16 h-16 rounded-2xl bg-surface-800 flex items-center justify-center text-brand-400 shadow-inner">
                  <Upload className="w-8 h-8" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-base font-semibold text-white">
                    Drag and drop your catalog file here
                  </h3>
                  <p className="text-xs text-surface-400">
                    Supports spreadsheets and structured product documents
                  </p>
                </div>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xlsx,.csv,.docx,.pdf"
                  onChange={handleFileChange}
                  className="hidden"
                />

                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="px-5 py-2.5 bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs rounded-xl transition shadow-lg flex items-center gap-2"
                >
                  <FileSpreadsheet className="w-4 h-4" /> Browse Files
                </button>

                <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
                  <span className="px-2.5 py-1 text-[11px] font-mono rounded-lg bg-surface-800 text-surface-300 border border-surface-700">
                    .XLSX (Multi-sheet)
                  </span>
                  <span className="px-2.5 py-1 text-[11px] font-mono rounded-lg bg-surface-800 text-surface-300 border border-surface-700">
                    .CSV
                  </span>
                  <span className="px-2.5 py-1 text-[11px] font-mono rounded-lg bg-surface-800 text-surface-300 border border-surface-700">
                    .DOCX (Tables)
                  </span>
                  <span className="px-2.5 py-1 text-[11px] font-mono rounded-lg bg-surface-800 text-surface-300 border border-surface-700">
                    .PDF (Searchable text)
                  </span>
                  <span className="text-xs text-surface-500">Max size: 10MB</span>
                </div>
              </div>

              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl space-y-2 text-xs text-surface-400">
                <div className="font-semibold text-surface-200">Catalog Processing Guarantees:</div>
                <ul className="list-disc list-inside space-y-1 text-surface-300">
                  <li>Tenant Scoped: Products are strictly imported under your merchant ownership.</li>
                  <li>Autonomous Header Normalization: Recognizes variations like <em>Item Name</em>, <em>Selling Price</em>, <em>Qty</em>, <em>Part Number</em>.</li>
                  <li>Safety Gate: Extracted records are previewed and editable prior to any database write.</li>
                </ul>
              </div>
            </div>
          )}

          {/* STEP 2: Extracting Spinner */}
          {step === 'extracting' && (
            <div className="p-16 text-center space-y-4">
              <RefreshCw className="w-12 h-12 text-brand-400 animate-spin mx-auto" />
              <div className="space-y-1">
                <h3 className="text-base font-bold text-white">Extracting Catalog Information</h3>
                <p className="text-xs text-surface-400">
                  Parsing {file?.name} ({((file?.size || 0) / 1024).toFixed(1)} KB), detecting column headers, and verifying merchant SKUs...
                </p>
              </div>
            </div>
          )}

          {/* STEP 3: Preview Table & Resolution */}
          {step === 'preview' && parseResponse && (
            <div className="space-y-6">
              {/* File details bar */}
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="flex items-center gap-3">
                  <FileText className="w-8 h-8 text-brand-400 shrink-0" />
                  <div>
                    <div className="text-sm font-bold text-white flex items-center gap-2">
                      {parseResponse.file_name}
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-surface-800 text-surface-300 border border-surface-700">
                        {parseResponse.format}
                      </span>
                    </div>
                    <div className="text-xs text-surface-400 mt-0.5">
                      File Size: {(parseResponse.file_size / 1024).toFixed(1)} KB • Detected Columns: {parseResponse.headers.length}
                    </div>
                  </div>
                </div>

                {/* Multi-sheet selector for XLSX */}
                {parseResponse.sheets && parseResponse.sheets.length > 1 && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-surface-400">Worksheet:</span>
                    <select
                      value={selectedSheet}
                      onChange={e => handleSheetSwitch(e.target.value)}
                      className="bg-surface-800 border border-surface-700 text-white text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-brand-500"
                    >
                      {parseResponse.sheets.map(sh => (
                        <option key={sh} value={sh}>
                          {sh}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <button
                  type="button"
                  onClick={resetAll}
                  className="text-xs text-surface-400 hover:text-danger-400 transition"
                >
                  Change File
                </button>
              </div>

              {/* Summary stat cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 bg-surface-950 border border-surface-800 rounded-xl">
                  <div className="text-xs text-surface-400">Total Extracted</div>
                  <div className="text-xl font-bold text-white mt-0.5">{totalCount}</div>
                </div>
                <div className="p-3 bg-surface-950 border border-surface-800 rounded-xl">
                  <div className="text-xs text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Ready to Import
                  </div>
                  <div className="text-xl font-bold text-emerald-400 mt-0.5">{validCount}</div>
                </div>
                <div className="p-3 bg-surface-950 border border-surface-800 rounded-xl">
                  <div className="text-xs text-amber-400 flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5" /> Existing SKUs
                  </div>
                  <div className="text-xl font-bold text-amber-400 mt-0.5">{duplicateCount}</div>
                </div>
                <div className="p-3 bg-surface-950 border border-surface-800 rounded-xl">
                  <div className="text-xs text-red-400 flex items-center gap-1">
                    <XCircle className="w-3.5 h-3.5" /> Incomplete / Invalid
                  </div>
                  <div className="text-xl font-bold text-red-400 mt-0.5">{invalidCount}</div>
                </div>
              </div>

              {/* Duplicate Handling Policy */}
              {duplicateCount > 0 && (
                <div className="p-4 bg-amber-950/20 border border-amber-500/30 rounded-xl space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold text-amber-300">
                    <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
                    <span>Duplicate Resolution Policy for {duplicateCount} Existing SKU(s):</span>
                  </div>
                  <div className="flex flex-wrap gap-4 text-xs">
                    <label className="flex items-center gap-2 cursor-pointer text-surface-200">
                      <input
                        type="radio"
                        name="dupPolicy"
                        value="skip"
                        checked={duplicatePolicy === 'skip'}
                        onChange={() => setDuplicatePolicy('skip')}
                        className="accent-brand-500"
                      />
                      <span><strong>Skip existing products</strong> (Keep current database records unchanged)</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer text-surface-200">
                      <input
                        type="radio"
                        name="dupPolicy"
                        value="update"
                        checked={duplicatePolicy === 'update'}
                        onChange={() => setDuplicatePolicy('update')}
                        className="accent-brand-500"
                      />
                      <span><strong>Update existing products</strong> (Safely refresh price, stock, and description)</span>
                    </label>
                  </div>
                </div>
              )}

              {/* Warnings Banner */}
              {parseResponse.warnings && parseResponse.warnings.length > 0 && (
                <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs text-amber-300 space-y-1">
                  {parseResponse.warnings.map((w, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Extracted Rows Preview Table */}
              <div className="border border-surface-800 rounded-xl overflow-hidden bg-surface-950">
                <div className="px-4 py-3 bg-surface-900 border-b border-surface-800 flex items-center justify-between">
                  <div className="text-xs font-semibold text-white">
                    Preview Data (Inline Editable)
                  </div>
                  <div className="text-[11px] text-surface-400">
                    Double-check values or remove rows before confirming
                  </div>
                </div>

                <div className="overflow-x-auto max-h-72">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-surface-900/80 sticky top-0 border-b border-surface-800 text-surface-400 font-mono">
                      <tr>
                        <th className="px-3 py-2 text-center w-12">#</th>
                        <th className="px-3 py-2 w-28">Status</th>
                        <th className="px-3 py-2 min-w-[180px]">Product Name *</th>
                        <th className="px-3 py-2 min-w-[120px]">SKU *</th>
                        <th className="px-3 py-2 min-w-[110px]">Price (₹) *</th>
                        <th className="px-3 py-2 min-w-[90px]">Stock</th>
                        <th className="px-3 py-2 min-w-[130px]">Category</th>
                        <th className="px-3 py-2 w-12 text-center">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-800/60">
                      {editableRows.map((row, idx) => {
                        const isInvalid = row.validation_status === 'invalid' || row.validation_status === 'file_duplicate';
                        const isDup = row.validation_status === 'duplicate';

                        return (
                          <tr
                            key={idx}
                            className={`hover:bg-surface-900/40 transition ${
                              isInvalid ? 'bg-red-950/10' : isDup ? 'bg-amber-950/10' : ''
                            }`}
                          >
                            <td className="px-3 py-2 text-center text-surface-500 font-mono">
                              {row.row_index}
                            </td>
                            <td className="px-3 py-2">
                              {row.validation_status === 'valid' && (
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                  Valid
                                </span>
                              )}
                              {row.validation_status === 'duplicate' && (
                                <span
                                  className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30"
                                  title="Existing SKU in your store catalog"
                                >
                                  Existing
                                </span>
                              )}
                              {row.validation_status === 'file_duplicate' && (
                                <span
                                  className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30"
                                  title="Duplicate SKU within this file"
                                >
                                  File Dup
                                </span>
                              )}
                              {row.validation_status === 'invalid' && (
                                <span
                                  className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-300 border border-red-500/30"
                                  title={row.validation_errors.join('; ')}
                                >
                                  Invalid
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-2">
                              <input
                                type="text"
                                value={row.name}
                                onChange={e => handleRowChange(idx, 'name', e.target.value)}
                                className="w-full bg-surface-900 border border-surface-700 rounded px-2 py-1 text-white text-xs focus:border-brand-500 focus:outline-none"
                              />
                            </td>
                            <td className="px-3 py-2">
                              <input
                                type="text"
                                value={row.sku}
                                onChange={e => handleRowChange(idx, 'sku', e.target.value)}
                                className="w-full bg-surface-900 border border-surface-700 rounded px-2 py-1 font-mono text-white text-xs focus:border-brand-500 focus:outline-none"
                              />
                            </td>
                            <td className="px-3 py-2">
                              <input
                                type="number"
                                step="0.01"
                                value={row.price ?? ''}
                                onChange={e => handleRowChange(idx, 'price', e.target.value ? parseFloat(e.target.value) : null)}
                                className="w-full bg-surface-900 border border-surface-700 rounded px-2 py-1 text-white text-xs focus:border-brand-500 focus:outline-none text-right"
                              />
                            </td>
                            <td className="px-3 py-2">
                              <input
                                type="number"
                                value={row.stock}
                                onChange={e => handleRowChange(idx, 'stock', parseInt(e.target.value, 10) || 0)}
                                className="w-full bg-surface-900 border border-surface-700 rounded px-2 py-1 text-white text-xs focus:border-brand-500 focus:outline-none text-center"
                              />
                            </td>
                            <td className="px-3 py-2">
                              <input
                                type="text"
                                value={row.category_name || ''}
                                placeholder="None"
                                onChange={e => handleRowChange(idx, 'category_name', e.target.value)}
                                className="w-full bg-surface-900 border border-surface-700 rounded px-2 py-1 text-white text-xs focus:border-brand-500 focus:outline-none"
                              />
                            </td>
                            <td className="px-3 py-2 text-center">
                              <button
                                type="button"
                                onClick={() => handleRemoveRow(idx)}
                                className="text-surface-500 hover:text-red-400 p-1 transition"
                                title="Remove row"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* STEP 4: Importing Spinner */}
          {step === 'importing' && (
            <div className="p-16 text-center space-y-4">
              <RefreshCw className="w-12 h-12 text-brand-400 animate-spin mx-auto" />
              <div className="space-y-1">
                <h3 className="text-base font-bold text-white">Persisting Products to Database</h3>
                <p className="text-xs text-surface-400">
                  Executing atomic database transactions, creating inventory items, and publishing outbox events...
                </p>
              </div>
            </div>
          )}

          {/* STEP 5: Complete */}
          {step === 'complete' && importResult && (
            <div className="p-8 text-center space-y-6">
              <div className="w-16 h-16 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <div className="space-y-1">
                <h3 className="text-xl font-bold text-white">Catalog Import Successful</h3>
                <p className="text-xs text-surface-300">
                  Your products have been verified and persisted to your merchant database.
                </p>
              </div>

              <div className="grid grid-cols-3 gap-3 max-w-lg mx-auto">
                <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                  <div className="text-xs text-surface-400">Newly Created</div>
                  <div className="text-2xl font-bold text-emerald-400 mt-1">
                    {importResult.imported_count}
                  </div>
                </div>
                <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                  <div className="text-xs text-surface-400">Updated</div>
                  <div className="text-2xl font-bold text-brand-400 mt-1">
                    {importResult.updated_count}
                  </div>
                </div>
                <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                  <div className="text-xs text-surface-400">Skipped</div>
                  <div className="text-2xl font-bold text-surface-400 mt-1">
                    {importResult.skipped_count}
                  </div>
                </div>
              </div>

              {importResult.errors && importResult.errors.length > 0 && (
                <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs text-amber-300 max-w-lg mx-auto text-left space-y-1">
                  <div className="font-bold">Notices:</div>
                  {importResult.errors.map((e, idx) => (
                    <div key={idx}>• {e}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* STEP 6: Error State */}
          {step === 'error' && (
            <div className="p-10 text-center space-y-4">
              <div className="w-14 h-14 rounded-full bg-red-500/20 border border-red-500/40 text-red-400 flex items-center justify-center mx-auto">
                <XCircle className="w-8 h-8" />
              </div>
              <div className="space-y-1">
                <h3 className="text-lg font-bold text-white">Catalog Processing Failed</h3>
                <p className="text-xs text-red-300 max-w-md mx-auto">
                  {errorMessage || 'An error occurred during file extraction or catalog validation.'}
                </p>
              </div>

              <div className="pt-2">
                <button
                  type="button"
                  onClick={resetAll}
                  className="px-5 py-2.5 bg-surface-800 hover:bg-surface-700 text-white font-semibold text-xs rounded-xl border border-surface-700 transition"
                >
                  Try Another File
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer Controls */}
        <div className="px-6 py-4 border-t border-surface-800 bg-surface-950/50 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-surface-300 hover:text-white rounded-lg transition"
          >
            {step === 'complete' ? 'Done' : 'Cancel'}
          </button>

          {step === 'preview' && (
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={resetAll}
                className="px-4 py-2 text-xs font-semibold bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-lg transition border border-surface-700"
              >
                Reset
              </button>
              <button
                type="button"
                onClick={handleExecuteImport}
                disabled={editableRows.length === 0}
                className="px-5 py-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-40 text-white font-bold text-xs rounded-xl transition shadow-lg flex items-center gap-2"
              >
                <Database className="w-4 h-4" /> Confirm & Import {editableRows.length} Product(s)
              </button>
            </div>
          )}

          {step === 'complete' && (
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-xl transition shadow-lg flex items-center gap-2"
            >
              View Updated Products <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
