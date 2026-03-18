import { type FormEvent, useEffect, useState } from 'react'
import {
  fetchCorpora,
  listProfiles,
  createCorpus,
  listModels,
  selectModel,
  ingestImages,
  ingestManifest,
  ingestFiles,
  runCorpus,
  getJob,
  retryJob,
  type Corpus,
  type CorpusProfile,
  type ModelInfo,
  type Job,
  type CreateCorpusInput,
} from '../lib/api.ts'

type AdminTab = 'corpus' | 'model' | 'ingest' | 'run'
type IngestSubTab = 'urls' | 'manifest' | 'files'

interface Props {
  onHome: () => void
}

// ── CorpusSelector ─────────────────────────────────────────────────────────

interface CorpusSelectorProps {
  corpora: Corpus[]
  value: string
  onChange: (id: string) => void
}

function CorpusSelector({ corpora, value, onChange }: CorpusSelectorProps) {
  if (corpora.length === 0) {
    return (
      <p className="text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-6">
        Aucun corpus. Créez-en un dans l'onglet « Nouveau corpus ».
      </p>
    )
  }
  return (
    <div className="mb-6">
      <label className="block text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">
        Corpus cible
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="border border-stone-300 rounded px-3 py-2 text-sm w-full max-w-sm bg-white focus:outline-none focus:ring-2 focus:ring-stone-400"
      >
        {corpora.map((c) => (
          <option key={c.id} value={c.id}>
            {c.title} ({c.slug})
          </option>
        ))}
      </select>
    </div>
  )
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

// ── Section 1 — Créer un corpus ─────────────────────────────────────────────

interface CreateCorpusSectionProps {
  onCreated: (corpus: Corpus) => void
}

function CreateCorpusSection({ onCreated }: CreateCorpusSectionProps) {
  const [profiles, setProfiles] = useState<CorpusProfile[]>([])
  const [form, setForm] = useState<CreateCorpusInput>({
    slug: '',
    title: '',
    profile_id: '',
  })
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
      setSuccess(`Corpus « ${corpus.title} » créé (id : ${corpus.id})`)
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
    <section>
      <h2 className="text-lg font-semibold text-stone-800 mb-6">Créer un corpus</h2>
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 max-w-md">
        <div>
          <label className="block text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">
            Slug{' '}
            <span className="text-stone-400 font-normal normal-case">
              (identifiant unique, sans espaces)
            </span>
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
    </section>
  )
}

// ── Section 2 — Configurer le modèle IA ────────────────────────────────────

interface ModelSectionProps {
  corpora: Corpus[]
  selectedCorpusId: string
  onSelectCorpus: (id: string) => void
}

