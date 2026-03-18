import { useCallback, useEffect, useRef, useState } from 'react'
import {
  applyCorrections,
  getHistory,
  fetchMasterJson,
  type PageMaster,
  type VersionInfo,
} from '../lib/api.ts'
import Viewer from '../components/Viewer.tsx'

interface Props {
  pageId: string
  onBack: () => void
}

type Panel = 'transcription' | 'commentary' | 'regions' | 'history'

export default function Editor({ pageId, onBack }: Props) {
  const [master, setMaster] = useState<PageMaster | null>(null)
  const [history, setHistory] = useState<VersionInfo[]>([])
  const [activePanel, setActivePanel] = useState<Panel>('transcription')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // Editable field values
  const [ocrText, setOcrText] = useState('')
  const [commentaryPublic, setCommentaryPublic] = useState('')
  const [commentaryScholarly, setCommentaryScholarly] = useState('')
  const [editorialStatus, setEditorialStatus] = useState('')
  const [regionValidations, setRegionValidations] = useState<Record<string, string>>({})

  const successTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [m, h] = await Promise.all([fetchMasterJson(pageId), getHistory(pageId)])
      setMaster(m)
      setHistory(h)
      setOcrText(m.ocr?.diplomatic_text ?? '')
      setCommentaryPublic(m.commentary?.public ?? '')
      setCommentaryScholarly(m.commentary?.scholarly ?? '')
      setEditorialStatus(m.editorial.status)
      // Restore existing region validations from extensions
      const ext = (m as unknown as { extensions?: { region_validations?: Record<string, string> } }).extensions
      setRegionValidations(ext?.region_validations ?? {})
    } catch (e: unknown) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [pageId])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const handleSave = async () => {
    setSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    try {
      const updated = await applyCorrections(pageId, {
        ocr_diplomatic_text: ocrText !== (master?.ocr?.diplomatic_text ?? '') ? ocrText : undefined,
        editorial_status: editorialStatus !== master?.editorial.status ? editorialStatus : undefined,
        commentary_public: commentaryPublic !== (master?.commentary?.public ?? '') ? commentaryPublic : undefined,
        commentary_scholarly: commentaryScholarly !== (master?.commentary?.scholarly ?? '') ? commentaryScholarly : undefined,
        region_validations: Object.keys(regionValidations).length > 0 ? regionValidations : undefined,
      })
      setMaster(updated)
      const h = await getHistory(pageId)
      setHistory(h)
      setSaveSuccess(true)
      if (successTimeout.current) clearTimeout(successTimeout.current)
      successTimeout.current = setTimeout(() => setSaveSuccess(false), 3000)
    } catch (e: unknown) {
      setSaveError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const handleRestore = async (version: number) => {
    setSaving(true)
    setSaveError(null)
    try {
      const updated = await applyCorrections(pageId, { restore_to_version: version })
      setMaster(updated)
      setOcrText(updated.ocr?.diplomatic_text ?? '')
      setCommentaryPublic(updated.commentary?.public ?? '')
      setCommentaryScholarly(updated.commentary?.scholarly ?? '')
      setEditorialStatus(updated.editorial.status)
      const h = await getHistory(pageId)
      setHistory(h)
    } catch (e: unknown) {
      setSaveError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const setRegionValidation = (regionId: string, val: string) => {
    setRegionValidations((prev) => ({ ...prev, [regionId]: val }))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen text-stone-500">
        Chargement…
      </div>
    )
  }

  if (error) {
    return <div className="p-8 text-red-600">Erreur : {error}</div>
  }

  const imageUrl = master ? '' : '' // image path not directly stored on PageMaster
  const regions = master?.layout?.regions ?? []

  return (
    <div className="flex flex-col h-screen bg-stone-100">
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <header className="flex items-center gap-3 bg-stone-900 text-stone-100 px-5 py-2.5 shrink-0">
        <button
          onClick={onBack}
          className="text-stone-400 hover:text-stone-100 text-sm transition-colors"
        >
          ← Retour
        </button>
        <span className="text-stone-600">|</span>
        <span className="text-sm font-medium text-stone-200">
          Éditeur — {master?.folio_label ?? pageId}
        </span>
        {master && (
          <span className="ml-2 text-xs text-stone-400">
            v{master.editorial.version} · {master.editorial.status}
          </span>
        )}

        <div className="ml-auto flex items-center gap-3">
          {saveSuccess && (
            <span className="text-green-400 text-xs">Enregistré</span>
          )}
          {saveError && (
            <span className="text-red-400 text-xs">{saveError}</span>
          )}
          <button
            onClick={() => void handleSave()}
            disabled={saving}
            className="px-4 py-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white text-sm rounded transition-colors"
          >
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      </header>

      {/* ── Layout 50 / 50 ──────────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Visionneuse gauche */}
        <div className="relative" style={{ width: '50%' }}>
          <Viewer imageUrl={imageUrl} onViewerReady={() => {}} />
          {!imageUrl && (
            <div className="absolute inset-0 flex items-center justify-center bg-stone-200 text-stone-400 text-sm">
              Aperçu image non disponible
            </div>
          )}
        </div>

        {/* Panneaux droite */}
        <div
          className="flex flex-col border-l border-stone-200 bg-white"
          style={{ width: '50%' }}
        >
          {/* Onglets */}
          <div className="flex border-b border-stone-200 shrink-0">
            {(['transcription', 'commentary', 'regions', 'history'] as Panel[]).map((p) => (
              <button
                key={p}
                onClick={() => setActivePanel(p)}
                className={`flex-1 py-2.5 text-xs font-medium capitalize transition-colors ${
                  activePanel === p
                    ? 'border-b-2 border-amber-500 text-amber-700 bg-amber-50'
                    : 'text-stone-500 hover:text-stone-800'
                }`}
              >
                {p === 'transcription' ? 'Transcription' :
                 p === 'commentary' ? 'Commentaire' :
                 p === 'regions' ? 'Régions' : 'Historique'}
              </button>
            ))}
          </div>

          {/* Contenu du panneau actif */}
          <div className="flex-1 overflow-y-auto p-4">

            {/* ── Transcription ─────────────────────────────────────────── */}
            {activePanel === 'transcription' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-stone-600 mb-1.5 uppercase tracking-wide">
                    Texte diplomatique (OCR)
                  </label>
                  <textarea
                    value={ocrText}
                    onChange={(e) => setOcrText(e.target.value)}
                    rows={12}
                    className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-amber-400 resize-y"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-stone-600 mb-1.5 uppercase tracking-wide">
                    Statut éditorial
                  </label>
                  <select
                    value={editorialStatus}
                    onChange={(e) => setEditorialStatus(e.target.value)}
                    className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400"
                  >
                    <option value="machine_draft">machine_draft</option>
                    <option value="needs_review">needs_review</option>
                    <option value="reviewed">reviewed</option>
                    <option value="validated">validated</option>
                    <option value="published">published</option>
                  </select>
                </div>
                {master?.ocr && (
                  <div className="text-xs text-stone-400 space-y-0.5">
                    <div>Langue : {master.ocr.language}</div>
                    <div>Confiance : {(master.ocr.confidence * 100).toFixed(0)} %</div>
                  </div>
                )}
              </div>
            )}

            {/* ── Commentaire ───────────────────────────────────────────── */}
            {activePanel === 'commentary' && (
              <div className="space-y-5">
                <div>
                  <label className="block text-xs font-semibold text-stone-600 mb-1.5 uppercase tracking-wide">
                    Commentaire public
                  </label>
                  <textarea
                    value={commentaryPublic}
                    onChange={(e) => setCommentaryPublic(e.target.value)}
                    rows={6}
                    className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 resize-y"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-stone-600 mb-1.5 uppercase tracking-wide">
                    Commentaire savant
                  </label>
                  <textarea
                    value={commentaryScholarly}
                    onChange={(e) => setCommentaryScholarly(e.target.value)}
                    rows={8}
                    className="w-full border border-stone-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400 resize-y"
                  />
                </div>
              </div>
            )}

            {/* ── Régions ───────────────────────────────────────────────── */}
            {activePanel === 'regions' && (
              <div className="space-y-2">
                {regions.length === 0 ? (
                  <p className="text-sm text-stone-400 italic">Aucune région détectée.</p>
                ) : (
                  regions.map((region) => {
                    const validation = regionValidations[region.id]
                    return (
                      <div
                        key={region.id}
                        className="flex items-center justify-between border border-stone-200 rounded-lg px-3 py-2.5 text-sm"
                      >
                        <div>
                          <span className="font-medium text-stone-800 capitalize">
                            {region.type.replace(/_/g, ' ')}
                          </span>
                          <span className="ml-2 text-xs text-stone-400 font-mono">{region.id}</span>
                          <div className="text-xs text-stone-400">
                            confiance : {(region.confidence * 100).toFixed(0)} %
                          </div>
                        </div>
                        <div className="flex gap-2 ml-4 shrink-0">
                          <button
                            onClick={() => setRegionValidation(region.id, 'validated')}
                            className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                              validation === 'validated'
                                ? 'bg-green-600 text-white'
                                : 'bg-stone-100 text-stone-600 hover:bg-green-100'
                            }`}
                          >
                            Valider
                          </button>
                          <button
                            onClick={() => setRegionValidation(region.id, 'rejected')}
                            className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                              validation === 'rejected'
                                ? 'bg-red-600 text-white'
                                : 'bg-stone-100 text-stone-600 hover:bg-red-100'
                            }`}
                          >
                            Rejeter
                          </button>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            )}

            {/* ── Historique ────────────────────────────────────────────── */}
            {activePanel === 'history' && (
              <div className="space-y-2">
                {history.length === 0 ? (
                  <p className="text-sm text-stone-400 italic">
                    Aucune version archivée.
                  </p>
                ) : (
                  history.map((v) => (
                    <div
                      key={v.version}
                      className="flex items-center justify-between border border-stone-200 rounded-lg px-3 py-2.5 text-sm"
                    >
                      <div>
                        <span className="font-medium text-stone-800">v{v.version}</span>
                        <span className="ml-2 text-xs text-stone-500">{v.status}</span>
                        <div className="text-xs text-stone-400 mt-0.5">
                          {new Date(v.saved_at).toLocaleString('fr-FR')}
                        </div>
                      </div>
                      <button
                        onClick={() => void handleRestore(v.version)}
                        disabled={saving}
                        className="ml-4 px-3 py-1 text-xs bg-stone-100 text-stone-600 hover:bg-amber-100 hover:text-amber-700 disabled:opacity-40 rounded-md transition-colors"
                      >
                        Restaurer
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
