import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, Mail, Phone, Search, ShieldCheck, Star, Users2 } from 'lucide-react'

const apiBase = import.meta.env.VITE_API_BASE ?? ''

function apiUrl(path) {
  return `${apiBase}${path}`
}

export default function VendorDirectory({ profileRefreshEpoch = 0 }) {
  const [vendors, setVendors] = useState([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expandedIds, setExpandedIds] = useState(() => new Set())

  useEffect(() => {
    const run = async () => {
      setLoading(true)
      setError('')
      try {
        const url = `${apiUrl('/api/vendor-profiles')}?_=${encodeURIComponent(String(profileRefreshEpoch))}&_ts=${Date.now()}`
        const r = await fetch(url, { cache: 'no-store' })
        if (!r.ok) throw new Error(`Failed to load vendors: ${r.status}`)
        const data = await r.json()
        setVendors(Array.isArray(data) ? data : [])
      } catch (e) {
        setError(e.message || 'Unable to load vendors.')
      } finally {
        setLoading(false)
      }
    }
    run()
  }, [profileRefreshEpoch])

  const toggleCardExpanded = (cardKey) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(cardKey)) next.delete(cardKey)
      else next.add(cardKey)
      return next
    })
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return vendors
    return vendors.filter((v) => {
      const name = String(v.Vendor_Name ?? '').toLowerCase()
      const phone = String(v.Contact_Phone ?? '').toLowerCase()
      const vendorId = String(v.Vendor_ID ?? '').toLowerCase()
      return name.includes(q) || phone.includes(q) || vendorId.includes(q)
    })
  }, [query, vendors])

  const renderStars = (ratingValue) => {
    const rating = Number(ratingValue ?? 0)
    const fullStars = Math.max(0, Math.min(5, Math.round(rating)))
    return (
      <div className="flex items-center gap-1">
        {Array.from({ length: 5 }).map((_, i) => (
          <Star
            key={i}
            className={`h-4 w-4 ${
              i < fullStars ? 'fill-amber-400 text-amber-400' : 'text-slate-600'
            }`}
          />
        ))}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Vendor Directory
            </p>
            <h2 className="mt-1 text-2xl font-semibold text-white">Verified MSME Partners</h2>
            <p className="mt-1 text-sm text-slate-400">
              Browse all persisted vendors and monitor lead distribution.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 lg:min-w-[360px]">
            <Search className="h-4 w-4 text-slate-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by vendor ID, name, or phone"
              className="w-full bg-transparent text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none"
            />
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between text-sm">
        <p className="text-slate-400">
          Showing <span className="font-semibold text-slate-200">{filtered.length}</span> of{' '}
          <span className="font-semibold text-slate-200">{vendors.length}</span> vendors
        </p>
      </div>

      {loading && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-12 text-center text-slate-400">
          Loading vendor directory...
        </div>
      )}

      {!loading && error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">
          {error}
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-12 text-center">
          <Users2 className="mx-auto h-12 w-12 text-slate-600" />
          <p className="mt-3 text-slate-400">No vendors found for this search.</p>
        </div>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((v) => {
            const id = String(v.Vendor_ID ?? '')
            const cardKey = id || `${v.Vendor_Name}-${v.Contact_Phone}`
            const leads = Number(v.Leads_Received ?? 0)
            const rating = Number(v.Vendor_Rating ?? 0)
            const reviews = Number(v.Total_Reviews ?? 0)
            const defectRate = Number(v.Defect_Rate_Pct ?? 0)
            const trustScore = Number(v.Trust_Score ?? Math.max(0, 100 - defectRate))
            const isGovtVerified = Boolean(v.Govt_Order_Badge ?? v.Gov_Order_Badge)
            const expanded = expandedIds.has(cardKey)
            return (
              <article
                key={cardKey}
                className="rounded-2xl border border-slate-800 bg-gradient-to-b from-slate-900 to-slate-950 p-5 shadow-lg transition hover:border-amber-500/40 hover:shadow-amber-900/20"
              >
                <div className="mb-4 flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-lg font-semibold text-white">{v.Vendor_Name}</h3>
                      {isGovtVerified ? (
                        <span
                          title="Gov order badge: strong performance on government / public-sector buyer orders."
                          className="inline-flex items-center gap-1 rounded-full border border-yellow-400/60 bg-gradient-to-r from-yellow-500/25 via-amber-400/20 to-yellow-500/25 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-yellow-100 shadow-sm shadow-amber-900/40"
                        >
                          <span aria-hidden>🎖️</span>
                          Gov Approved
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs uppercase tracking-wide text-slate-400">
                      {v.Category || 'Uncategorized'}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {renderStars(rating)}
                      <span className="text-xs font-medium tabular-nums text-slate-300">
                        {Number.isNaN(rating) ? '—' : rating.toFixed(2)}
                        <span className="font-normal text-slate-500"> /5</span>
                      </span>
                      <span className="text-xs text-slate-400">
                        ({Number.isNaN(reviews) ? 0 : reviews} Reviews)
                      </span>
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-2">
                    <button
                      type="button"
                      onClick={() => toggleCardExpanded(cardKey)}
                      aria-expanded={expanded}
                      title={expanded ? 'Hide quality control metrics' : 'Show defect rate and trust score'}
                      className="inline-flex items-center gap-1 rounded-lg border border-slate-600/80 bg-slate-800/50 px-2.5 py-1.5 text-xs font-medium text-slate-300 transition hover:border-emerald-500/40 hover:bg-slate-800 hover:text-white"
                    >
                      {expanded ? 'Hide metrics' : 'QC details'}
                      <ChevronDown
                        className={`h-3.5 w-3.5 transition-transform ${expanded ? 'rotate-180' : ''}`}
                        aria-hidden
                      />
                    </button>
                    <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-300">
                      Leads: {Number.isNaN(leads) ? 0 : leads}
                    </span>
                  </div>
                </div>

                {isGovtVerified && (
                  <div
                    title="Successful fulfillment for government or public-sector buyers with low defects and on-time payment."
                    className="mb-4 flex items-center gap-2 rounded-xl border border-yellow-500/45 bg-gradient-to-r from-yellow-500/15 via-amber-500/10 to-yellow-500/15 px-3 py-2 shadow-inner shadow-amber-900/25"
                  >
                    <ShieldCheck className="h-4 w-4 shrink-0 text-yellow-300" aria-hidden />
                    <span className="text-xs font-medium leading-snug text-yellow-50/95">
                      Public-sector fulfillment track record from audited dock transactions.
                    </span>
                  </div>
                )}

                <div className="space-y-2 text-sm">
                  <p className="text-slate-300">
                    <span className="mr-2 inline-block rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-400">
                      ID
                    </span>
                    {id}
                  </p>
                  <p className="flex items-center gap-2 text-slate-300">
                    <Phone className="h-4 w-4 text-amber-400" />
                    {v.Contact_Phone || 'NA'}
                  </p>
                  <p className="flex items-center gap-2 text-slate-300">
                    <Mail className="h-4 w-4 text-sky-400" />
                    {v.Contact_Email || 'NA'}
                  </p>
                  {expanded && (
                    <div className="mt-3 rounded-lg border border-slate-700 bg-slate-900/70 p-2.5">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                        Quality Control Metric
                      </p>
                      <div className="mt-1 flex items-center justify-between text-sm">
                        <span className="text-slate-300">
                          Defect Rate: {Number.isNaN(defectRate) ? '0.00' : defectRate.toFixed(2)}%
                        </span>
                        <span className="font-semibold text-emerald-300">
                          Trust Score: {Number.isNaN(trustScore) ? '0.00' : trustScore.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