function ModelSection({ corpora, selectedCorpusId, onSelectCorpus }: ModelSectionProps) {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [loadingModels, setLoadingModels] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedModelId, setSelectedModelId] = useState('')
  const [savingModel, setSavingModel] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null)

  useEffect(() => {
    setLoadingModels(true)
    setLoadError(null)
    listModels()
      .then((ms) => {
        setModels(ms)
        if (ms.length > 0) setSelectedModelId(ms[0].model_id)
      })
      .catch((err) => {
        setLoadError(err instanceof Error ? err.message : 'Erreur inconnue')
      })
      .finally(() => setLoadingModels(false))
  }, [])

  const handleSelectModel = async (e: FormEvent) => {
    e.preventDefault()
    setSaveError(null)
    setSaveSuccess(null)
    setSavingModel(true)
    const model = models.find((m) => m.model_id === selectedModelId)
    try {
      await selectModel(
        selectedCorpusId,
        selectedModelId,
        model?.display_name ?? selectedModelId,
        model?.provider ?? 'google_ai_studio',
      )
      setSaveSuccess(
        `Modèle « ${model?.display_name ?? selectedModelId} » associé au corpus.`,
      )
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Erreur inconnue')
    } finally {
      setSavingModel(false)
    }
  }

  return (
    <section>
      <h2 className="text-lg font-semibold text-stone-800 mb-6">Configurer le modèle IA</h2>
      <CorpusSelector corpora={corpora} value={selectedCorpusId} onChange={onSelectCorpus} />

      {loadingModels && (
        <p className="text-sm text-stone-400">Chargement des modèles disponibles…</p>
      )}

      {!loadingModels && loadError && (
        <ErrorMsg message={loadError} />
      )}

      {!loadingModels && !loadError && models.length === 0 && (
        <p className="text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded px-3 py-2">
          Aucun modèle détecté. Vérifiez que les secrets{' '}
          <code className="font-mono">AI_PROVIDER</code> et{' '}
          <code className="font-mono">VERTEX_API_KEY</code> (ou{' '}
          <code className="font-mono">GOOGLE_AI_STUDIO_API_KEY</code>) sont bien configurés
          dans les secrets HuggingFace.
        </p>
      )}

      {!loadingModels && models.length > 0 && (
        <form onSubmit={(e) => void handleSelectModel(e)} className="space-y-4 max-w-md">
          <div>
            <label className="block text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">
              Modèle disponible
            </label>
            <select
              value={selectedModelId}
              onChange={(e) => setSelectedModelId(e.target.value)}
              className="border border-stone-300 rounded px-3 py-2 text-sm w-full bg-white focus:outline-none focus:ring-2 focus:ring-stone-400"
            >
              {models.map((m) => (
                <option key={m.model_id} value={m.model_id}>
                  {m.display_name} — {m.provider}
                  {m.supports_vision ? ' (vision)' : ''}
                </option>
              ))}
            </select>
          </div>
          {saveError && <ErrorMsg message={saveError} />}
          {saveSuccess && <SuccessMsg message={saveSuccess} />}
          <button
            type="submit"
            disabled={savingModel || !selectedCorpusId || !selectedModelId}
            className="bg-stone-800 text-white px-5 py-2 rounded text-sm font-medium hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {savingModel ? 'Enregistrement…' : 'Sélectionner ce modèle'}
          </button>
        </form>
      )}
    </section>
  )
}

// ── Section 3 — Ingestion ──────────────────────────────────────────────────

interface IngestSectionProps {
  corpora: Corpus[]
  selectedCorpusId: string
  onSelectCorpus: (id: string) => void
}

