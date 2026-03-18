import { useCallback, useEffect, useState } from 'react'
import type OpenSeadragon from 'openseadragon'
import {
  fetchPages,
  fetchMasterJson,
  fetchProfile,
  type Page,
  type PageMaster,
  type CorpusProfile,
  type Region,
} from '../lib/api.ts'
import Viewer from '../components/Viewer.tsx'
import RegionOverlay from '../components/RegionOverlay.tsx'
import LayerPanel from '../components/LayerPanel.tsx'
import TranscriptionPanel from '../components/TranscriptionPanel.tsx'
import TranslationPanel from '../components/TranslationPanel.tsx'
import CommentaryPanel from '../components/CommentaryPanel.tsx'

interface Props {
  manuscriptId: string
  profileId: string
  onBack: () => void
}

export default function Reader({ manuscriptId, profileId, onBack }: Props) {
  const [pages, setPages] = useState<Page[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [master, setMaster] = useState<PageMaster | null>(null)
  const [profile, setProfile] = useState<CorpusProfile | null>(null)
  const [visibleLayers, setVisibleLayers] = useState<Set<string>>(new Set())
  const [osdViewer, setOsdViewer] = useState<OpenSeadragon.Viewer | null>(null)
  const [selectedRegion, setSelectedRegion] = useState<Region | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Chargement initial : liste des pages + profil
  useEffect(() => {
    Promise.all([fetchPages(manuscriptId), fetchProfile(profileId)])
      .then(([pgs, prof]) => {
        const sorted = [...pgs].sort((a, b) => a.sequence - b.sequence)
        setPages(sorted)
        setProfile(prof)
        setVisibleLayers(new Set(prof.active_layers))
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [manuscriptId, profileId])

  // Chargement du master.json à chaque changement de page
  useEffect(() => {
    if (pages.length === 0) return
    setMaster(null)
    setSelectedRegion(null)
    fetchMasterJson(pages[currentIndex].id).then(setMaster).catch(() => setMaster(null))
  }, [pages, currentIndex])

  const handleViewerReady = useCallback((v: OpenSeadragon.Viewer) => {
    setOsdViewer(v)
  }, [])

  const toggleLayer = useCallback((layer: string) => {
    setVisibleLayers((prev) => {
      const next = new Set(prev)
      if (next.has(layer)) next.delete(layer)
      else next.add(layer)
      return next
    })
  }, [])

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

  if (pages.length === 0) {
    return (
      <div className="p-8 text-stone-500">
        Aucune page dans ce manuscrit.{' '}
        <button onClick={onBack} className="underline">
          Retour
        </button>
      </div>
    )
  }

  const currentPage = pages[currentIndex]
  const imageUrl = currentPage.image_master_path ?? ''
  const regions: Region[] = master?.layout?.regions ?? []

  return (
    <div className="flex flex-col h-screen bg-stone-100">
      {/* ── Barre de navigation ─────────────────────────────────────────────── */}
      <header className="flex items-center gap-3 bg-stone-900 text-stone-100 px-5 py-2.5 shrink-0">
        <button
          onClick={onBack}
          className="text-stone-400 hover:text-stone-100 text-sm transition-colors"
        >
          ← Corpus
        </button>
        <span className="text-stone-600">|</span>
        <span className="text-sm font-medium text-stone-200 truncate max-w-xs">
          {profile?.label ?? profileId}
        </span>

        <div className="ml-auto flex items-center gap-2">
          <span className="text-stone-400 text-xs">
            {currentPage.folio_label} — {currentIndex + 1} / {pages.length}
          </span>
          <button
            disabled={currentIndex === 0}
            onClick={() => setCurrentIndex((i) => i - 1)}
            className="px-3 py-1 bg-stone-700 hover:bg-stone-600 disabled:opacity-30 rounded text-sm transition-colors"
          >
            ←
          </button>
          <button
            disabled={currentIndex === pages.length - 1}
            onClick={() => setCurrentIndex((i) => i + 1)}
            className="px-3 py-1 bg-stone-700 hover:bg-stone-600 disabled:opacity-30 rounded text-sm transition-colors"
          >
            →
          </button>
        </div>
      </header>

      {/* ── Contenu principal ───────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Visionneuse 70% */}
        <div className="relative flex flex-col" style={{ width: '70%' }}>
          <Viewer imageUrl={imageUrl} onViewerReady={handleViewerReady} />
          <RegionOverlay
            viewer={osdViewer}
            regions={regions}
            onRegionClick={setSelectedRegion}
          />

          {/* Fiche région (popup) */}
          {selectedRegion && (
            <div className="absolute bottom-14 left-4 bg-white/95 backdrop-blur-sm rounded-lg shadow-xl border border-stone-200 p-3 max-w-xs text-xs">
              <div className="flex items-center justify-between gap-4 mb-1.5">
                <span className="font-semibold text-stone-800 capitalize">
                  {selectedRegion.type.replace(/_/g, ' ')}
                </span>
                <button
                  onClick={() => setSelectedRegion(null)}
                  className="text-stone-400 hover:text-stone-700 leading-none"
                >
                  ✕
                </button>
              </div>
              <div className="space-y-0.5 text-stone-500">
                <div>id : <span className="font-mono">{selectedRegion.id}</span></div>
                <div>confiance : {(selectedRegion.confidence * 100).toFixed(0)} %</div>
                <div>bbox : [{selectedRegion.bbox.join(', ')}]</div>
              </div>
            </div>
          )}

          {/* Indicateur page non analysée */}
          {!master && !loading && imageUrl && (
            <div className="absolute top-3 left-3 bg-amber-500/90 text-white text-xs px-3 py-1 rounded-full">
              Page non analysée
            </div>
          )}
        </div>

        {/* Panneaux droite 30% */}
        <div
          className="flex flex-col overflow-hidden border-l border-stone-200 bg-white"
          style={{ width: '30%' }}
        >
          {profile && (
            <LayerPanel
              activeLayers={profile.active_layers}
              visibleLayers={visibleLayers}
              onToggle={toggleLayer}
            />
          )}

          <div className="flex-1 overflow-y-auto divide-y divide-stone-100">
            {master ? (
              <>
                <TranscriptionPanel
                  ocr={master.ocr}
                  editorial={master.editorial}
                  visible={visibleLayers.has('ocr_diplomatic')}
                />
                <TranslationPanel
                  translation={master.translation}
                  editorial={master.editorial}
                  visible={visibleLayers.has('translation_fr')}
                />
                <CommentaryPanel
                  commentary={master.commentary}
                  editorial={master.editorial}
                  visiblePublic={visibleLayers.has('public_commentary')}
                  visibleScholarly={visibleLayers.has('scholarly_commentary')}
                />
              </>
            ) : (
              <div className="p-4 text-sm text-stone-400 italic">
                {imageUrl
                  ? 'Cette page n'a pas encore été analysée par l'IA.'
                  : 'Aucune image associée à cette page.'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
