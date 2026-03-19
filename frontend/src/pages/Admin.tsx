import { type FormEvent, useEffect, useRef, useState } from 'react'
import {
  fetchCorpora,
  fetchManuscripts,
  fetchPages,
  listProfiles,
  createCorpus,
  deleteCorpus,
  fetchProviders,
  fetchProviderModels,
  selectModel,
  getCorpusModel,
  ingestImages,
  ingestManifest,
  ingestFiles,
  runCorpus,
  getJob,
  retryJob,
  type Corpus,
  type CorpusProfile,
  type CorpusModelConfig,
  type ProviderInfo,
  type ModelInfo,
  type Job,
  type CreateCorpusInput,
} from '../lib/api.ts'

type IngestSubTab = 'urls' | 'manifest' | 'files'

interface Props {
  onHome: () => void
}

// ── Feedback helpers ───────────────────────────────────────────────────────

function ErrorMsg({ message }: { message: string }) {
  return (
    <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
      {message}
    </p>
  )
}

function SuccessMsg({ message }: { message: string }) {
  return (
    <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded px-3 py-2">
      {message}
    </p>
  )
}

// ── SectionCard ───────────────────────────────────────────────────────────

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-stone-200 rounded-lg p-6 mb-4">
      <h3 className="text-base font-semibold text-stone-800 mb-4">{title}</h3>
      {children}
    </div>
  )
}

// ── CreateCorpusPanel ─────────────────────────────────────────────────────

interface CreateCorpusPanelProps {
  onCreated: (corpus: Corpus) => void
}

function CreateCorpusPanel({ onCreated }: CreateCorpusPanelProps) {
  const [profiles, setProfiles] = useState<CorpusProfile[]>([])
  const [form, setForm] = useState<CreateCorpusInput>({ slug: '', title: '', profile_id: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    listProfiles()
      .then((ps) => {
        setProfiles(ps)
        if (ps.length > 0) setForm((f) => ({ ...f, profile_id: ps[0].profile_id }))
      })
      .catch(() => {})
  }, [])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    setLoading(true)
    try {
      const corpus = await createCorpus(form)
      setSuccess(`Corpus « ${corpus.title} » créé.`)
      setForm((f) => ({ ...f, slug: '', title: '' }))
      onCreated(corpus)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue')
    } finally {
      setLoading(false)
    }
  }

  const inputClass =
    'border border-stone-300 rounded px-3 py-2 text-sm w-full focus:outline-none focus:ring-2 focus:ring-stone-400'

  return (
    <div className="max-w-lg">
      <h2 className="text-xl font-semibold text-stone-800 mb-6">Créer un corpus</h2>
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        <div>
          <label className="block text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">
            Slug{' '}
            <span className="text-stone-400 font-normal normal-case">(identifiant unique, sans espaces)</span>
          </label>
          <input
            type="text"
            value={form.slug}
            onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
            required
            placeholder="ex. beatus-lat8878"
            className={inputClass}
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">
            Titre
          </label>
          <input
            type="text"
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            required
            placeholder="ex. Beatus de Saint-Sever"
            className={inputClass}
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">
            Profil
          </label>
          {profiles.length === 0 ? (
            <p className="text-sm text-stone-400">Chargement des profils…</p>
          ) : (
            <select
              value={form.profile_id}
              onChange={(e) => setForm((f) => ({ ...f, profile_id: e.target.value }))}
              className="border border-stone-300 rounded px-3 py-2 text-sm w-full bg-white focus:outline-none focus:ring-2 focus:ring-stone-400"
            >
              {profiles.map((p) => (
                <option key={p.profile_id} value={p.profile_id}>
                  {p.label} ({p.profile_id})
                </option>
              ))}
            </select>
          )}
        </div>
        {error && <ErrorMsg message={error} />}
        {success && <SuccessMsg message={success} />}
        <button
          type="submit"
          disabled={loading || !form.slug || !form.title || !form.profile_id}
          className="bg-stone-800 text-white px-5 py-2 rounded text-sm font-medium hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Création…' : 'Créer le corpus'}
        </button>
      </form>
    </div>
  )
}