function IngestSection({ corpora, selectedCorpusId, onSelectCorpus }: IngestSectionProps) {
  const [subTab, setSubTab] = useState<IngestSubTab>('urls')

  // URLs tab
  const [urlsText, setUrlsText] = useState('')
  const [folioLabelsText, setFolioLabelsText] = useState('')
  const [urlsLoading, setUrlsLoading] = useState(false)
  const [urlsError, setUrlsError] = useState<string | null>(null)
  const [urlsSuccess, setUrlsSuccess] = useState<string | null>(null)

  // Manifest tab
  const [manifestUrl, setManifestUrl] = useState('')
  const [manifestLoading, setManifestLoading] = useState(false)
  const [manifestError, setManifestError] = useState<string | null>(null)
  const [manifestSuccess, setManifestSuccess] = useState<string | null>(null)

  // Files tab
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
    if (urls.length === 0) {
      setUrlsError('Aucune URL renseignée.')
      return
    }
    if (labels.length !== urls.length) {
      setUrlsError(
        `Le nombre de folio_labels (${labels.length}) doit être égal au nombre d'URLs (${urls.length}).`,
      )
      return
    }
    setUrlsLoading(true)
    try {
      const resp = await ingestImages(selectedCorpusId, urls, labels)
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
      const resp = await ingestManifest(selectedCorpusId, manifestUrl)
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
    if (selectedFiles.length === 0) {
      setFilesError('Aucun fichier sélectionné.')
      return
    }
    setFilesLoading(true)
    try {
      const resp = await ingestFiles(selectedCorpusId, selectedFiles)
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
    <section>
      <h2 className="text-lg font-semibold text-stone-800 mb-6">Ingérer des images</h2>
      <CorpusSelector corpora={corpora} value={selectedCorpusId} onChange={onSelectCorpus} />

      {/* Sub-tabs */}
      <div className="flex border-b border-stone-200 mb-6">
        <button className={subTabClass('urls')} onClick={() => setSubTab('urls')}>
          URLs directes
        </button>
        <button className={subTabClass('manifest')} onClick={() => setSubTab('manifest')}>
          Manifest IIIF
        </button>
        <button className={subTabClass('files')} onClick={() => setSubTab('files')}>
          Fichiers locaux
        </button>
      </div>

      {/* URLs tab */}
      {subTab === 'urls' && (
        <form onSubmit={(e) => void handleUrlsSubmit(e)} className="space-y-4 max-w-lg">
          <div>
            <label className="block text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">
              URLs d'images{' '}
              <span className="font-normal normal-case text-stone-400">(1 par ligne)</span>
            </label>
            <textarea
              value={urlsText}
              onChange={(e) => setUrlsText(e.target.value)}
              rows={5}
              placeholder="https://gallica.bnf.fr/iiif/ark:/…/f1/full/max/0/native.jpg"
              className={textareaClass}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-stone-500 uppercase tracking-wide mb-1">
              Folio labels{' '}
              <span className="font-normal normal-case text-stone-400">(1 par ligne, même ordre)</span>
            </label>
            <textarea
              value={folioLabelsText}
              onChange={(e) => setFolioLabelsText(e.target.value)}
              rows={5}
              placeholder={'001r\n001v\n002r'}
              className={textareaClass}
            />
          </div>
          {urlsError && <ErrorMsg message={urlsError} />}
          {urlsSuccess && <SuccessMsg message={urlsSuccess} />}
          <button type="submit" disabled={urlsLoading || !selectedCorpusId} className={submitBtnClass}>
            {urlsLoading ? 'Ingestion…' : 'Ingérer les images'}
          </button>
        </form>
      )}

      {/* Manifest tab */}
      {subTab === 'manifest' && (
        <form onSubmit={(e) => void handleManifestSubmit(e)} className="space-y-4 max-w-lg">
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
          <button
            type="submit"
            disabled={manifestLoading || !selectedCorpusId || !manifestUrl}
            className={submitBtnClass}
          >
            {manifestLoading ? 'Ingestion…' : 'Importer le manifest'}
          </button>
        </form>
      )}

      {/* Files tab */}
      {subTab === 'files' && (
        <form onSubmit={(e) => void handleFilesSubmit(e)} className="space-y-4 max-w-lg">
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
              <p className="text-xs text-stone-500 mt-1">
                {selectedFiles.length} fichier(s) sélectionné(s)
              </p>
            )}
          </div>
          {filesError && <ErrorMsg message={filesError} />}
          {filesSuccess && <SuccessMsg message={filesSuccess} />}
          <button
            type="submit"
            disabled={filesLoading || !selectedCorpusId || selectedFiles.length === 0}
            className={submitBtnClass}
          >
            {filesLoading ? 'Envoi…' : 'Envoyer les fichiers'}
          </button>
        </form>
      )}
    </section>
  )
}

// ── Section 4 — Lancer le traitement ────────────────────────────────────────

interface RunSectionProps {
  corpora: Corpus[]
  selectedCorpusId: string
  onSelectCorpus: (id: string) => void
}

