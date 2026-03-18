const BASE_URL: string = import.meta.env.VITE_API_URL ?? ''

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ApiKeyResponse {
  valid: boolean
  provider: string
  model_count: number
  error: string | null
}

export interface ModelInfo {
  model_id: string
  display_name: string
  provider: string
  supports_vision: boolean
  input_token_limit: number | null
  output_token_limit: number | null
}

export interface IngestResponse {
  corpus_id: string
  manuscript_id: string
  pages_created: number
  page_ids: string[]
}

export interface CorpusRunResponse {
  corpus_id: string
  jobs_created: number
  job_ids: string[]
}

export type JobStatus = 'pending' | 'running' | 'done' | 'failed'

export interface Job {
  id: string
  corpus_id: string
  page_id: string | null
  status: JobStatus
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  created_at: string
}

export interface CreateCorpusInput {
  slug: string
  title: string
  profile_id: string
}

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

async function post<T>(path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!resp.ok) {
    const payload = await resp.json().catch(() => null)
    const detail = (payload as { detail?: string } | null)?.detail
    throw new Error(detail ?? `HTTP ${resp.status} — ${path}`)
  }
  return resp.json() as Promise<T>
}

async function put<T>(path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!resp.ok) {
    const payload = await resp.json().catch(() => null)
    const detail = (payload as { detail?: string } | null)?.detail
    throw new Error(detail ?? `HTTP ${resp.status} — ${path}`)
  }
  return resp.json() as Promise<T>
}

async function postForm<T>(path: string, data: FormData): Promise<T> {
  const resp = await fetch(`${BASE_URL}${path}`, { method: 'POST', body: data })
  if (!resp.ok) {
    const payload = await resp.json().catch(() => null)
    const detail = (payload as { detail?: string } | null)?.detail
    throw new Error(detail ?? `HTTP ${resp.status} — ${path}`)
  }
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

export const listProfiles = (): Promise<CorpusProfile[]> =>
  get('/api/v1/profiles')

export const createCorpus = (input: CreateCorpusInput): Promise<Corpus> =>
  post('/api/v1/corpora', input)

export const validateApiKey = (apiKey: string): Promise<ApiKeyResponse> =>
  post('/api/v1/settings/api-key', { api_key: apiKey })

export const listModels = (): Promise<ModelInfo[]> =>
  get('/api/v1/models')

export const selectModel = (
  corpusId: string,
  modelId: string,
  displayName: string,
  providerType: string,
): Promise<unknown> =>
  put(`/api/v1/corpora/${corpusId}/model`, {
    model_id: modelId,
    display_name: displayName,
    provider_type: providerType,
  })

export const ingestImages = (
  corpusId: string,
  urls: string[],
  folioLabels: string[],
): Promise<IngestResponse> =>
  post(`/api/v1/corpora/${corpusId}/ingest/iiif-images`, {
    urls,
    folio_labels: folioLabels,
  })

export const ingestManifest = (
  corpusId: string,
  manifestUrl: string,
): Promise<IngestResponse> =>
  post(`/api/v1/corpora/${corpusId}/ingest/iiif-manifest`, {
    manifest_url: manifestUrl,
  })

export const ingestFiles = (
  corpusId: string,
  files: File[],
): Promise<IngestResponse> => {
  const data = new FormData()
  for (const f of files) data.append('files', f)
  return postForm(`/api/v1/corpora/${corpusId}/ingest/files`, data)
}

export const runCorpus = (corpusId: string): Promise<CorpusRunResponse> =>
  post(`/api/v1/corpora/${corpusId}/run`)

export const getJob = (jobId: string): Promise<Job> =>
  get(`/api/v1/jobs/${jobId}`)

export const retryJob = (jobId: string): Promise<Job> =>
  post(`/api/v1/jobs/${jobId}/retry`)
