import { useEffect, useState } from 'react'
import {
  fetchCorpora,
  fetchManuscripts,
  type Corpus,
  type Manuscript,
} from '../lib/api.ts'

interface Props {
  onOpenManuscript: (manuscriptId: string, profileId: string) => void
}

export default function Home({ onOpenManuscript }: Props) {
  const [corpora, setCorpora] = useState<Corpus[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [manuscripts, setManuscripts] = useState<Record<string, Manuscript[]>>({})
  const [expanding, setExpanding] = useState<string | null>(null)

  useEffect(() => {
    fetchCorpora()
      .then(setCorpora)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const handleCorpusClick = async (corpus: Corpus) => {
    // Si déjà chargé, naviguer directement si un seul manuscrit
    const cached = manuscripts[corpus.id]
    if (cached) {
      if (cached.length === 1) onOpenManuscript(cached[0].id, corpus.profile_id)
      return
    }

    setExpanding(corpus.id)
    try {
      const ms = await fetchManuscripts(corpus.id)
      setManuscripts((prev) => ({ ...prev, [corpus.id]: ms }))
      if (ms.length === 1) onOpenManuscript(ms[0].id, corpus.profile_id)
    } catch {
      // Échec silencieux — la liste reste vide
    } finally {
      setExpanding(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen text-stone-500">
        Chargement…
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8 text-red-600">
        Erreur : {error}
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <header className="bg-stone-900 text-stone-100 px-8 py-6">
        <h1 className="text-2xl font-semibold tracking-tight">Scriptorium AI</h1>
        <p className="text-stone-400 text-sm mt-1">
          Plateforme de génération d'éditions savantes augmentées
        </p>
      </header>

      <main className="max-w-3xl mx-auto py-10 px-8">
        <h2 className="text-sm font-semibold text-stone-500 uppercase tracking-wide mb-6">
          Corpus disponibles
        </h2>

        {corpora.length === 0 ? (
          <p className="text-stone-400 text-sm">
            Aucun corpus enregistré. Créez-en un via{' '}
            <code className="bg-stone-200 px-1 rounded text-xs">POST /api/v1/corpora</code>.
          </p>
        ) : (
          <ul className="space-y-3">
            {corpora.map((corpus) => (
              <li key={corpus.id}>
                <button
                  onClick={() => void handleCorpusClick(corpus)}
                  className="w-full text-left bg-white border border-stone-200 rounded-lg px-6 py-4 hover:border-stone-400 hover:shadow-sm transition-all"
                >
                  <div className="font-medium text-stone-900">{corpus.title}</div>
                  <div className="text-xs text-stone-400 mt-1">
                    Profil : {corpus.profile_id} · Slug : {corpus.slug}
                  </div>
                </button>

                {expanding === corpus.id && (
                  <div className="mt-2 ml-4 text-xs text-stone-400">Chargement…</div>
                )}

                {manuscripts[corpus.id] && manuscripts[corpus.id].length > 1 && (
                  <ul className="mt-2 ml-4 space-y-1">
                    {manuscripts[corpus.id].map((ms) => (
                      <li key={ms.id}>
                        <button
                          onClick={() => onOpenManuscript(ms.id, corpus.profile_id)}
                          className="text-sm text-stone-600 hover:text-stone-900 hover:underline text-left"
                        >
                          {ms.title}
                          {ms.total_pages > 0 && (
                            <span className="text-stone-400 ml-1">
                              ({ms.total_pages} pages)
                            </span>
                          )}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  )
}