function RunSection({ corpora, selectedCorpusId, onSelectCorpus }: RunSectionProps) {
  const [launching, setLaunching] = useState(false)
  const [launchError, setLaunchError] = useState<string | null>(null)
  const [jobIds, setJobIds] = useState<string[]>([])
  const [jobs, setJobs] = useState<Record<string, Job>>({})
  const [polling, setPolling] = useState(false)

  useEffect(() => {
    if (!polling || jobIds.length === 0) return

    const poll = async () => {
      try {
        const results = await Promise.all(jobIds.map((id) => getJob(id)))
        const map: Record<string, Job> = {}
        for (const job of results) map[job.id] = job
        setJobs(map)
        const allTerminal = results.every(
          (j) => j.status === 'done' || j.status === 'failed',
        )
        if (allTerminal) setPolling(false)
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
      const resp = await runCorpus(selectedCorpusId)
      setJobIds(resp.job_ids)
      setPolling(true)
    } catch (err) {
      setLaunchError(err instanceof Error ? err.message : 'Erreur inconnue')
    } finally {
      setLaunching(false)
    }
  }

  const handleRetryFailed = async () => {
    const failedIds = Object.values(jobs)
      .filter((j) => j.status === 'failed')
      .map((j) => j.id)
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
      <span
        className={`text-xs px-2 py-0.5 rounded font-medium ${classes[status] ?? 'bg-stone-100 text-stone-500'}`}
      >
        {status}
      </span>
    )
  }

  return (
    <section>
      <h2 className="text-lg font-semibold text-stone-800 mb-6">Lancer le traitement</h2>
      <CorpusSelector corpora={corpora} value={selectedCorpusId} onChange={onSelectCorpus} />

      <div className="space-y-4">
        {launchError && <ErrorMsg message={launchError} />}

        <div className="flex flex-wrap gap-3 items-center">
          <button
            onClick={() => void handleRun()}
            disabled={launching || !selectedCorpusId || polling}
            className="bg-stone-800 text-white px-5 py-2 rounded text-sm font-medium hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {launching
              ? 'Démarrage…'
              : polling
                ? 'Traitement en cours…'
                : 'Analyser tout le corpus'}
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
              {failedCount > 0 && (
                <span className="text-red-600 ml-2">· {failedCount} en erreur</span>
              )}
              {polling && (
                <span className="text-blue-600 ml-2">· actualisation toutes les 3 s</span>
              )}
            </p>

            <ul className="space-y-1 max-h-80 overflow-y-auto border border-stone-200 rounded p-2 bg-white">
              {jobList.map((job) => (
                <li
                  key={job.id}
                  className="flex items-center justify-between text-xs text-stone-600 py-1 px-2 rounded hover:bg-stone-50"
                >
                  <span className="font-mono truncate max-w-xs">
                    {job.page_id ?? job.id}
                  </span>
                  <div className="flex items-center gap-2 ml-2 shrink-0">
                    {statusBadge(job.status)}
                    {job.error_message && (
                      <span
                        className="text-red-500 truncate max-w-xs"
                        title={job.error_message}
                      >
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
    </section>
  )
}

// ── Admin (composant principal) ─────────────────────────────────────────────

export default function Admin({ onHome }: Props) {
  const [activeTab, setActiveTab] = useState<AdminTab>('corpus')
  const [corpora, setCorpora] = useState<Corpus[]>([])
  const [selectedCorpusId, setSelectedCorpusId] = useState<string>('')

  const refreshCorpora = () => {
    fetchCorpora()
      .then((cs) => {
        setCorpora(cs)
        setSelectedCorpusId((prev) => prev || (cs.length > 0 ? cs[0].id : ''))
      })
      .catch(() => {})
  }

  useEffect(() => {
    refreshCorpora()
  }, [])

  const tabClass = (tab: AdminTab) =>
    `px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
      activeTab === tab
        ? 'border-stone-800 text-stone-900'
        : 'border-transparent text-stone-500 hover:text-stone-700'
    }`

  return (
    <div className="min-h-screen bg-stone-50">
      <header className="bg-stone-900 text-stone-100 px-8 py-4 flex items-center gap-4">
        <button
          onClick={onHome}
          className="text-stone-400 hover:text-stone-100 text-sm transition-colors"
        >
          ← Accueil
        </button>
        <h1 className="text-xl font-semibold tracking-tight">Administration</h1>
      </header>

      <nav className="bg-white border-b border-stone-200 px-8">
        <div className="flex">
          <button className={tabClass('corpus')} onClick={() => setActiveTab('corpus')}>
            Nouveau corpus
          </button>
          <button className={tabClass('model')} onClick={() => setActiveTab('model')}>
            Modèle IA
          </button>
          <button className={tabClass('ingest')} onClick={() => setActiveTab('ingest')}>
            Ingestion
          </button>
          <button className={tabClass('run')} onClick={() => setActiveTab('run')}>
            Traitement
          </button>
        </div>
      </nav>

      <main className="max-w-3xl mx-auto py-10 px-8">
        {activeTab === 'corpus' && (
          <CreateCorpusSection
            onCreated={(corpus) => {
              setCorpora((prev) => [...prev, corpus])
              setSelectedCorpusId(corpus.id)
            }}
          />
        )}
        {activeTab === 'model' && (
          <ModelSection
            corpora={corpora}
            selectedCorpusId={selectedCorpusId}
            onSelectCorpus={setSelectedCorpusId}
          />
        )}
        {activeTab === 'ingest' && (
          <IngestSection
            corpora={corpora}
            selectedCorpusId={selectedCorpusId}
            onSelectCorpus={setSelectedCorpusId}
          />
        )}
        {activeTab === 'run' && (
          <RunSection
            corpora={corpora}
            selectedCorpusId={selectedCorpusId}
            onSelectCorpus={setSelectedCorpusId}
          />
        )}
      </main>
    </div>
  )
}