// ── ModelPanel ────────────────────────────────────────────────────────────

interface ModelPanelProps {
  corpusId: string
  onSaved: () => void
}

function ModelPanel({ corpusId, onSaved }: ModelPanelProps) {
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [loadingProviders, setLoadingProviders] = useState(true)
  const [providersError, setProvidersError] = useState<string | null>(null)

  const [selectedProvider, setSelectedProvider] = useState<string>('')
  const [models, setModels] = useState<ModelInfo[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [modelsError, setModelsError] = useState<string | null>(null)
  const [selectedModelId, setSelectedModelId] = useState('')

  const [currentModel, setCurrentModel] = useState<CorpusModelConfig | null>(null)
  const [savingModel, setSavingModel] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null)

  // Load current model config and providers on mount
  useEffect(() => {
    void getCorpusModel(corpusId).then(setCurrentModel)
    setLoadingProviders(true)
    setProvidersError(null)
    fetchProviders()
      .then((ps) => {
        setProviders(ps)
        const first = ps.find((p) => p.available)
        if (first) setSelectedProvider(first.provider_type)
      })
      .catch((err) => {
        setProvidersError(err instanceof Error ? err.message : 'Erreur inconnue')
      })
      .finally(() => setLoadingProviders(false))
  }, [corpusId])

  // Load models when provider changes
  useEffect(() => {
    if (!selectedProvider) return
    setModels([])
    setSelectedModelId('')
    setModelsError(null)
    setLoadingModels(true)
    fetchProviderModels(selectedProvider)
      .then((ms) => {
        setModels(ms)
        if (ms.length > 0) setSelectedModelId(ms[0].model_id)
      })
      .catch((err) => {
        setModelsError(err instanceof Error ? err.message : 'Erreur inconnue')
      })
      .finally(() => setLoadingModels(false))
  }, [selectedProvider])

  const handleSelectModel = async (e: FormEvent) => {
    e.preventDefault()
    setSaveError(null)
    setSaveSuccess(null)
    setSavingModel(true)
    const model = models.find((m) => m.model_id === selectedModelId)
    try {
      await selectModel(corpusId, selectedModelId, model?.display_name ?? selectedModelId, selectedProvider)
      const updated = await getCorpusModel(corpusId)
      setCurrentModel(updated)
      setSaveSuccess(`Modèle « ${model?.display_name ?? selectedModelId} » associé au corpus.`)
      onSaved()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Erreur inconnue')
    } finally {
      setSavingModel(false)
    }
  }

  const availableProviders = providers.filter((p) => p.available)

  return (
    <>
      {currentModel && (
        <div className="mb-4 text-sm bg-stone-50 border border-stone-200 rounded px-3 py-2 text-stone-600">
          Modèle actuel :{' '}
          <span className="font-medium text-stone-800">{currentModel.selected_model_display_name}</span>
          {' '}({currentModel.provider_type})
        </div>
      )}

      {loadingProviders && (
        <p className="text-sm text-stone-400">Détection des providers disponibles…</p>
      )}
      {!loadingProviders && providersError && <ErrorMsg message={providersError} />}
      {!loadingProviders && providers.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-2">
            Providers IA détectés
          </p>
          <div className="flex flex-wrap gap-2">
            {providers.map((p) => (
              <span
                key={p.provider_type}
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${
                  p.available
                    ? 'bg-green-50 border-green-200 text-green-800 cursor-pointer hover:bg-green-100'
                    : 'bg-stone-50 border-stone-200 text-stone-400 cursor-default'
                } ${selectedProvider === p.provider_type ? 'ring-2 ring-stone-500' : ''}`}
                onClick={() => p.available && setSelectedProvider(p.provider_type)}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${p.available ? 'bg-green-500' : 'bg-stone-300'}`} />
                {p.display_name}
                {p.available && <span className="text-green-600">({p.model_count})</span>}
                {!p.available && <span className="text-stone-400">— clé manquante</span>}
              </span>
            ))}
          </div>
          {availableProviders.length === 0 && (
            <p className="text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded px-3 py-2 mt-3">
              Aucun provider disponible. Vérifiez les secrets{' '}
              <code className="font-mono">GOOGLE_AI_STUDIO_API_KEY</code>,{' '}
              <code className="font-mono">VERTEX_API_KEY</code> ou{' '}
              <code className="font-mono">MISTRAL_API_KEY</code>.
            </p>
          )}
        </div>
      )}

      {selectedProvider && (
        <form onSubmit={(e) => void handleSelectModel(e)} className="space-y-3 max-w-sm">
          {loadingModels && <p className="text-sm text-stone-400">Chargement des modèles…</p>}
          {!loadingModels && modelsError && <ErrorMsg message={modelsError} />}
          {!loadingModels && models.length > 0 && (
            <div>
              <label className="block text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">
                Modèle — {providers.find((p) => p.provider_type === selectedProvider)?.display_name}
              </label>
              <select
                value={selectedModelId}
                onChange={(e) => setSelectedModelId(e.target.value)}
                className="border border-stone-300 rounded px-3 py-2 text-sm w-full bg-white focus:outline-none focus:ring-2 focus:ring-stone-400"
              >
                {models.map((m) => (
                  <option key={m.model_id} value={m.model_id}>
                    {m.display_name}{m.supports_vision ? ' (vision)' : ''}
                  </option>
                ))}
              </select>
            </div>
          )}
          {saveError && <ErrorMsg message={saveError} />}
          {saveSuccess && <SuccessMsg message={saveSuccess} />}
          {!loadingModels && models.length > 0 && (
            <button
              type="submit"
              disabled={savingModel || !selectedModelId}
              className="bg-stone-800 text-white px-5 py-2 rounded text-sm font-medium hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {savingModel ? 'Enregistrement…' : 'Sélectionner ce modèle'}
            </button>
          )}
        </form>
      )}
    </>
  )
}

