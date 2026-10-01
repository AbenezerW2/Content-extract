import { AnimatePresence, motion } from "motion/react"
import {
  Check,
  ChevronRight,
  CircleStop,
  Contrast,
  ExternalLink,
  FileText,
  FolderOpen,
  Globe2,
  History,
  Laptop,
  LoaderCircle,
  Moon,
  Play,
  ScrollText,
  Sparkles,
  Sun,
  X,
} from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import binaryBooksArt from "@/assets/binary-books.png"
import youtubeExtractionArt from "@/assets/youtube-extraction.png"
import { GlassSurface } from "@/components/ui/glass-surface"
import { GlyphMatrix } from "@/components/ui/glyph-matrix"
import {
  WebPageWorkflowIcon,
} from "@/components/workflow-icons"
import {
  MorphingDialog,
  MorphingDialogClose,
  MorphingDialogContainer,
  MorphingDialogContent,
  MorphingDialogDescription,
  MorphingDialogTitle,
  MorphingDialogTrigger,
} from "@/components/ui/morphing-dialog"
import { cn } from "@/lib/utils"

type Mode = "page" | "site" | "book" | "youtube" | "kortext"
type Workflow = "web" | "book" | "youtube" | "kortext"
type Theme = "light" | "dark" | "black" | "system"

const MAX_ACTIVITY_CHARS = 200_000
type OutputFormat = "markdown" | "json" | "text" | "html"
type HtmlMode = "clean" | "snapshot"

type ExtractionForm = {
  mode: Mode
  url: string
  name: string
  outputDir: string
  format: OutputFormat
  htmlMode: HtmlMode
  embedImages: boolean
  startChapter: number
  endChapter: number
  bookMultiple: boolean
  delay: number
  playwright: boolean
  headed: boolean
  waitForUser: boolean
  overwrite: boolean
  languages: string
  translateTo: string
  strictLanguage: boolean
  playlist: boolean
  maxVideos: number | ""
  maxPages: number | ""
}

type HistoryEntry = {
  timestamp: string
  mode: Mode
  source: string
  path: string
  label: string
}

type BridgeEvent = {
  type: "output" | "saved" | "verification" | "captured" | "finished" | "error"
  text?: string
  path?: string
  exitCode?: number
}

type BridgeStatus = {
  events: BridgeEvent[]
  cursor: number
  running: boolean
  exitCode: number | null
}

type DesktopApi = {
  choose_output_dir: (initial: string) => Promise<string | null>
  start_extraction: (payload: Record<string, unknown>) => Promise<{ ok: boolean; error?: string }>
  get_status: (cursor: number) => Promise<BridgeStatus>
  send_verification: () => Promise<{ ok: boolean }>
  stop_extraction: () => Promise<{ ok: boolean }>
  open_output_folder: (path: string) => Promise<{ ok: boolean; error?: string }>
  get_history: (mode: Mode) => Promise<HistoryEntry[]>
}

declare global {
  interface Window {
    pywebview?: { api: DesktopApi }
  }
}

const initialForm: ExtractionForm = {
  mode: "book",
  url: "",
  name: "",
  outputDir: "~/Documents/Extracted",
  format: "markdown",
  htmlMode: "clean",
  embedImages: true,
  startChapter: 1,
  endChapter: 12,
  bookMultiple: true,
  delay: 1,
  playwright: true,
  headed: true,
  waitForUser: true,
  overwrite: false,
  languages: "en, en-US, en-GB",
  translateTo: "",
  strictLanguage: false,
  playlist: false,
  maxVideos: 30,
  maxPages: 30,
}

const spring = { type: "spring" as const, stiffness: 420, damping: 34 }

const modeDetails: Record<Mode, { title: string; description: string; unit: string }> = {
  kortext: { title: "Kortext reader capture", description: "Sign in, open a PDF book, then capture pages from your current position.", unit: "pages" },
  page: { title: "Web-page extraction", description: "Capture one public page and name it from the page title by default.", unit: "page" },
  site: { title: "Whole-site extraction", description: "Follow same-site links and save up to 30 public pages.", unit: "pages" },
  book: { title: "Book extraction", description: "Extract one chapter or a numbered chapter range in one browser session.", unit: "chapters" },
  youtube: { title: "YouTube transcript extraction", description: "Use detected video titles, custom formats, or a playlist of up to 30 videos.", unit: "transcripts" },
}

