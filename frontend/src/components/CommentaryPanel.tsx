import { useState, type FC } from 'react'
import type { Commentary, EditorialInfo, EditorialStatus } from '../lib/api.ts'

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
  commentary: Commentary | null
  editorial: EditorialInfo
  visiblePublic: boolean
  visibleScholarly: boolean
}

const CommentaryPanel: FC<Props> = ({ commentary, editorial, visiblePublic, visibleScholarly }) => {
  const [tab, setTab] = useState<'public' | 'scholarly'>('public')

  if (!visiblePublic && !visibleScholarly) return null

  // Si une seule couche est visible, forcer l'onglet correspondant
  const activeTab: 'public' | 'scholarly' =
    !visiblePublic && visibleScholarly ? 'scholarly' :
    !visibleScholarly && visiblePublic ? 'public' :
    tab

  const content = activeTab === 'public' ? commentary?.public : commentary?.scholarly
  const bothVisible = visiblePublic && visibleScholarly

  return (
    <div className="px-4 py-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wide">
          Commentaire
        </h3>
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[editorial.status]}`}
        >
          {STATUS_LABELS[editorial.status]}
        </span>
      </div>

      {bothVisible && (
        <div className="flex gap-2 mb-3">
          {(['public', 'scholarly'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`text-xs px-3 py-1 rounded transition-colors ${
                activeTab === t
                  ? 'bg-stone-800 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
              }`}
            >
              {t === 'public' ? 'Public' : 'Savant'}
            </button>
          ))}
        </div>
      )}

      {content ? (
        <p className="text-sm text-stone-800 leading-relaxed whitespace-pre-wrap">{content}</p>
      ) : (
        <p className="text-sm text-stone-400 italic">Commentaire non disponible.</p>
      )}
    </div>
  )
}

export default CommentaryPanel
