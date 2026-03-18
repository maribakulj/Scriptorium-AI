const BASE_URL: string = import.meta.env.VITE_API_URL ?? ''

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Corpus {
  id: string
  slug: string
  title: string
  profile_id: string
  created_at: string
  updated_at: string
}

export interface Manuscript {
  id: string
  corpus_id: string
  title: string
  shelfmark: string | null
  date_label: string | null
  total_pages: number
}

export interface Page {
  id: string
  manuscript_id: string
  folio_label: string
  sequence: number
  image_master_path: string | null
  processing_status: string
  confidence_summary: number | null
}

export type RegionType =
  | 'text_block'
  | 'miniature'
  | 'decorated_initial'
  | 'margin'
  | 'rubric'
  | 'other'

export interface Region {
  id: string
  type: RegionType
  bbox: [number, number, number, number]
  confidence: number
  polygon?: number[][] | null
  parent_region_id?: string | null
}

export interface OCRResult {
  diplomatic_text: string
  language: string
  confidence: number
  uncertain_segments: string[]
}

export interface Translation {
  fr: string
  en: string
}

export interface CommentaryClaim {
  claim: string
  evidence_region_ids: string[]
  certainty: 'high' | 'medium' | 'low' | 'speculative'
}

export interface Commentary {
  public: string
  scholarly: string
  claims: CommentaryClaim[]
}

export type EditorialStatus =
  | 'machine_draft'
  | 'needs_review'
  | 'reviewed'
  | 'validated'
  | 'published'

export interface EditorialInfo {
  status: EditorialStatus
  validated: boolean
  validated_by: string | null
  version: number
  notes: string[]
}

export interface ImageInfo {
  master?: string
  derivative_web?: string
  iiif_base?: string
  width?: number
  height?: number
}

export interface PageMaster {
  schema_version: string
  page_id: string
  corpus_profile: string
  manuscript_id: string
  folio_label: string
  sequence: number
  image: ImageInfo
  layout: { regions: Region[] }
  ocr: OCRResult | null
  translation: Translation | null
  summary: { short: string; detailed: string } | null
  commentary: Commentary | null
  editorial: EditorialInfo
}

export interface CorpusProfile {
  profile_id: string
  label: string
  language_hints: string[]
  script_type: string
  active_layers: string[]
  uncertainty_config: { flag_below: number; min_acceptable: number }
  export_config: { mets: boolean; alto: boolean; tei: boolean }
}

// ── Fetch helpers ─────────────────────────────────────────────────────────────

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`)
  if (!resp.ok) throw new Error(`HTTP ${resp.status} — ${path}`)
  return resp.json() as Promise<T>
}

// ── API functions ─────────────────────────────────────────────────────────────

export const fetchCorpora = (): Promise<Corpus[]> =>
  get('/api/v1/corpora')

export const fetchManuscripts = (corpusId: string): Promise<Manuscript[]> =>
  get(`/api/v1/corpora/${corpusId}/manuscripts`)

export const fetchPages = (manuscriptId: string): Promise<Page[]> =>
  get(`/api/v1/manuscripts/${manuscriptId}/pages`)

export const fetchMasterJson = (pageId: string): Promise<PageMaster> =>
  get(`/api/v1/pages/${pageId}/master-json`)

export const fetchManifest = (manuscriptId: string): Promise<unknown> =>
  get(`/api/v1/manuscripts/${manuscriptId}/iiif-manifest`)

export const fetchProfile = (profileId: string): Promise<CorpusProfile> =>
  get(`/api/v1/profiles/${profileId}`)