function App() {
  const [form, setForm] = useState<ExtractionForm>(initialForm)
  const [theme, setTheme] = useState<Theme>(() => {
    const storedTheme = localStorage.getItem("content-extract-theme")
    return storedTheme === "light" || storedTheme === "dark" || storedTheme === "black" || storedTheme === "system"
      ? storedTheme
      : "system"
  })
  const [prefersDark, setPrefersDark] = useState(() => window.matchMedia("(prefers-color-scheme: dark)").matches)
  const [running, setRunning] = useState(false)
  const [verificationNeeded, setVerificationNeeded] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  const [savedCount, setSavedCount] = useState(0)
  const [status, setStatus] = useState("Ready to extract")
  const [error, setError] = useState("")
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const cursorRef = useRef(0)
  const isDark = theme === "dark" || theme === "black" || (theme === "system" && prefersDark)
  const isBlack = theme === "black"
  const modeDetail = form.mode === "book"
    ? form.bookMultiple
      ? { title: "Multiple-chapter extraction", description: "Extract a numbered chapter range in one browser session.", unit: "chapters" }
      : { title: "Single-chapter extraction", description: "Extract one numbered chapter into a clean local file.", unit: "chapter" }
    : modeDetails[form.mode]

  const expectedOutputs = form.mode === "book"
    ? Math.max(1, form.endChapter - form.startChapter + 1)
    : form.mode === "site" || form.mode === "kortext"
      ? form.maxPages
      : form.mode === "youtube" && form.playlist
        ? form.maxVideos
        : 1
  const safeExpectedOutputs = Math.max(1, Number(expectedOutputs) || 1)
  const unlimitedCapture = form.mode === "kortext" && Number(form.maxPages) === 0
  const progress = unlimitedCapture ? (running ? 30 : savedCount ? 100 : 0) : running || savedCount ? Math.min(100, Math.round((savedCount / safeExpectedOutputs) * 100)) : 0

  const refreshHistory = useCallback(async () => {
    if (!window.pywebview?.api) {
      setHistory([])
      return
    }
    try {
      setHistory(await window.pywebview.api.get_history(form.mode))
    } catch {
      setHistory([])
    }
  }, [form.mode])

  const consumeEvents = useCallback((events: BridgeEvent[]) => {
    const output = events
      .filter((event) => event.type === "output" && event.text)
      .map((event) => event.text)
      .join("")
    if (output) {
      setLogs((current) => {
        const combined = `${current.join("")}${output}`
        return [combined.slice(-MAX_ACTIVITY_CHARS)]
      })
    }

    for (const event of events) {
      if (event.type === "captured" || (event.type === "saved" && form.mode !== "kortext")) {
        setSavedCount((count) => count + 1)
        setStatus(form.mode === "book" ? "Extracting chapters" : form.mode === "site" ? "Crawling site pages" : form.mode === "youtube" ? "Saving transcript" : "Saving page")
      }
      if (event.type === "verification") {
        setVerificationNeeded(true)
        setStatus(form.mode === "kortext" ? "Open your book, then start capture" : "Waiting for browser verification")
      }
      if (event.type === "finished") {
        setRunning(false)
        setVerificationNeeded(false)
        if (event.exitCode === 0) {
          setSavedCount((count) => count || (safeExpectedOutputs === 1 ? 1 : 0))
          setStatus("Extraction complete")
          void refreshHistory()
        } else {
          setStatus("Extraction stopped")
          setError("The extractor did not finish. Open activity for details.")
        }
      }
      if (event.type === "error") setError(event.text || "Something went wrong.")
    }
  }, [safeExpectedOutputs, form.mode, refreshHistory])

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)")
    const updatePreference = () => setPrefersDark(media.matches)
    media.addEventListener("change", updatePreference)
    return () => media.removeEventListener("change", updatePreference)
  }, [])

  useEffect(() => {
    localStorage.setItem("content-extract-theme", theme)
    document.documentElement.classList.toggle("dark", isDark)
    document.documentElement.classList.toggle("black-theme", isBlack)
    document.documentElement.style.colorScheme = isDark ? "dark" : "light"
  }, [isBlack, isDark, theme])

  useEffect(() => {
    if (!running || !window.pywebview?.api) return
    let cancelled = false
    let timer: number | undefined

    const poll = async () => {
      try {
        const update = await window.pywebview!.api.get_status(cursorRef.current)
        if (cancelled) return
        cursorRef.current = update.cursor
        consumeEvents(update.events)
        if (!update.running && update.exitCode !== null) {
          setRunning(false)
          return
        }
      } catch (pollError) {
        if (cancelled) return
        setError(String(pollError))
        setRunning(false)
        return
      }

      // Schedule only after the current bridge call completes so a busy
      // Windows UI thread can never accumulate overlapping COM requests.
      timer = window.setTimeout(() => void poll(), 500)
    }

    timer = window.setTimeout(() => void poll(), 0)
    return () => {
      cancelled = true
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [consumeEvents, running])

  useEffect(() => {
    // History is loaded from native storage whenever the workflow changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshHistory()
  }, [refreshHistory])

  function updateForm<K extends keyof ExtractionForm>(key: K, value: ExtractionForm[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function setMode(mode: Mode) {
    if (running) return
    setForm((current) => ({
      ...current,
      mode,
      maxPages: mode === "kortext" ? 3 : 30,
      url: mode === "kortext" ? "https://app.kortext.com" : (current.mode === "page" || current.mode === "site") && (mode === "page" || mode === "site") ? current.url : "",
      name: (current.mode === "page" || current.mode === "site") && (mode === "page" || mode === "site") ? current.name : "",
      outputDir: "~/Documents/Extracted",
      format: mode === "youtube" ? "text" : current.format,
      playwright: mode === "book",
      headed: mode === "book",
      waitForUser: mode === "book",
    }))
    setError("")
    setSavedCount(0)
    setStatus("Ready to extract")
  }

  function setWorkflow(workflow: Workflow) {
    if ((workflow === "web" && (form.mode === "page" || form.mode === "site")) || workflow === form.mode) return
    setMode(workflow === "web" ? (form.mode === "site" ? "site" : "page") : workflow)
  }

  function setBookMultiple(multiple: boolean) {
    setForm((current) => ({
      ...current,
      bookMultiple: multiple,
      endChapter: multiple ? Math.max(current.endChapter, current.startChapter + 1) : current.startChapter,
    }))
    setError("")
  }

  function setBookStartChapter(chapter: number) {
    setForm((current) => ({
      ...current,
      startChapter: chapter,
      endChapter: current.bookMultiple ? current.endChapter : chapter,
    }))
  }

  function setPlaywright(checked: boolean) {
    setForm((current) => ({
      ...current,
      playwright: checked,
      headed: checked ? current.headed : false,
      waitForUser: checked ? current.waitForUser : false,
    }))
  }

  function setHeaded(checked: boolean) {
    setForm((current) => ({
      ...current,
      headed: checked,
      waitForUser: checked ? current.waitForUser : false,
    }))
  }

  function validate() {
    if (form.mode !== "youtube" && !/^https?:\/\/\S+$/i.test(form.url.trim())) return "Enter a complete public http:// or https:// URL."
    if (form.mode === "youtube" && !form.url.trim()) return "Enter a YouTube URL or video ID."
    if (form.mode === "book" && !form.name.trim()) return "Enter a book name."
    if (!form.outputDir.trim()) return "Choose an output folder."
    if (form.mode === "book" && (form.startChapter < 1 || form.endChapter < form.startChapter)) {
      return "The ending chapter must be at or after the starting chapter."
    }
    if (form.mode === "kortext" && (form.maxPages === "" || !Number.isInteger(Number(form.maxPages)) || Number(form.maxPages) < 0)) return "Enter a whole number of pages, or 0 for all pages."
    const maxPages = Number(form.maxPages)
    const maxVideos = Number(form.maxVideos)
    if (form.mode === "site" && (maxPages < 1 || maxPages > 30)) return "Choose a whole-site limit between 1 and 30 pages."
    if (form.mode === "youtube" && form.playlist && (maxVideos < 1 || maxVideos > 30)) return "Choose a playlist limit between 1 and 30 videos."
    return ""
  }

  async function startExtraction() {
    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }
    if (!window.pywebview?.api) {
      setError("Launch the desktop interface with `python app.py` to run the extractor.")
      return
    }

    setError("")
    setLogs([])
    setSavedCount(0)
    setVerificationNeeded(false)
    cursorRef.current = 0
    const result = await window.pywebview.api.start_extraction({
      mode: form.mode,
      url: form.url,
      name: form.name,
      output_dir: form.outputDir,
      output_format: form.format,
      html_mode: form.htmlMode,
      embed_images: form.embedImages,
      start_chapter: form.startChapter,
      end_chapter: form.endChapter,
      delay: form.delay,
      playwright: form.mode === "book" ? true : form.playwright,
      headed: form.headed,
      wait_for_user: form.waitForUser,
      overwrite: form.overwrite,
      languages: form.languages,
      translate_to: form.translateTo,
      strict_language: form.strictLanguage,
      playlist: form.playlist,
      max_videos: Number(form.maxVideos),
      max_pages: Number(form.maxPages),
    })
    if (!result.ok) {
      setError(result.error || "The extractor could not start.")
      return
    }
    setRunning(true)
    setStatus(form.mode === "kortext" ? "Opening Kortext browser" : form.mode === "youtube" ? (form.playlist ? "Reading playlist" : "Fetching captions") : form.mode === "site" ? "Crawling site" : form.playwright || form.mode === "book" ? "Launching browser" : "Fetching page")
  }

  async function chooseOutput() {
    if (!window.pywebview?.api) return
    const selection = await window.pywebview.api.choose_output_dir(form.outputDir)
    if (selection) updateForm("outputDir", selection)
  }

  async function confirmVerification() {
    const result = await window.pywebview?.api.send_verification()
    if (result?.ok) {
      setVerificationNeeded(false)
      setStatus(form.mode === "kortext" ? "Capturing reader pages" : "Verification confirmed")
    }
  }

  async function stopExtraction() {
    await window.pywebview?.api.stop_extraction()
    setVerificationNeeded(false)
    setStatus("Stopping extraction…")
  }

  async function openOutput() {
    if (!window.pywebview?.api) return
    const result = await window.pywebview.api.open_output_folder(form.outputDir)
    if (!result.ok) setError(result.error || "Could not open the output folder.")
  }

  return (
    <div className={cn(
      "relative min-h-screen overflow-hidden text-slate-950 transition-colors duration-500 dark:text-white",
      isBlack ? "bg-black" : "bg-white dark:bg-[#070b12]",
    )}>
      <GlyphMatrix
        glyphs="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        cellSize={18}
        mutationRate={0.04}
        interval={80}
        driftSpeed={16}
        fadeBottom={0.55}
        color={isDark ? "#ffffff" : "#000000"}
        className="fixed inset-0 z-0 h-screen w-screen opacity-55"
      />

      <main className="relative z-10 mx-auto flex min-h-screen w-full max-w-6xl flex-col px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
        <header className="mb-8 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="grid size-11 place-items-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-600/25">
              <Sparkles size={21} />
            </div>
            <div>
              <p className="text-lg font-extrabold tracking-tight">Content Extract</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Public content in. Clean knowledge out.</p>
            </div>
          </div>
          <ThemeSwitcher theme={theme} onChange={setTheme} />
        </header>

        <section className="mb-7 max-w-3xl">
          <motion.p
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-3 text-xs font-bold tracking-[0.18em] text-blue-600 uppercase dark:text-blue-400"
          >
            Local extraction workspace
          </motion.p>
          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.04 }}
            className="text-3xl leading-tight font-black tracking-[-0.035em] text-balance sm:text-4xl lg:text-5xl"
          >
            Extract pages, books, and YouTube captions.
          </motion.h1>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.12 }}
            className="mt-4 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base dark:text-slate-400"
          >
            Choose a workflow, keep human verification in your hands, and save clean local output without repeating terminal commands.
          </motion.p>
        </section>

        <ModePicker mode={form.mode} onChange={setWorkflow} />

        <GlassSurface
          width="100%"
          height="auto"
          borderRadius={28}
          borderWidth={0.06}
          brightness={68}
          blur={8}
          displace={0.45}
          distortionScale={-28}
          redOffset={0}
          greenOffset={2}
          blueOffset={4}
          backgroundOpacity={isDark ? 0.58 : 0.52}
          saturation={1.45}
          className="mt-5 border border-white/75 dark:border-white/15"
        >
        <motion.section layout transition={spring} className="w-full p-5 sm:p-7 lg:p-8">
          <div className="mb-7 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-xl font-extrabold tracking-tight">
                {modeDetail.title}
              </h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {modeDetail.description}
              </p>
            </div>
            <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-bold text-blue-700 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-300">
              {form.mode === "kortext" && Number(form.maxPages) === 0 ? "Until the last page" : `Up to ${safeExpectedOutputs} ${safeExpectedOutputs === 1 ? modeDetail.unit.replace(/s$/, "") : modeDetail.unit}`}
            </span>
          </div>

          {form.mode !== "kortext" && <WorkflowVariantTabs
            form={form}
            onWebChange={setMode}
            onBookChange={setBookMultiple}
            onYouTubeChange={(playlist) => updateForm("playlist", playlist)}
          />}

          <div className="grid min-w-0 grid-cols-1 gap-5 md:grid-cols-2">
            <Field label={form.mode === "kortext" ? "Kortext reader or sign-in URL" : form.mode === "book" ? "Book URL" : form.mode === "youtube" ? (form.playlist ? "YouTube playlist URL" : "YouTube URL or video ID") : form.mode === "site" ? "Starting site URL" : "Page URL"} className="md:col-span-2">
              <div className="relative">
                <Globe2 className="pointer-events-none absolute top-1/2 left-4 -translate-y-1/2 text-slate-400" size={17} />
                <input
                  className="control pl-11"
                  value={form.url}
                  onChange={(event) => updateForm("url", event.target.value)}
                  placeholder={form.mode === "book" ? "https://example.com/book/" : form.mode === "youtube" ? (form.playlist ? "https://youtube.com/playlist?list=..." : "https://youtube.com/watch?v=...") : form.mode === "site" ? "https://example.com/" : "https://example.com/article"}
                  spellCheck={false}
                />
              </div>
            </Field>

            <Field label={form.mode === "kortext" ? "Book name (optional)" : form.mode === "book" ? "Book name" : form.mode === "youtube" ? "Custom filename (optional)" : form.mode === "site" ? "Filename prefix (optional)" : "Custom filename (optional)"}>
              <input
                className="control"
                value={form.name}
                onChange={(event) => updateForm("name", event.target.value)}
                placeholder={form.mode === "kortext" ? "e.g. Sociology" : form.mode === "book" ? "Book Name" : form.mode === "youtube" ? "Leave blank to use video titles" : form.mode === "site" ? "Leave blank to use page titles" : "Leave blank to use the page title"}
              />
            </Field>

            <Field label="Output folder">
              <div className="flex min-w-0 gap-2">
                <input
                  className="control min-w-0 flex-1"
                  value={form.outputDir}
                  onChange={(event) => updateForm("outputDir", event.target.value)}
                  placeholder="~/Documents/Extracted"
                />
                <motion.button whileHover={{ y: -2 }} whileTap={{ scale: 0.96 }} className="icon-button" onClick={chooseOutput} title="Choose folder">
                  <FolderOpen size={18} />
                </motion.button>
              </div>
            </Field>

            {form.mode === "book" && form.bookMultiple && (
              <motion.div
                key="chapter-range"
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={spring}
                className="grid grid-cols-2 gap-3 md:col-span-2 md:max-w-md"
              >
                <Field label="Start chapter">
                  <input className="control" type="number" min={1} value={form.startChapter} onChange={(event) => setBookStartChapter(Number(event.target.value))} />
                </Field>
                <Field label="End chapter">
                  <input className="control" type="number" min={1} value={form.endChapter} onChange={(event) => updateForm("endChapter", Number(event.target.value))} />
                </Field>
              </motion.div>
            )}

            {form.mode === "book" && !form.bookMultiple && (
              <motion.div key="single-chapter" initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={spring} className="md:col-span-2 md:max-w-48">
                <Field label="Chapter number">
                  <input className="control" type="number" min={1} value={form.startChapter} onChange={(event) => setBookStartChapter(Number(event.target.value))} />
                </Field>
              </motion.div>
            )}

            {form.mode === "site" && (
              <Field label="Maximum pages (1–30)">
                <input className="control" type="number" min={1} max={30} value={form.maxPages} onChange={(event) => updateForm("maxPages", event.target.value === "" ? "" : Number(event.target.value))} />
              </Field>
            )}

            {form.mode === "youtube" && form.playlist && (
              <Field label="Maximum playlist videos (1–30)">
                <input className="control" type="number" min={1} max={30} value={form.maxVideos} onChange={(event) => updateForm("maxVideos", event.target.value === "" ? "" : Number(event.target.value))} />
              </Field>
            )}

            {form.mode === "kortext" && <>
              <Field label="Page limit (0 = all pages)">
                <input className="control" type="number" min={0} step={1} value={form.maxPages} onChange={(event) => updateForm("maxPages", event.target.value === "" ? "" : Number(event.target.value))} />
              </Field>
              <Field label="Output format"><div className="control">PNG pages + HTML gallery</div></Field>
              <p className="text-sm leading-6 text-slate-500 md:col-span-2 dark:text-slate-400">Open the browser below, sign in, and open your PDF book in the same tab. Choose single-page / fit-page view and your starting page, then return here and choose Start capture. Each run creates a new folder. Try 3 pages first; 0 continues to the last page.</p>
            </>}
            {form.mode !== "kortext" && <Field label="Output format">
              <select className="control appearance-none" value={form.format} onChange={(event) => updateForm("format", event.target.value as OutputFormat)}>
                <option value="markdown">Markdown (.md)</option>
                <option value="json">JSON (.json)</option>
                <option value="text">Plain text (.txt)</option>
                {form.mode !== "youtube" && <option value="html">Web page (.html)</option>}
              </select>
            </Field>}

            {form.mode !== "kortext" && form.mode !== "youtube" && form.format === "html" && (
              <>
                <Field label="HTML capture">
                  <select className="control appearance-none" value={form.htmlMode} onChange={(event) => updateForm("htmlMode", event.target.value as HtmlMode)}>
                    <option value="clean">Clean portable page</option>
                    <option value="snapshot">Original-site snapshot</option>
                  </select>
                </Field>
                <p className="rounded-xl border border-blue-200/70 bg-blue-50/70 px-4 py-3 text-xs leading-5 text-slate-600 md:col-span-2 dark:border-blue-400/15 dark:bg-blue-400/[0.06] dark:text-slate-400">
                  {form.htmlMode === "snapshot"
                    ? "Preserves site styles and scripts. Linked resources may need internet access; enable Render JavaScript for dynamic sites and open snapshots only from sites you trust."
                    : "Removes active site content and applies a portable reading layout suitable for reopening offline."}
                </p>
              </>
            )}

            {form.mode === "youtube" ? (
              <>
                <Field label="Preferred languages">
                  <input className="control" value={form.languages} onChange={(event) => updateForm("languages", event.target.value)} placeholder="en, en-US, am" />
                </Field>
                <Field label="Translate fallback to (optional)">
                  <input className="control" value={form.translateTo} onChange={(event) => updateForm("translateTo", event.target.value)} placeholder="en" />
                </Field>
              </>
            ) : form.mode !== "kortext" && (
              <Field label={form.mode === "book" ? "Delay between chapters" : form.mode === "site" ? "Delay between pages" : "Delay before fetching"}>
                <div className="relative">
                  <input className="control pr-20" type="number" min={0} step={0.5} value={form.delay} onChange={(event) => updateForm("delay", Number(event.target.value))} />
                  <span className="pointer-events-none absolute top-1/2 right-4 -translate-y-1/2 text-xs font-semibold text-slate-400">seconds</span>
                </div>
              </Field>
            )}
          </div>

          {form.mode !== "kortext" && <div className="mt-7 border-t border-slate-200 pt-6 dark:border-white/10">
            <p className="field-label">{form.mode === "youtube" ? "Transcript options" : "Browser options"}</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {form.mode === "youtube" ? (
                <>
                  <Toggle label="Require preferred language" checked={form.strictLanguage} onChange={(checked) => updateForm("strictLanguage", checked)} />
                </>
              ) : (
                <>
                  <Toggle label="Render JavaScript" checked={form.mode === "book" || form.playwright} disabled={form.mode === "book"} onChange={setPlaywright} />
                  <Toggle label="Show browser" checked={form.headed} disabled={form.mode !== "book" && !form.playwright} onChange={setHeaded} />
                  <Toggle label="Wait for verification" checked={form.waitForUser} disabled={!form.headed || (form.mode !== "book" && !form.playwright)} onChange={(checked) => updateForm("waitForUser", checked)} />
                  {form.format === "html" && <Toggle label="Embed page images" checked={form.embedImages} onChange={(checked) => updateForm("embedImages", checked)} />}
                </>
              )}
              <Toggle label="Overwrite files" checked={form.overwrite} onChange={(checked) => updateForm("overwrite", checked)} />
            </div>
          </div>}

          <AnimatePresence>
            {error && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="mt-5 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-300">
                <X className="mt-0.5 shrink-0" size={16} />
                <span className="flex-1">{error}</span>
                <button onClick={() => setError("")} aria-label="Dismiss error"><X size={15} /></button>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="mt-7 flex flex-col-reverse gap-3 border-t border-slate-200 pt-6 sm:flex-row sm:items-center sm:justify-between dark:border-white/10">
            <div className="flex flex-wrap gap-2">
              <ActivityDialog logs={logs} status={status} savedCount={savedCount} expectedOutputs={unlimitedCapture ? 0 : safeExpectedOutputs} />
              <HistoryDialog entries={history} mode={form.mode} onRefresh={refreshHistory} />
            </div>
            <div className="flex flex-wrap gap-2 sm:justify-end">
              <motion.button whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }} onClick={openOutput} className="inline-flex h-11 items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm font-bold text-slate-700 dark:border-white/10 dark:bg-white/[0.055] dark:text-slate-200">
                <ExternalLink size={16} /> Open output
              </motion.button>
              {running ? (
                <motion.button whileTap={{ scale: 0.97 }} onClick={stopExtraction} className="inline-flex h-11 items-center gap-2 rounded-xl bg-red-600 px-5 text-sm font-bold text-white shadow-lg shadow-red-600/20">
                  <CircleStop size={17} /> Stop
                </motion.button>
              ) : (
                <motion.button whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }} onClick={startExtraction} className="inline-flex h-11 items-center gap-2 rounded-xl bg-blue-600 px-5 text-sm font-bold text-white shadow-lg shadow-blue-600/25">
                  <Play size={17} fill="currentColor" /> {form.mode === "kortext" ? "Open Kortext browser" : "Start extraction"}
                </motion.button>
              )}
            </div>
          </div>
        </motion.section>
        </GlassSurface>

        <AnimatePresence>
          {(running || savedCount > 0) && (
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-5">
              <GlassSurface width="100%" height="auto" borderRadius={28} distortionScale={-24} greenOffset={2} blueOffset={4} backgroundOpacity={isDark ? 0.58 : 0.52} saturation={1.45} className="border border-white/75 dark:border-white/15">
              <section className="w-full p-5">
                <div className="flex items-center gap-4">
                <div className={cn("grid size-10 shrink-0 place-items-center rounded-xl", verificationNeeded ? "bg-amber-100 text-amber-700 dark:bg-amber-400/10 dark:text-amber-300" : "bg-blue-100 text-blue-700 dark:bg-blue-400/10 dark:text-blue-300")}>
                  {running ? <LoaderCircle className="animate-spin" size={19} /> : <Check size={19} />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <p className="truncate text-sm font-extrabold">{status}</p>
                    <p className="shrink-0 text-xs font-bold text-slate-500 dark:text-slate-400">{form.mode === "kortext" ? `${savedCount} pages saved` : `${savedCount} / ${safeExpectedOutputs}`}</p>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-white/10">
                    <motion.div className="h-full rounded-full bg-blue-600" animate={{ width: `${progress}%` }} transition={spring} />
                  </div>
                </div>
                {verificationNeeded && (
                  <motion.button initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} whileTap={{ scale: 0.97 }} onClick={confirmVerification} className="shrink-0 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white">
                    {form.mode === "kortext" ? "Start capture" : "Verification complete"}
                  </motion.button>
                )}
                </div>
              </section>
              </GlassSurface>
            </motion.div>
          )}
        </AnimatePresence>

        <footer className="mt-auto pt-8 text-center text-xs text-slate-500 dark:text-slate-500">
          Runs locally. Respects normal site access controls and available caption permissions.
        </footer>
      </main>
    </div>
  )
}

