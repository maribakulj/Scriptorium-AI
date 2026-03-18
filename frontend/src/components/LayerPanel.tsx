import type { FC } from 'react'

const LAYER_LABELS: Record<string, string> = {
  image: 'Image',
  ocr_diplomatic: 'Transcription diplomatique',
  ocr_normalized: 'Transcription normalisée',
  translation_fr: 'Traduction (FR)',
  translation_en: 'Traduction (EN)',
  summary: 'Résumé',
  scholarly_commentary: 'Commentaire savant',
  public_commentary: 'Commentaire public',
  iconography_detection: 'Iconographie',
  material_notes: 'Notes matérielles',
  uncertainty: 'Incertitudes',
}

interface Props {
  activeLayers: string[]
  visibleLayers: Set<string>
  onToggle: (layer: string) => void
}

const LayerPanel: FC<Props> = ({ activeLayers, visibleLayers, onToggle }) => (
  <div className="border-b border-stone-200 bg-stone-50 px-4 py-3 shrink-0">
    <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-2">
      Couches
    </h3>
    <div className="flex flex-wrap gap-x-4 gap-y-1.5">
      {activeLayers.map((layer) => (
        <label
          key={layer}
          className="flex items-center gap-1.5 text-xs text-stone-700 cursor-pointer select-none"
        >
          <input
            type="checkbox"
            checked={visibleLayers.has(layer)}
            onChange={() => onToggle(layer)}
            className="rounded border-stone-300 text-stone-700 focus:ring-stone-500"
          />
          {LAYER_LABELS[layer] ?? layer}
        </label>
      ))}
    </div>
  </div>
)

export default LayerPanel
