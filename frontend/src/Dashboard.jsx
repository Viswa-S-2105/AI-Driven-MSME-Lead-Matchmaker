import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Activity,
  BadgeCheck,
  BookUser,
  Bot,
  ClipboardCheck,
  FileSpreadsheet,
  LayoutDashboard,
  Loader2,
  Mail,
  MessageSquare,
  Play,
  Upload,
  Users,
} from 'lucide-react'
import VendorDirectory from './VendorDirectory.jsx'
import BuyerDirectory from './BuyerDirectory.jsx'
import PostTransactionAudits from './PostTransactionAudits.jsx'
import ConfirmModal from './ConfirmModal.jsx'

const apiBase = import.meta.env.VITE_API_BASE ?? ''

function apiUrl(path) {
  return `${apiBase}${path}`
}

/** Avoid hanging forever if the API is down or the wrong port is configured */
const FETCH_TIMEOUT_MS = 45_000

function fetchWithTimeout(url, options = {}) {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS)
  return fetch(url, { ...options, signal: ctrl.signal }).finally(() =>
    clearTimeout(t)
  )
}

function formatHttpError(status, detail) {
  if (typeof detail === 'string') return detail || status
  if (Array.isArray(detail)) {
    return detail.map((x) => (typeof x === 'object' && x?.msg ? x.msg : String(x))).join('; ')
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return status
}

export default function Dashboard() {
  const [tab, setTab] = useState('vendors')
  /** Bumped after batch audit / dev reset so directory pages refetch master CSV data. */
  const [profileRefreshEpoch, setProfileRefreshEpoch] = useState(0)
  const [vendorRows, setVendorRows] = useState([])
  const [vendorCols, setVendorCols] = useState([])
  const [vendorUploading, setVendorUploading] = useState(false)
  const [resettingLeads, setResettingLeads] = useState(false)
  const [inquiryUploading, setInquiryUploading] = useState(false)
  const [matchRunning, setMatchRunning] = useState(false)
  const [logLines, setLogLines] = useState([])
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [modalTitle, setModalTitle] = useState('')
  const [modalMessage, setModalMessage] = useState('')
  const [modalConfirmText, setModalConfirmText] = useState('Confirm')
  const [modalShowCancel, setModalShowCancel] = useState(true)
  const [modalAction, setModalAction] = useState(null)
  const logEndRef = useRef(null)
  const eventSourceRef = useRef(null)

  const closeModal = () => {
    setIsModalOpen(false)
    setModalAction(null)
  }

  const openInfoModal = (title, message) => {
    setModalTitle(title)
    setModalMessage(message)
    setModalConfirmText('OK')
    setModalShowCancel(false)
    setModalAction(null)
    setIsModalOpen(true)
  }

  const openConfirmModal = ({ title, message, confirmText = 'Confirm', action }) => {
    setModalTitle(title)
    setModalMessage(message)
    setModalConfirmText(confirmText)
    setModalShowCancel(true)
    setModalAction(() => action)
    setIsModalOpen(true)
  }

  const handleModalConfirm = async () => {
    const action = modalAction
    closeModal()
    if (typeof action === 'function') {
      await action()
    }
  }

  const scrollLog = useCallback(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollLog()
  }, [logLines, scrollLog])

  useEffect(() => {
    const bump = () => setProfileRefreshEpoch((n) => n + 1)
    window.addEventListener('msme-master-db-updated', bump)
    return () => window.removeEventListener('msme-master-db-updated', bump)
  }, [])

  const loadVendorPreview = async () => {
    try {
      const r = await fetchWithTimeout(apiUrl('/api/vendors/preview'))
      if (!r.ok) return
      const data = await r.json()
      setVendorCols(data.columns || [])
      setVendorRows(data.rows || [])
    } catch {
      /* optional */
    }
  }

  const onVendorFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setVendorUploading(true)
    const fd = new FormData()
    fd.append('file', file)
    try {
      const r = await fetchWithTimeout(apiUrl('/api/upload/vendors'), {
        method: 'POST',
        body: fd,
      })
      const j = await r.json().catch(() => ({}))
      if (!r.ok) {
        throw new Error(formatHttpError(r.statusText, j.detail) || 'Upload failed')
      }
      if (j.preview_rows && j.columns) {
        setVendorCols(j.columns)
        setVendorRows(j.preview_rows)
      } else {
        await loadVendorPreview()
      }
    } catch (err) {
      const name = err?.name
      const msg =
        name === 'AbortError'
          ? `Request timed out after ${FETCH_TIMEOUT_MS / 1000}s. Start the API on port 8001: uvicorn main:app --host 127.0.0.1 --port 8001`
          : err.message || 'Upload failed (is the backend running on port 8001?)'
      openInfoModal('Vendor Upload Failed', msg)
    } finally {
      setVendorUploading(false)
      e.target.value = ''
    }
  }

  const onInquiryFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setInquiryUploading(true)
    const fd = new FormData()
    fd.append('file', file)
    try {
      const r = await fetchWithTimeout(apiUrl('/api/upload/inquiries'), {
        method: 'POST',
        body: fd,
      })
      const j = await r.json().catch(() => ({}))
      if (!r.ok) {
        throw new Error(formatHttpError(r.statusText, j.detail) || 'Upload failed')
      }
      openInfoModal('Upload Complete', `Uploaded ${j.rows ?? '?'} inquiries.`)
    } catch (err) {
      const msg =
        err?.name === 'AbortError'
          ? `Timed out. Start FastAPI on port 8001 (see vendor upload error text).`
          : err.message || 'Upload failed'
      openInfoModal('Inquiries Upload Failed', msg)
    } finally {
      setInquiryUploading(false)
      e.target.value = ''
    }
  }

  const performResetLeads = async () => {
    setResettingLeads(true)
    try {
      const r = await fetchWithTimeout(apiUrl('/api/admin/reset-leads'), {
        method: 'POST',
      })
      const j = await r.json().catch(() => ({}))
      if (!r.ok) {
        throw new Error(formatHttpError(r.statusText, j.detail) || 'Reset failed')
      }
      await loadVendorPreview()
      openInfoModal('Reset Complete', `Updated ${j.rows_updated ?? 0} vendors.`)
    } catch (err) {
      const msg =
        err?.name === 'AbortError'
          ? `Reset timed out after ${FETCH_TIMEOUT_MS / 1000}s.`
          : err.message || 'Reset failed'
      openInfoModal('Reset Failed', msg)
    } finally {
      setResettingLeads(false)
    }
  }

  const onResetLeads = () => {
    openConfirmModal({
      title: 'Reset Leads Counter',
      message:
        'Reset Leads_Received to 0 for all vendors in master_vendors_db.csv? This is intended for demo/testing runs.',
      confirmText: 'Reset Now',
      action: performResetLeads,
    })
  }

  const runMatchmaker = () => {
    if (matchRunning) return
    eventSourceRef.current?.close()
    setLogLines([])
    setMatchRunning(true)

    const es = new EventSource(apiUrl('/api/run-matchmaker'))
    eventSourceRef.current = es

    es.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data)
        const line = payload.line ?? JSON.stringify(payload)
        const type = payload.type || 'log'
        setLogLines((prev) => [...prev, { type, text: line }])
        if (type === 'error' || type === 'done') {
          es.close()
          setMatchRunning(false)
        }
      } catch {
        setLogLines((prev) => [...prev, { type: 'log', text: ev.data }])
      }
    }

    es.onerror = () => {
      setLogLines((prev) => [
        ...prev,
        { type: 'error', text: '[frontend] SSE connection error or closed.' },
      ])
      es.close()
      setMatchRunning(false)
    }
  }

  const logColor = (type) => {
    if (type === 'error') return 'text-red-400'
    if (type === 'match') return 'text-emerald-400'
    if (type === 'email') return 'text-sky-400'
    if (type === 'sms') return 'text-amber-300'
    if (type === 'done') return 'text-violet-300 font-semibold'
    return 'text-slate-300'
  }

  const nav = [
    { id: 'vendors', label: 'Vendor Registry', icon: Users },
    { id: 'directory', label: 'Vendor Directory', icon: BookUser },
    { id: 'buyers', label: 'Buyer Directory', icon: BadgeCheck },
    { id: 'audits', label: 'Post-Transaction Audits', icon: ClipboardCheck },
    { id: 'matchmaker', label: 'AI Batch Matchmaker', icon: Bot },
  ]

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <aside className="flex w-64 flex-col border-r border-slate-800 bg-slate-900/80">
        <div className="flex items-center gap-2 border-b border-slate-800 px-5 py-4">
          <LayoutDashboard className="h-8 w-8 text-amber-500" />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              MSME Admin
            </p>
            <p className="font-semibold text-white">Export Matchmaker</p>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-3">
          {nav.map((item) => {
            const Icon = item.icon
            const active = tab === item.id
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id)}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition ${
                  active
                    ? 'bg-amber-500/15 text-amber-400 ring-1 ring-amber-500/40'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <Icon className="h-5 w-5 shrink-0" />
                {item.label}
              </button>
            )
          })}
        </nav>
        <div className="border-t border-slate-800 p-4 text-xs text-slate-500">
          <Activity className="mb-1 inline h-4 w-4" /> Internal use — uploads stored in{' '}
          <code className="text-slate-400">uploads/</code>
        </div>
      </aside>

      <main className="flex flex-1 flex-col overflow-hidden">
        <header className="border-b border-slate-800 bg-slate-900/50 px-8 py-5">
          <h1 className="text-xl font-semibold text-white">
            {tab === 'vendors'
              ? 'Vendor Registry'
              : tab === 'directory'
                ? 'Vendor Directory'
                : tab === 'buyers'
                  ? 'Buyer Directory'
                  : tab === 'audits'
                    ? 'Post-Transaction Audits'
                : 'AI Batch Matchmaker'}
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            {tab === 'vendors'
              ? 'Upload and preview MSME vendor CSV data.'
              : tab === 'directory'
                ? 'Search and browse all persisted vendors from the master database.'
                : tab === 'buyers'
                  ? 'Browse foreign buyer trust and payment behavior indicators.'
                  : tab === 'audits'
                    ? 'Paste dock-side reports and trigger AI-based trust profile updates.'
              : 'Upload export inquiries, train the classifier, and stream match + notification logs.'}
          </p>
        </header>

        <div className="flex-1 overflow-auto p-8">
          {tab === 'vendors' && (
            <div className="mx-auto max-w-5xl space-y-6">
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg">
                <div className="mb-4 flex items-center gap-2 text-slate-300">
                  <Upload className="h-5 w-5 text-amber-500" />
                  <span className="font-medium">Upload vendor CSV</span>
                  <span className="text-xs text-slate-500">
                    (Vendor_ID, Vendor_Name, Category, Contact_Email, Contact_Phone)
                  </span>
                </div>
                <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-700 bg-slate-950/50 px-6 py-10 transition hover:border-amber-600/50 hover:bg-slate-900">
                  <FileSpreadsheet className="mb-2 h-10 w-10 text-slate-600" />
                  <span className="text-sm text-slate-400">
                    {vendorUploading ? 'Uploading…' : 'Drop file or click to select'}
                  </span>
                  <input
                    type="file"
                    accept=".csv"
                    className="hidden"
                    disabled={vendorUploading}
                    onChange={onVendorFile}
                  />
                  {vendorUploading && (
                    <Loader2 className="mt-3 h-6 w-6 animate-spin text-amber-500" />
                  )}
                </label>
                <div className="mt-4 flex items-center justify-end">
                  <button
                    type="button"
                    onClick={onResetLeads}
                    disabled={resettingLeads || vendorUploading}
                    className="rounded-md border border-red-500/60 bg-red-500/10 px-3 py-1.5 text-xs font-semibold text-red-300 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {resettingLeads ? 'Resetting…' : 'Reset Leads to 0'}
                  </button>
                </div>
              </div>

              <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 shadow-lg">
                <div className="border-b border-slate-800 px-4 py-3 text-sm font-medium text-slate-300">
                  {vendorCols.length > 0
                    ? `Preview (${vendorRows.length} rows)`
                    : 'Table preview'}
                </div>
                <div className="max-h-[480px] overflow-auto">
                  {vendorCols.length === 0 ? (
                    <div className="flex flex-col items-center justify-center px-6 py-16 text-center text-slate-500">
                      <FileSpreadsheet className="mb-3 h-14 w-14 text-slate-600 opacity-50" aria-hidden />
                      <p className="text-base text-slate-400">No preview yet</p>
                      <p className="mt-2 max-w-md text-sm">
                        Upload your <span className="text-slate-300">msme_vendor_registry.csv</span> above.
                        The table appears only after a successful upload — nothing is loaded from disk on page load.
                      </p>
                    </div>
                  ) : (
                    <table className="w-full min-w-[640px] text-left text-sm">
                      <thead className="sticky top-0 bg-slate-900">
                        <tr className="border-b border-slate-800 text-xs uppercase text-slate-500">
                          {vendorCols.map((c) => (
                            <th key={c} className="px-4 py-3 font-medium">
                              {c}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800 text-slate-300">
                        {vendorRows.map((row, i) => (
                          <tr key={i} className="hover:bg-slate-800/40">
                            {vendorCols.map((k) => (
                              <td key={k} className="max-w-[220px] truncate px-4 py-2.5">
                                {String(row[k] ?? '')}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>
          )}

          {tab === 'matchmaker' && (
            <div className="mx-auto flex max-w-6xl flex-col gap-6 lg:flex-row">
              <div className="flex-1 space-y-6">
                <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 shadow-lg">
                  <div className="mb-4 flex items-center gap-2 text-slate-300">
                    <Upload className="h-5 w-5 text-amber-500" />
                    <span className="font-medium">Upload inquiries CSV</span>
                    <span className="text-xs text-slate-500">
                      (Buyer_Country, Inquiry_Text; Category optional — training falls back to project CSV)
                    </span>
                  </div>
                  <label className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-700 bg-slate-950/50 px-6 py-8 transition hover:border-amber-600/50">
                    <FileSpreadsheet className="mb-2 h-9 w-9 text-slate-600" />
                    <span className="text-sm text-slate-400">
                      {inquiryUploading ? 'Uploading…' : 'Select b2b_export_inquiries.csv'}
                    </span>
                    <input
                      type="file"
                      accept=".csv"
                      className="hidden"
                      disabled={inquiryUploading}
                      onChange={onInquiryFile}
                    />
                    {inquiryUploading && (
                      <Loader2 className="mt-3 h-6 w-6 animate-spin text-amber-500" />
                    )}
                  </label>
                </div>

                <button
                  type="button"
                  onClick={runMatchmaker}
                  disabled={matchRunning}
                  className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-6 py-4 text-lg font-semibold text-slate-950 shadow-lg shadow-amber-900/30 transition hover:from-amber-400 hover:to-orange-500 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {matchRunning ? (
                    <>
                      <Loader2 className="h-6 w-6 animate-spin" />
                      Running pipeline…
                    </>
                  ) : (
                    <>
                      <Play className="h-6 w-6 fill-current" />
                      Run AI Batch Matchmaker
                    </>
                  )}
                </button>
                <p className="text-center text-xs text-slate-500">
                  Trains TF-IDF (1–2 grams) + Logistic Regression on the inquiries file, then matches
                  vendors and simulates SMTP / Twilio when keys are placeholders.
                </p>
              </div>

              <div className="flex flex-1 flex-col rounded-xl border border-slate-800 bg-[#0d1117] shadow-inner">
                <div className="flex items-center gap-2 border-b border-slate-800 px-4 py-2.5 font-mono text-xs text-slate-400">
                  <span className="h-3 w-3 rounded-full bg-red-500/80" />
                  <span className="h-3 w-3 rounded-full bg-amber-500/80" />
                  <span className="h-3 w-3 rounded-full bg-emerald-500/80" />
                  <span className="ml-2">matchmaker.log — SSE stream</span>
                  <Mail className="ml-auto h-3.5 w-3.5 text-sky-500" />
                  <MessageSquare className="h-3.5 w-3.5 text-amber-500" />
                </div>
                <div className="min-h-[420px] flex-1 overflow-auto p-4 font-mono text-xs leading-relaxed lg:min-h-[560px]">
                  {logLines.length === 0 && !matchRunning && (
                    <p className="text-slate-600">
                      Output appears here when you run the batch matchmaker…
                    </p>
                  )}
                  {logLines.map((entry, i) => (
                    <div key={i} className={`whitespace-pre-wrap break-words ${logColor(entry.type)}`}>
                      {entry.text}
                    </div>
                  ))}
                  {matchRunning && logLines.length === 0 && (
                    <div className="flex items-center gap-2 text-slate-500">
                      <Loader2 className="h-4 w-4 animate-spin" /> Connecting…
                    </div>
                  )}
                  <div ref={logEndRef} />
                </div>
              </div>
            </div>
          )}

          {tab === 'directory' && (
            <VendorDirectory profileRefreshEpoch={profileRefreshEpoch} />
          )}
          {tab === 'buyers' && <BuyerDirectory profileRefreshEpoch={profileRefreshEpoch} />}
          {tab === 'audits' && <PostTransactionAudits />}
        </div>
      </main>
      <ConfirmModal
        isOpen={isModalOpen}
        title={modalTitle}
        message={modalMessage}
        confirmText={modalConfirmText}
        onConfirm={handleModalConfirm}
        onCancel={closeModal}
        showCancel={modalShowCancel}
      />
    </div>
  )
}
