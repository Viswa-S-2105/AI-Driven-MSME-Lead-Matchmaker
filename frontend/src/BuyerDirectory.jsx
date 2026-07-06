import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Building2, ChevronDown, Search, Star, Users2 } from 'lucide-react'

const apiBase = import.meta.env.VITE_API_BASE ?? ''

function apiUrl(path) {
  return `${apiBase}${path}`
}

function renderStars(ratingValue) {
  const rating = Number(ratingValue ?? 0)
  const fullStars = Math.max(0, Math.min(5, Math.round(rating)))
  return (
    <div className="flex items-center gap-1">
      {Array.from({ length: 5 }).map((_, i) => (
        <Star
          key={i}
          className={`h-4 w-4 ${i < fullStars ? 'fill-amber-400 text-amber-400' : 'text-slate-600'}`}
        />
      ))}
    </div>
  )
}

export default function BuyerDirectory({ profileRefreshEpoch = 0 }) {
  const [buyers, setBuyers] = useState([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expandedIds, setExpandedIds] = useState(() => new Set())

  useEffect(() => {
    const run = async () => {
      setLoading(true)
      setError('')
      try {
        const url = `${apiUrl('/api/buyer-profiles')}?_=${encodeURIComponent(String(profileRefreshEpoch))}&_ts=${Date.now()}`
        const r = await fetch(url, { cache: 'no-store' })
        if (!r.ok) throw new Error(`Failed to load buyers: ${r.status}`)
        const data = await r.json()
        setBuyers(Array.isArray(data) ? data : [])
      } catch (e) {
        setError(e.message || 'Unable to load buyer directory.')
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
    if (!q) return buyers
    return buyers.filter((b) => {
      const company = String(b.Company_Name ?? '').toLowerCase()
      const buyerId = String(b.Buyer_ID ?? '').toLowerCase()
      return company.includes(q) || buyerId.includes(q)
    })
  }, [buyers, query])

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Buyer Directory</p>
            <h2 className="mt-1 text-2xl font-semibold text-white">Registered Foreign Buyers</h2>
            <p className="mt-1 text-sm text-slate-400">
              Review buyer trust indicators before committing shipments.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 lg:min-w-[360px]">
            <Search className="h-4 w-4 text-slate-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by buyer ID or company"
              className="w-full bg-transparent text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none"
            />
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between text-sm">
        <p className="text-slate-400">
          Showing <span className="font-semibold text-slate-200">{filtered.length}</span> of{' '}
          <span className="font-semibold text-slate-200">{buyers.length}</span> buyers
        </p>
      </div>

      {loading && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-12 text-center text-slate-400">
          Loading buyer directory...
        </div>
      )}
      {!loading && error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">{error}</div>
      )}
      {!loading && !error && filtered.length === 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-12 text-center">
          <Users2 className="mx-auto h-12 w-12 text-slate-600" />
          <p className="mt-3 text-slate-400">No buyers found for this search.</p>
        </div>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((b) => {
            const id = String(b.Buyer_ID ?? '')
            const cardKey = id || String(b.Company_Name ?? '')
            const totalReviews = Number(b.Total_Reviews ?? 0)
            const paymentDelayFlags = Number(b.Payment_Delay_Flags ?? 0)
            const adjustedRating = Number(b.Adjusted_Buyer_Rating ?? b.Buyer_Rating ?? 0)
            const isNewBuyer = Boolean(b.New_Buyer) || totalReviews === 0
            const expanded = expandedIds.has(cardKey)
            const hasDelayWarning = paymentDelayFlags > 0
            const showGovernmentBadge =
              b.Government_Directory_Badge === true ||
              (String(b.Entity_Type ?? 'Private').trim().toLowerCase() !== 'private' &&
                String(b.Entity_Type ?? '').trim().length > 0)

            return (
              <article
                key={cardKey}
                className="rounded-2xl border border-slate-800 bg-gradient-to-b from-slate-900 to-slate-950 p-5 shadow-lg transition hover:border-sky-500/40 hover:shadow-sky-900/20"
              >
                <div className="mb-4 flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-lg font-semibold text-white">{b.Company_Name}</h3>
                      {showGovernmentBadge ? (
                        <span className="inline-flex items-center gap-1 rounded-lg border border-sky-500/50 bg-sky-500/15 px-2 py-0.5 text-xs font-semibold text-sky-100 shadow-sm shadow-sky-900/30">
                          <span aria-hidden>🏛️</span>
                          Government
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs uppercase tracking-wide text-slate-400">Buyer ID: {id || 'NA'}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    {hasDelayWarning ? (
                      <button
                        type="button"
                        onClick={() => toggleCardExpanded(cardKey)}
                        aria-expanded={expanded}
                        title={expanded ? 'Hide payment delay notice' : 'Show payment delay notice'}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-600/80 bg-slate-800/50 px-2.5 py-1.5 text-xs font-medium text-slate-300 transition hover:border-amber-500/40 hover:bg-slate-800 hover:text-white"
                      >
                        {expanded ? 'Hide warning' : 'Delay details'}
                        <ChevronDown
                          className={`h-3.5 w-3.5 transition-transform ${expanded ? 'rotate-180' : ''}`}
                          aria-hidden
                        />
                      </button>
                    ) : null}
                    <Building2 className="h-5 w-5 shrink-0 text-sky-300" aria-hidden />
                  </div>
                </div>

                {isNewBuyer ? (
                  <div className="mb-4 inline-flex rounded-full border border-slate-500/50 bg-slate-700/30 px-3 py-1 text-xs font-semibold text-slate-200">
                    New Buyer - Unrated
                  </div>
                ) : (
                  <div className="mb-4 flex items-center gap-2">
                    {renderStars(adjustedRating)}
                    <span className="text-xs text-slate-400">({totalReviews} Reviews)</span>
                  </div>
                )}

                <div className="space-y-2 text-sm">
                  <p className="text-slate-300">
                    Base Rating:{' '}
                    <span className="font-semibold text-slate-100">
                      {Number.isNaN(Number(b.Buyer_Rating)) ? '0.00' : Number(b.Buyer_Rating).toFixed(2)}
                    </span>
                  </p>
                  {!isNewBuyer && (
                    <p className="text-slate-300">
                      Adjusted Rating:{' '}
                      <span className="font-semibold text-sky-300">
                        {Number.isNaN(adjustedRating) ? '0.00' : adjustedRating.toFixed(2)}
                      </span>
                    </p>
                  )}
                </div>

                {expanded && hasDelayWarning && (
                  <div className="mt-3 border-t border-slate-800/80 pt-3">
                    <div className="flex items-center gap-2 rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-xs font-medium text-red-200">
                      <AlertTriangle className="h-4 w-4 shrink-0 text-red-300" aria-hidden />
                      Payment Delays Recorded ({paymentDelayFlags}) - Check demurrage risk
                    </div>
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