// ── IngestPanel ───────────────────────────────────────────────────────────

interface IngestPanelProps {
  corpusId: string
}

function IngestPanel({ corpusId }: IngestPanelProps) {
  const [subTab, setSubTab] = useState<IngestSubTab>('urls')

  const [urlsText, setUrlsText] = useState('')
  const [folioLabelsText, setFolioLabelsText] = useState('')
  const [urlsLoading, setUrlsLoading] = useState(false)
  const [urlsError, setUrlsError] = useState<string | null>(null)
  const [urlsSuccess, setUrlsSuccess] = useState<string | null>(null)

  const [manifestUrl, setManifestUrl] = useState('')
  const [manifestLoading, setManifestLoading] = useState(false)
  const [manifestError, setManifestError] = useState<string | null>(null)
  const [manifestSuccess, setManifestSuccess] = useState<string | null>(null)

  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [filesLoading, setFilesLoading] = useState(false)
  const [filesError, setFilesError] = useState<string | null>(null)
  const [filesSuccess, setFilesSuccess] = useState<string | null>(null)

  const handleUrlsSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setUrlsError(null)
    setUrlsSuccess(null)
    const urls = urlsText.split('\n').map((l) => l.trim()).filter(Boolean)
    const labels = folioLabelsText.split('\n').map((l) => l.trim()).filter(Boolean)
    if (urls.length === 0) { setUrlsError('Aucune URL renseignée.'); return }
    if (labels.length !== urls.length) {
      setUrlsError(`Le nombre de folio_labels (${labels.length}) doit être égal au nombre d'URLs (${urls.length}).`)
      return
    }
    setUrlsLoading(true)
    try {
      const resp = await ingestImages(corpusId, urls, labels)
      setUrlsSuccess(`${resp.pages_created} page(s) ingérée(s).`)
      setUrlsText('')
      setFolioLabelsText('')
    } catch (err) {
      setUrlsError(err instanceof Error ? err.message : 'Erreur inconnue')
    } finally {
      setUrlsLoading(false)
    }
  }

  const handleManifestSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setManifestError(null)
    setManifestSuccess(null)
    setManifestLoading(true)
    try {
      const resp = await ingestManifest(corpusId, manifestUrl)
      setManifestSuccess(`${resp.pages_created} page(s) ingérée(s) depuis le manifest.`)
      setManifestUrl('')
    } catch (err) {
      setManifestError(err instanceof Error ? err.message : 'Erreur inconnue')
    } finally {
      setManifestLoading(false)
    }
  }

  const handleFilesSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setFilesError(null)
    setFilesSuccess(null)
    if (selectedFiles.length === 0) { setFilesError('Aucun fichier sélectionné.'); return }
    setFilesLoading(true)
    try {
      const resp = await ingestFiles(corpusId, selectedFiles)
      setFilesSuccess(`${resp.pages_created} page(s) ingérée(s).`)
      setSelectedFiles([])
    } catch (err) {
      setFilesError(err instanceof Error ? err.message : 'Erreur inconnue')
    } finally {
      setFilesLoading(false)
    }
  }

  const subTabClass = (tab: IngestSubTab) =>
    `px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
      subTab === tab
        ? 'border-stone-800 text-stone-900'
        : 'border-transparent text-stone-500 hover:text-stone-700'
    }`

  const textareaClass =
    'border border-stone-300 rounded px-3 py-2 text-sm w-full font-mono focus:outline-none focus:ring-2 focus:ring-stone-400'
  const submitBtnClass =
    'bg-stone-800 text-white px-5 py-2 rounded text-sm font-medium hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors'

  return (
    <>
      <div className="flex border-b border-stone-200 mb-4 -mt-1">
        <button className={subTabClass('urls')} onClick={() => setSubTab('urls')}>URLs directes</button>
        <button className={subTabClass('manifest')} onClick={() => setSubTab('manifest')}>Manifest IIIF</button>
        <button className={subTabClass('files')} onClick={() => setSubTab('files')}>Fichiers locaux</button>
      </div>

      {subTab === 'urls' && (
        <form onSubmit={(e) => void handleUrlsSubmit(e)} className="space-y-3 max-w-lg">
          <div>
            <label className="block text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">
              URLs d'images <span className="font-normal normal-case text-stone-400">(1 par ligne)</span>
            </label>
            <textarea
              value={urlsText}
              onChange={(e) => setUrlsText(e.target.value)}
              rows={4}
              placeholder="https://gallica.bnf.fr/iiif/ark:/…/f1/full/max/0/native.jpg"
              className={textareaClass}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">
              Folio labels <span className="font-normal normal-case text-stone-400">(1 par ligne, même ordre)</span>
            </label>
            <textarea
              value={folioLabelsText}
              onChange={(e) => setFolioLabelsText(e.target.value)}
              rows={4}
              placeholder={'001r\n001v\n002r'}
              className={textareaClass}
            />
          </div>
          {urlsError && <ErrorMsg message={urlsError} />}
          {urlsSuccess && <SuccessMsg message={urlsSuccess} />}
          <button type="submit" disabled={urlsLoading} className={submitBtnClass}>
            {urlsLoading ? 'Ingestion…' : 'Ingérer les images'}
          </button>
        </form>
      )}

      {subTab === 'manifest' && (
        <form onSubmit={(e) => void handleManifestSubmit(e)} className="space-y-3 max-w-lg">
          <div>
            <label className="block text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">
              URL du manifest IIIF
            </label>
            <input
              type="url"
              value={manifestUrl}
              onChange={(e) => setManifestUrl(e.target.value)}
              required
              placeholder="https://gallica.bnf.fr/iiif/ark:/…/manifest.json"
              className="border border-stone-300 rounded px-3 py-2 text-sm w-full font-mono focus:outline-none focus:ring-2 focus:ring-stone-400"
            />
          </div>
          {manifestError && <ErrorMsg message={manifestError} />}
          {manifestSuccess && <SuccessMsg message={manifestSuccess} />}
          <button type="submit" disabled={manifestLoading || !manifestUrl} className={submitBtnClass}>
            {manifestLoading ? 'Ingestion…' : 'Importer le manifest'}
          </button>
        </form>
      )}

      {subTab === 'files' && (
        <form onSubmit={(e) => void handleFilesSubmit(e)} className="space-y-3 max-w-lg">
          <div>
            <label className="block text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">
              Fichiers images
            </label>
            <input
              type="file"
              multiple
              accept="image/*"
              onChange={(e) => setSelectedFiles(Array.from(e.target.files ?? []))}
              className="block text-sm text-stone-600 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-medium file:bg-stone-100 file:text-stone-700 hover:file:bg-stone-200"
            />
            {selectedFiles.length > 0 && (
              <p className="text-xs text-stone-500 mt-1">{selectedFiles.length} fichier(s) sélectionné(s)</p>
            )}
          </div>
          {filesError && <ErrorMsg message={filesError} />}
          {filesSuccess && <SuccessMsg message={filesSuccess} />}
          <button type="submit" disabled={filesLoading || selectedFiles.length === 0} className={submitBtnClass}>
            {filesLoading ? 'Envoi…' : 'Envoyer les fichiers'}
          </button>
        </form>
      )}
    </>
  )
}

