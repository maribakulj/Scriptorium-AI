import { useCallback, useEffect, useRef, useState } from 'react'
import { searchPages, type SearchResult } from '../lib/api.ts'

interface Props {
  onSelectResult?: (result: SearchResult) => void
}

export default function SearchBar({ onSelectResult }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const runSearch = useCallback(async (q: string) => {
    if (q.trim().length < 2) {
      setResults([])
      setOpen(false)
      return
    }
    setLoading(true)
    try {
      const res = await searchPages(q.trim())
      setResults(res)
      setOpen(true)
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      void runSearch(query)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query, runSearch])

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={containerRef} className="relative w-72">
      <div className="relative">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder="Rechercher dans les manuscrits…"
          className="w-full bg-stone-800 text-stone-100 placeholder-stone-500 text-sm px-3 py-1.5 pr-8 rounded-md border border-stone-700 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500"
        />
        {loading && (
          <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-stone-400 text-xs">
            …
          </span>
        )}
      </div>

      {open && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-stone-200 rounded-lg shadow-xl z-50 max-h-80 overflow-y-auto">
          {results.length === 0 ? (
            <div className="px-4 py-3 text-sm text-stone-400 italic">Aucun résultat.</div>
          ) : (
            <ul>
              {results.map((r) => (
                <li key={r.page_id}>
                  <button
                    onClick={() => {
                      setOpen(false)
                      onSelectResult?.(r)
                    }}
                    className="w-full text-left px-4 py-3 hover:bg-amber-50 border-b border-stone-100 last:border-0 transition-colors"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-stone-800 text-sm">
                        {r.folio_label}
                      </span>
                      <span className="text-xs text-stone-400 shrink-0">
                        score : {r.score}
                      </span>
                    </div>
                    <div className="text-xs text-stone-500 mt-0.5 truncate">
                      {r.excerpt}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