function ModePicker({ mode, onChange }: { mode: Mode; onChange: (workflow: Workflow) => void }) {
  const options = [
    { id: "kortext" as const, title: "Kortext", description: "Capture pages from your PDF reader.", visual: <FileText className="size-10 text-blue-600" /> },
    {
      id: "web" as const,
      title: "Web",
      description: "Extract one public page or crawl a whole site.",
      visual: <WebPageWorkflowIcon className="size-full" />,
    },
    {
      id: "book" as const,
      title: "Book",
      description: "Save one chapter or a numbered chapter range.",
      visual: <img src={binaryBooksArt} alt="" className="size-[115%] object-contain" />,
    },
    {
      id: "youtube" as const,
      title: "YouTube",
      description: "Save one transcript or extract a playlist.",
      visual: <img src={youtubeExtractionArt} alt="" className="size-[118%] object-contain" />,
    },
  ]
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {options.map((option) => {
        const selected = option.id === "web" ? mode === "page" || mode === "site" : mode === option.id
        return (
          <motion.div
            key={option.id}
            layout
            whileHover={{ y: -3 }}
            whileTap={{ scale: 0.985 }}
            transition={spring}
          >
            <GlassSurface
              width="100%"
              height="100%"
              borderRadius={16}
              borderWidth={0.09}
              brightness={68}
              blur={8}
              displace={0.35}
              distortionScale={-22}
              greenOffset={2}
              blueOffset={4}
              backgroundOpacity={selected ? 0.12 : 0.48}
              saturation={1.55}
              className={cn(
                "min-h-32 border shadow-lg transition-all",
                selected
                  ? "border-blue-300/70 text-white shadow-blue-900/20"
                  : "border-white/75 text-slate-900 shadow-slate-900/8 hover:border-blue-300/70 dark:border-white/14 dark:text-white dark:shadow-black/25 dark:hover:border-blue-400/35",
              )}
              style={selected ? { backgroundColor: "rgb(37 99 235 / 0.82)" } : undefined}
            >
              <button type="button" onClick={() => onChange(option.id)} className="relative min-h-32 w-full p-4 text-left sm:p-5">
                {selected && <motion.div layoutId="mode-glow" className="absolute inset-0 bg-[radial-gradient(circle_at_85%_15%,rgba(255,255,255,0.25),transparent_40%)]" />}
                <div className="relative flex items-start gap-4">
                  <div className={cn("grid size-16 shrink-0 place-items-center overflow-hidden rounded-2xl border p-1.5 shadow-sm", selected ? "border-white/40 bg-white/96" : "border-white/75 bg-white/74 dark:border-white/10 dark:bg-slate-900/70")}>
                    {option.visual}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-extrabold">{option.title}</p>
                      <ChevronRight className={selected ? "opacity-100" : "opacity-30"} size={17} />
                    </div>
                    <p className={cn("mt-1 text-sm leading-5", selected ? "text-blue-100" : "text-slate-500 dark:text-slate-400")}>{option.description}</p>
                  </div>
                </div>
              </button>
            </GlassSurface>
          </motion.div>
        )
      })}
    </div>
  )
}