// ── RunPanel ──────────────────────────────────────────────────────────────

interface RunPanelProps {
  corpusId: string
  hasModel: boolean
}

function RunPanel({ corpusId, hasModel }: RunPanelProps) {
  const [pageCount, setPageCount] = useState<number | null>(null)
  const [launching, setLaunching] = useState(false)
  const [launchError, setLaunchError] = useState<string | null>(null)
  const [jobIds, setJobIds] = useState<string[]>([])
  const [jobs, setJobs] = useState<Record<string, Job>>({})
  const [polling, setPolling] = useState(false)

  // Fetch page count from manuscripts + pages
  useEffect(() => {
    fetchManuscripts(corpusId)
      .then(async (manuscripts) => {
        if (manuscripts.length === 0) { setPageCount(0); return }
        const pagesArrays = await Promise.all(manuscripts.map((m) => fetchPages(m.id)))
        setPageCount(pagesArrays.reduce((sum, ps) => sum + ps.length, 0))
      })
      .catch(() => setPageCount(null))
  }, [corpusId])

  useEffect(() => {
    if (!polling || jobIds.length === 0) return
    const poll = async () => {
      try {
        const results = await Promise.all(jobIds.map((id) => getJob(id)))
        const map: Record<string, Job> = {}
        for (const job of results) map[job.id] = job
        setJobs(map)
        if (results.every((j) => j.status === 'done' || j.status === 'failed')) setPolling(false)
      } catch {
        // Erreur réseau transitoire — on continue
      }
    }
    const id = setInterval(() => void poll(), 3000)
    return () => clearInterval(id)
  }, [polling, jobIds])

  const handleRun = async () => {
    setLaunchError(null)
    setJobIds([])
    setJobs({})
    setLaunching(true)
    try {
      const resp = await runCorpus(corpusId)
      setJobIds(resp.job_ids)
      setPolling(true)
    } catch (err) {
      setLaunchError(err instanceof Error ? err.message : 'Erreur inconnue')
    } finally {
      setLaunching(false)
    }
  }

  const handleRetryFailed = async () => {
    const failedIds = Object.values(jobs).filter((j) => j.status === 'failed').map((j) => j.id)
    if (failedIds.length === 0) return
    await Promise.allSettled(failedIds.map((id) => retryJob(id)))
    setPolling(true)
  }

  const jobList = Object.values(jobs)
  const doneCount = jobList.filter((j) => j.status === 'done').length
  const failedCount = jobList.filter((j) => j.status === 'failed').length
  const totalCount = jobList.length

  const statusBadge = (status: string) => {
    const classes: Record<string, string> = {
      pending: 'bg-stone-100 text-stone-600',
      running: 'bg-blue-100 text-blue-700',
      done: 'bg-green-100 text-green-700',
      failed: 'bg-red-100 text-red-700',
    }
    return (
      <span className={`text-xs px-2 py-0.5 rounded font-medium ${classes[status] ?? 'bg-stone-100 text-stone-500'}`}>
        {status}
      </span>
    )
  }

  if (!hasModel) {
    return (
      <p className="text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded px-3 py-2">
        Configurez d'abord un modèle IA pour ce corpus.
      </p>
    )
  }

  return (
    <div className="space-y-4">
      {pageCount !== null && (
        <p className="text-sm text-stone-600">
          {pageCount === 0
            ? 'Aucune page ingérée.'
            : `${pageCount} page(s) dans ce corpus.`}
        </p>
      )}

      {launchError && <ErrorMsg message={launchError} />}

      <div className="flex flex-wrap gap-3 items-center">
        <button
          onClick={() => void handleRun()}
          disabled={launching || polling || pageCount === 0}
          className="bg-stone-800 text-white px-5 py-2 rounded text-sm font-medium hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {launching ? 'Démarrage…' : polling ? 'Traitement en cours…' : 'Analyser tout le corpus'}
        </button>

        {failedCount > 0 && !polling && (
          <button
            onClick={() => void handleRetryFailed()}
            className="border border-stone-300 text-stone-700 px-5 py-2 rounded text-sm font-medium hover:bg-stone-50 transition-colors"
          >
            Relancer {failedCount} page(s) en erreur
          </button>
        )}
      </div>

      {totalCount > 0 && (
        <div>
          <p className="text-sm text-stone-600 mb-3">
            Progression : <strong>{doneCount}</strong> / {totalCount} pages traitées
            {failedCount > 0 && <span className="text-red-600 ml-2">· {failedCount} en erreur</span>}
            {polling && <span className="text-blue-600 ml-2">· actualisation toutes les 3 s</span>}
          </p>
          <ul className="space-y-1 max-h-64 overflow-y-auto border border-stone-200 rounded p-2 bg-white">
            {jobList.map((job) => (
              <li
                key={job.id}
                className="flex items-center justify-between text-xs text-stone-600 py-1 px-2 rounded hover:bg-stone-50"
              >
                <span className="font-mono truncate max-w-xs">{job.page_id ?? job.id}</span>
                <div className="flex items-center gap-2 ml-2 shrink-0">
                  {statusBadge(job.status)}
                  {job.error_message && (
                    <span className="text-red-500 truncate max-w-xs" title={job.error_message}>
                      {job.error_message}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── CorpusDetail ──────────────────────────────────────────────────────────

interface CorpusDetailProps {
  corpus: Corpus
  onDeleted: () => void
}

function CorpusDetail({ corpus, onDeleted }: CorpusDetailProps) {
  const [hasModel, setHasModel] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    getCorpusModel(corpus.id)
      .then((m) => setHasModel(m !== null))
      .catch(() => {})
  }, [corpus.id])

  const handleDelete = async () => {
    setDeleteError(null)
    setDeleting(true)
    try {
      await deleteCorpus(corpus.id)
      onDeleted()
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Erreur inconnue')
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  return (
    <div>
      {/* Corpus header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-stone-800">{corpus.title}</h2>
          <p className="text-sm text-stone-500 mt-0.5">
            <span className="font-mono">{corpus.slug}</span>
            {' · '}
            <span>{corpus.profile_id}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {deleteError && <span className="text-xs text-red-600">{deleteError}</span>}
          {confirmDelete ? (
            <>
              <span className="text-xs text-stone-600">Confirmer la suppression ?</span>
              <button
                onClick={() => void handleDelete()}
                disabled={deleting}
                className="px-3 py-1.5 bg-red-600 text-white text-xs rounded font-medium hover:bg-red-700 disabled:opacity-50 transition-colors"
              >
                {deleting ? 'Suppression…' : 'Supprimer'}
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="px-3 py-1.5 border border-stone-300 text-stone-600 text-xs rounded font-medium hover:bg-stone-50 transition-colors"
              >
                Annuler
              </button>
            </>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              className="px-3 py-1.5 border border-red-200 text-red-600 text-xs rounded font-medium hover:bg-red-50 transition-colors"
            >
              Supprimer
            </button>
          )}
        </div>
      </div>

      {/* Section cards */}
      <SectionCard title="Modèle IA">
        <ModelPanel
          key={corpus.id}
          corpusId={corpus.id}
          onSaved={() => setHasModel(true)}
        />
      </SectionCard>

      <SectionCard title="Ingestion">
        <IngestPanel key={corpus.id} corpusId={corpus.id} />
      </SectionCard>

      <SectionCard title="Traitement">
        <RunPanel key={corpus.id} corpusId={corpus.id} hasModel={hasModel} />
      </SectionCard>
    </div>
  )
}

// ── Admin (composant principal) ─────────────────────────────────────────────

export default function Admin({ onHome }: Props) {
  const [corpora, setCorpora] = useState<Corpus[]>([])
  const [selectedCorpusId, setSelectedCorpusId] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const didInit = useRef(false)

  const refreshCorpora = (selectId?: string) => {
    fetchCorpora()
      .then((cs) => {
        setCorpora(cs)
        if (selectId) {
          setSelectedCorpusId(selectId)
          setShowCreate(false)
        } else if (!didInit.current) {
          didInit.current = true
          if (cs.length > 0) {
            setSelectedCorpusId(cs[0].id)
            setShowCreate(false)
          } else {
            setShowCreate(true)
          }
        }
      })
      .catch(() => {})
  }

  useEffect(() => {
    refreshCorpora()
  }, [])

  const selectedCorpus = corpora.find((c) => c.id === selectedCorpusId) ?? null

  return (
    <div className="h-screen flex flex-col bg-stone-50">
      {/* Top bar */}
      <header className="bg-stone-900 text-stone-100 px-6 py-4 flex items-center gap-4 shrink-0">
        <button
          onClick={onHome}
          className="text-stone-400 hover:text-stone-100 text-sm transition-colors"
        >
          ← Accueil
        </button>
        <h1 className="text-xl font-semibold tracking-tight">Administration</h1>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 bg-white border-r border-stone-200 flex flex-col shrink-0 overflow-y-auto">
          <div className="p-3 border-b border-stone-100">
            <button
              onClick={() => { setShowCreate(true); setSelectedCorpusId(null) }}
              className={`w-full text-left px-3 py-2 rounded text-sm font-medium transition-colors ${
                showCreate && !selectedCorpusId
                  ? 'bg-stone-800 text-white'
                  : 'text-stone-600 hover:bg-stone-100'
              }`}
            >
              + Nouveau corpus
            </button>
          </div>
          <nav className="flex-1 p-3 space-y-0.5">
            {corpora.length === 0 && (
              <p className="text-xs text-stone-400 px-3 py-2">Aucun corpus</p>
            )}
            {corpora.map((c) => (
              <button
                key={c.id}
                onClick={() => { setSelectedCorpusId(c.id); setShowCreate(false) }}
                className={`w-full text-left px-3 py-2 rounded text-sm transition-colors ${
                  selectedCorpusId === c.id && !showCreate
                    ? 'bg-stone-100 text-stone-900 font-medium'
                    : 'text-stone-600 hover:bg-stone-50'
                }`}
              >
                <span className="block truncate">{c.title}</span>
                <span className="block truncate text-xs text-stone-400 font-mono">{c.slug}</span>
              </button>
            ))}
          </nav>
        </aside>

        {/* Main panel */}
        <main className="flex-1 overflow-y-auto p-8">
          {showCreate && !selectedCorpusId && (
            <CreateCorpusPanel
              onCreated={(corpus) => {
                refreshCorpora(corpus.id)
              }}
            />
          )}
          {!showCreate && selectedCorpus && (
            <CorpusDetail
              key={selectedCorpus.id}
              corpus={selectedCorpus}
              onDeleted={() => {
                const remaining = corpora.filter((c) => c.id !== selectedCorpus.id)
                setCorpora(remaining)
                if (remaining.length > 0) {
                  setSelectedCorpusId(remaining[0].id)
                  setShowCreate(false)
                } else {
                  setSelectedCorpusId(null)
                  setShowCreate(true)
                }
              }}
            />
          )}
          {!showCreate && !selectedCorpus && corpora.length > 0 && (
            <p className="text-sm text-stone-400">Sélectionnez un corpus dans la barre latérale.</p>
          )}
        </main>
      </div>
    </div>
  )
}
