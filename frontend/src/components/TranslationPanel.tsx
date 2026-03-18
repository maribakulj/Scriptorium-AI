import type { FC } from 'react'
import type { Translation, EditorialInfo, EditorialStatus } from '../lib/api.ts'

const STATUS_LABELS: Record<EditorialStatus, string> = {
  machine_draft: 'Brouillon IA',
  needs_review: 'À réviser',
  reviewed: 'Révisé',
  validated: 'Validé',
  published: 'Publié',
}

const STATUS_COLORS: Record<EditorialStatus, string> = {
  machine_draft: 'bg-amber-100 text-amber-700',
  needs_review: 'bg-orange-100 text-orange-700',
  reviewed: 'bg-blue-100 text-blue-700',
  validated: 'bg-green-100 text-green-700',
  published: 'bg-emerald-100 text-emerald-700',
}

interface Props {
  translation: Translation | null
  editorial: EditorialInfo
  visible: boolean
}

const TranslationPanel: FC<Props> = ({ translation, editorial, visible }) => {
  if (!visible) return null

  return (
    <div className="px-4 py-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wide">
          Traduction (FR)
        </h3>
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[editorial.status]}`}
        >
          {STATUS_LABELS[editorial.status]}
        </span>
      </div>
      {translation?.fr ? (
        <p className="text-sm text-stone-800 leading-relaxed whitespace-pre-wrap">
          {translation.fr}
        </p>
      ) : (
        <p className="text-sm text-stone-400 italic">Traduction non disponible.</p>
      )}
    </div>
  )
}

export default TranslationPanel