function WorkflowVariantTabs({
  form,
  onWebChange,
  onBookChange,
  onYouTubeChange,
}: {
  form: ExtractionForm
  onWebChange: (mode: "page" | "site") => void
  onBookChange: (multiple: boolean) => void
  onYouTubeChange: (playlist: boolean) => void
}) {
  const options = form.mode === "page" || form.mode === "site"
    ? [
        { id: "page", label: "One page", selected: form.mode === "page", select: () => onWebChange("page") },
        { id: "site", label: "Whole site", selected: form.mode === "site", select: () => onWebChange("site") },
      ]
    : form.mode === "book"
      ? [
          { id: "single", label: "One chapter", selected: !form.bookMultiple, select: () => onBookChange(false) },
          { id: "multiple", label: "Multiple chapters", selected: form.bookMultiple, select: () => onBookChange(true) },
        ]
      : [
          { id: "video", label: "Single video", selected: !form.playlist, select: () => onYouTubeChange(false) },
          { id: "playlist", label: "Playlist", selected: form.playlist, select: () => onYouTubeChange(true) },
        ]

  return (
    <div className="mb-7 inline-flex rounded-2xl border border-white/65 bg-white/28 p-1.5 shadow-sm backdrop-blur-[20px] dark:border-white/10 dark:bg-white/[0.025]" role="tablist" aria-label="Extraction scope">
      {options.map((option) => (
        <button
          key={option.id}
          role="tab"
          aria-selected={option.selected}
          onClick={option.select}
          className={cn(
            "min-w-32 rounded-xl px-4 py-2.5 text-sm font-bold transition-all",
            option.selected
              ? "bg-blue-600 text-white shadow-md shadow-blue-600/20"
              : "text-slate-600 hover:bg-white/65 hover:text-slate-950 dark:text-slate-400 dark:hover:bg-white/8 dark:hover:text-white",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

function Field({ label, className, children }: { label: string; className?: string; children: React.ReactNode }) {
  return <label className={cn("min-w-0", className)}><span className="field-label">{label}</span>{children}</label>
}

function Toggle({ label, checked, disabled = false, onChange }: { label: string; checked: boolean; disabled?: boolean; onChange: (checked: boolean) => void }) {
  return (
    <motion.button
      whileTap={disabled ? undefined : { scale: 0.98 }}
      onClick={() => !disabled && onChange(!checked)}
      className={cn("flex min-h-11 items-center gap-3 rounded-xl border px-3.5 py-2.5 text-left text-sm font-semibold transition", checked ? "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-200" : "border-slate-200 bg-slate-50 text-slate-600 dark:border-white/10 dark:bg-white/[0.035] dark:text-slate-400", disabled && "cursor-not-allowed opacity-65")}
      aria-pressed={checked}
    >
      <span className={cn("grid size-5 shrink-0 place-items-center rounded-md border", checked ? "border-blue-600 bg-blue-600 text-white" : "border-slate-300 bg-white dark:border-white/20 dark:bg-white/5")}>
        {checked && <Check size={13} strokeWidth={3} />}
      </span>
      <span>{label}</span>
    </motion.button>
  )
}

function ThemeSwitcher({ theme, onChange }: { theme: Theme; onChange: (theme: Theme) => void }) {
  const choices = [
    { id: "light" as const, icon: Sun, label: "Light" },
    { id: "system" as const, icon: Laptop, label: "System" },
    { id: "dark" as const, icon: Moon, label: "Midnight blue" },
    { id: "black" as const, icon: Contrast, label: "Black" },
  ]
  return (
    <div className="flex rounded-xl border border-slate-200 bg-white/80 p-1 shadow-sm backdrop-blur-xl dark:border-white/10 dark:bg-white/[0.055]">
      {choices.map(({ id, icon: Icon, label }) => (
        <button key={id} onClick={() => onChange(id)} className={cn("relative grid size-8 place-items-center rounded-lg text-slate-500 transition dark:text-slate-400", theme === id && "text-slate-950 dark:text-white")} title={`${label} theme`} aria-label={`${label} theme`}>
          {theme === id && <motion.span layoutId="theme-pill" className="absolute inset-0 rounded-lg bg-slate-100 shadow-sm dark:bg-white/10" transition={spring} />}
          <Icon className="relative" size={15} />
        </button>
      ))}
    </div>
  )
}

function ActivityDialog({ logs, status, savedCount, expectedOutputs }: { logs: string[]; status: string; savedCount: number; expectedOutputs: number }) {
  const logText = useMemo(() => logs.join("").trim() || "Activity will appear here after extraction starts.", [logs])
  return (
    <MorphingDialog transition={{ type: "spring", bounce: 0.04, duration: 0.42 }}>
      <MorphingDialogTrigger className="flex h-11 items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 text-left dark:border-white/10 dark:bg-white/[0.035]">
        <ScrollText size={17} className="text-blue-600 dark:text-blue-400" />
        <span><span className="block text-xs font-extrabold">Activity</span><span className="block text-[0.68rem] text-slate-500 dark:text-slate-400">{expectedOutputs ? `${savedCount} of ${expectedOutputs} saved` : `${savedCount} pages saved`}</span></span>
      </MorphingDialogTrigger>
      <MorphingDialogContainer>
        <MorphingDialogContent className="relative max-h-[calc(100vh-2rem)] w-full max-w-2xl overflow-y-auto rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-white/10 dark:bg-[#0d1420] sm:p-7">
          <MorphingDialogTitle className="flex items-center gap-3 pr-10">
            <div className="grid size-10 place-items-center rounded-xl bg-blue-100 text-blue-700 dark:bg-blue-400/10 dark:text-blue-300"><FileText size={18} /></div>
            <div><h3 className="text-lg font-extrabold">Extraction activity</h3><p className="text-sm text-slate-500 dark:text-slate-400">{status}</p></div>
          </MorphingDialogTitle>
          <MorphingDialogDescription className="mt-5" variants={{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: 8 } }}>
            <pre className="max-h-[55vh] min-h-48 overflow-auto whitespace-pre-wrap rounded-2xl border border-slate-200 bg-slate-950 p-4 font-mono text-xs leading-5 text-slate-300 dark:border-white/10">{logText}</pre>
          </MorphingDialogDescription>
          <MorphingDialogClose className="icon-button top-5 right-5"><X size={17} /></MorphingDialogClose>
        </MorphingDialogContent>
      </MorphingDialogContainer>
    </MorphingDialog>
  )
}

function HistoryDialog({ entries, mode, onRefresh }: { entries: HistoryEntry[]; mode: Mode; onRefresh: () => Promise<void> }) {
  return (
    <MorphingDialog transition={{ type: "spring", bounce: 0.04, duration: 0.42 }}>
      <MorphingDialogTrigger className="flex h-11 items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 text-left dark:border-white/10 dark:bg-white/[0.035]">
        <History size={17} className="text-blue-600 dark:text-blue-400" />
        <span><span className="block text-xs font-extrabold">History</span><span className="block text-[0.68rem] text-slate-500 dark:text-slate-400">{entries.length} recent {mode} runs</span></span>
      </MorphingDialogTrigger>
      <MorphingDialogContainer>
        <MorphingDialogContent className="relative max-h-[calc(100vh-2rem)] w-full max-w-2xl overflow-y-auto rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-white/10 dark:bg-[#0d1420] sm:p-7">
          <MorphingDialogTitle className="flex items-center gap-3 pr-10">
            <div className="grid size-10 place-items-center rounded-xl bg-blue-100 text-blue-700 dark:bg-blue-400/10 dark:text-blue-300"><History size={18} /></div>
            <div className="flex-1"><h3 className="text-lg font-extrabold">{modeDetails[mode].title} history</h3><p className="text-sm text-slate-500 dark:text-slate-400">Saved locally on this computer</p></div>
            <button className="rounded-lg px-3 py-1.5 text-xs font-bold text-blue-700 hover:bg-blue-50 dark:text-blue-300 dark:hover:bg-blue-400/10" onClick={() => void onRefresh()}>Refresh</button>
          </MorphingDialogTitle>
          <MorphingDialogDescription className="mt-5" variants={{ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: 8 } }}>
            {entries.length ? (
              <div className="max-h-[55vh] space-y-2 overflow-auto pr-1">
                {entries.map((entry) => (
                  <div key={`${entry.timestamp}-${entry.path}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-white/10 dark:bg-white/[0.035]">
                    <div className="flex items-start justify-between gap-3">
                      <p className="min-w-0 truncate text-sm font-extrabold">{entry.label}</p>
                      <time className="shrink-0 text-[0.68rem] text-slate-500 dark:text-slate-400">{new Date(entry.timestamp).toLocaleString()}</time>
                    </div>
                    <p className="mt-1 truncate text-xs text-slate-500 dark:text-slate-400">{entry.source}</p>
                    <p className="mt-2 truncate font-mono text-[0.68rem] text-slate-500 dark:text-slate-500">{entry.path}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-300 px-5 py-10 text-center text-sm text-slate-500 dark:border-white/15 dark:text-slate-400">Completed extractions for this section will appear here.</div>
            )}
          </MorphingDialogDescription>
          <MorphingDialogClose className="icon-button top-5 right-5"><X size={17} /></MorphingDialogClose>
        </MorphingDialogContent>
      </MorphingDialogContainer>
    </MorphingDialog>
  )
}

export default App
