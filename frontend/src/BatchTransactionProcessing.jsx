import { useEffect, useState } from 'react'
import axios from 'axios'
import { CheckCircle2, FileSearch, Loader2, Sparkles, UploadCloud, X } from 'lucide-react'

const apiBase = import.meta.env.VITE_API_BASE ?? ''

function apiUrl(path) {
  return `${apiBase}${path}`
}

/**
 * Batch CSV upload for closed-loop transaction feedback.
 * Uses multipart/form-data with field name `file` (required by FastAPI UploadFile).
 */
export default function BatchTransactionProcessing() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [devResetting, setDevResetting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  /** In-app notice after dev reset (replaces window.alert). */
  const [toast, setToast] = useState(null)

  useEffect(() => {
    if (!toast) return undefined
    const id = window.setTimeout(() => setToast(null), 5200)
    return () => window.clearTimeout(id)
  }, [toast])

  const isCsvFile = (candidate) =>
    Boolean(candidate && candidate.name && candidate.name.toLowerCase().endsWith('.csv'))

  const onFileSelected = (candidate) => {
    if (!isCsvFile(candidate)) {
      setSelectedFile(null)
      setError('Please select a valid .csv file.')
      return
    }
    setError('')
    setSelectedFile(candidate)
  }

  const uploadBatch = async () => {
    if (!selectedFile || isProcessing) return

    setIsProcessing(true)
    setError('')
    setResult(null)

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      // Let axios set multipart boundary automatically. A bare Content-Type of
      // multipart/form-data (no boundary) breaks parsing and FastAPI returns 422.
      const { data } = await axios.post(apiUrl('/api/batch-process-transactions'), formData)
      setResult(data)
      window.dispatchEvent(new CustomEvent('msme-master-db-updated'))
    } catch (e) {
      const detail = e.response?.data?.detail
      const msg =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d?.msg || JSON.stringify(d)).join('; ')
            : e.message || 'Unable to process batch upload.'
      setError(msg)
    } finally {
      setIsProcessing(false)
    }
  }

  const devResetDatabases = async () => {
    if (devResetting || isProcessing) return
    setDevResetting(true)
    setError('')
    setToast(null)
    try {
      const { data } = await axios.post(apiUrl('/api/dev/reset-databases'))
      setToast({
        title: 'Databases cleared for demo',
        detail:
          typeof data?.message === 'string'
            ? data.message
            : `Reset ${data?.buyer_rows_reset ?? 0} buyer rows and ${data?.vendor_rows_reset ?? 0} vendor rows.`,
      })
      window.dispatchEvent(new CustomEvent('msme-master-db-updated'))
    } catch (e) {
      const detail = e.response?.data?.detail
      const msg =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d?.msg || JSON.stringify(d)).join('; ')
            : e.message || 'Dev reset failed.'
      setError(msg)
    } finally {
      setDevResetting(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-6 right-6 z-[200] flex max-w-sm gap-3 rounded-xl border border-emerald-500/45 bg-slate-950/95 px-4 py-3 shadow-2xl shadow-black/40 ring-1 ring-emerald-500/15 backdrop-blur-md sm:bottom-8 sm:right-8"
        >
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" aria-hidden />
          <div className="min-w-0 flex-1 pt-0.5">
            <p className="text-sm font-semibold text-emerald-50">{toast.title}</p>
            {toast.detail ? (
              <p className="mt-1 text-xs leading-relaxed text-slate-400">{toast.detail}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => setToast(null)}
            className="-m-1 shrink-0 rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-800 hover:text-slate-200"
            aria-label="Dismiss notification"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="relative rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
        <div className="mb-4 flex items-center gap-3">
          <FileSearch className="h-6 w-6 text-amber-400" />
          <div>
            <h2 className="text-2xl font-semibold text-white">Post-Transaction Audits</h2>
            <p className="text-sm text-slate-400">
              Upload a dock-side transaction CSV to run AI signal extraction and trust profile updates.
            </p>
          </div>
        </div>
        <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-400">
          Transaction Summary Batch (.csv — column Summary_Text, summary_text, or transaction_summary;
          optional buyer_email / vendor_id columns)
        </label>
        <label
          onDragOver={(e) => {
            e.preventDefault()
            setDragActive(true)
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragActive(false)
            const droppedFile = e.dataTransfer?.files?.[0]
            if (droppedFile) onFileSelected(droppedFile)
          }}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-12 text-center transition ${
            dragActive
              ? 'border-amber-400 bg-amber-500/10'
              : 'border-slate-700 bg-slate-950/70 hover:border-amber-600/50'
          }`}
        >
          <UploadCloud className="mb-3 h-10 w-10 text-slate-400" />
          <p className="text-sm font-medium text-slate-200">
            {selectedFile ? `Selected: ${selectedFile.name}` : 'Drop CSV here or click to upload'}
          </p>
          <p className="mt-1 text-xs text-slate-500">Only .csv files are accepted</p>
          <input
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => onFileSelected(e.target.files?.[0])}
          />
        </label>

        <button
          type="button"
          onClick={uploadBatch}
          disabled={isProcessing || !selectedFile}
          className="mt-4 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-5 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-amber-900/30 transition hover:from-amber-400 hover:to-orange-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isProcessing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              AI is auditing the batch...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Run AI Audit & Update Profiles
            </>
          )}
        </button>

        <div className="mt-6 flex justify-end border-t border-slate-800/80 pt-4">
          <button
            type="button"
            title="Developer only: resets trust scores in master CSVs for local testing"
            onClick={devResetDatabases}
            disabled={devResetting || isProcessing}
            className="rounded-lg border border-slate-700/80 bg-slate-800/40 px-3 py-1.5 text-xs font-medium text-slate-500 transition hover:border-slate-600 hover:bg-slate-800/70 hover:text-slate-300 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {devResetting ? (
              <span className="inline-flex items-center gap-1.5">
                <Loader2 className="h-3 w-3 animate-spin" />
                Resetting…
              </span>
            ) : (
              'Dev Reset: Clear Ratings'
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">{error}</div>
      )}

      {result && (
        <div className="rounded-2xl border border-emerald-500/40 bg-gradient-to-br from-emerald-900/20 to-slate-900 p-6 shadow-lg shadow-emerald-900/20">
          <div className="mb-4 flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-300" />
            <h3 className="text-lg font-semibold text-white">Action Summary</h3>
          </div>
          <div className="grid gap-3 text-sm sm:grid-cols-2">
            <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-400">Batch Complete</p>
              <p className="mt-1 font-medium text-slate-100">
                {result?.transactions_processed ?? 0} transactions processed
              </p>
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-400">Rows Skipped Safely</p>
              <p className="mt-1 font-medium text-slate-100">{result?.transactions_skipped ?? 0}</p>
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-400">Buyer Profiles Updated</p>
              <p className="mt-1 font-medium text-slate-100">
                {result?.buyer_profiles_updated ?? 0}
              </p>
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-400">Vendor Profiles Updated</p>
              <p className="mt-1 font-medium text-slate-100">
                {result?.vendor_profiles_updated ?? 0}
              </p>
            </div>
          </div>
          <div className="mt-4 rounded-xl border border-emerald-400/30 bg-emerald-500/10 p-4">
            <p className="text-sm font-medium text-emerald-200">
              Batch Complete: {result?.transactions_processed ?? 0} transactions processed,{' '}
              {result?.total_profiles_updated ?? 0} profiles updated.
            </p>
            <p className="mt-1 text-xs text-emerald-100/90">
              Trust & Safety updates were permanently saved to master buyer/vendor databases.
            </p>
          </div>

          {Array.isArray(result?.transaction_row_results) && result.transaction_row_results.length > 0 && (
            <div className="mt-4 overflow-x-auto rounded-xl border border-slate-700 bg-slate-950/60">
              <table className="w-full min-w-[480px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-3 py-2 font-semibold">Row</th>
                    <th className="px-3 py-2 font-semibold">Buyer email</th>
                    <th className="px-3 py-2 font-semibold">Vendor</th>
                    <th className="px-3 py-2 font-semibold">Entity</th>
                  </tr>
                </thead>
                <tbody>
                  {result.transaction_row_results.map((row, i) => (
                    <tr key={`${row.row}-${i}`} className="border-b border-slate-800/80 last:border-0">
                      <td className="px-3 py-2 tabular-nums text-slate-400">{row.row}</td>
                      <td className="px-3 py-2 text-slate-200">
                        <span className="inline-flex flex-wrap items-center gap-2">
                          <span className="break-all">{row.buyer_email}</span>
                          {row.is_government ? (
                            <span className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-sky-500/50 bg-sky-500/15 px-2 py-0.5 text-xs font-semibold text-sky-100 shadow-sm shadow-sky-900/30">
                              <span aria-hidden>🏛️</span>
                              Government
                            </span>
                          ) : null}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-slate-200">
                        <span className="inline-flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs text-slate-300">
                            {row.vendor_id != null && row.vendor_id !== '' ? row.vendor_id : '—'}
                          </span>
                          {row.gov_badge_awarded ? (
                            <span
                              className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-yellow-500/55 bg-yellow-500/15 px-2 py-0.5 text-xs font-semibold text-yellow-100 shadow-sm shadow-amber-900/30"
                              title="This vendor newly earned the Gov Approved badge on this run."
                            >
                              <span aria-hidden>🎖️</span>
                              Gov badge
                            </span>
                          ) : null}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-slate-500">
                        {row.is_government ? 'Government / Public' : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {Array.isArray(result?.skipped_rows_preview) && result.skipped_rows_preview.length > 0 && (
            <div className="mt-4 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-200">
                Skipped rows (from backend)
              </p>
              <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-amber-100/95">
                {result.skipped_rows_preview.map((s, i) => (
                  <li key={i}>
                    Row {s.row}: {s.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
