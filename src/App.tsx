import { Fragment, useEffect, useMemo, useState } from "react"
import { openEpisodeInSpotify, spotifyShowUrl } from "./spotify"
import { TOPIC_LABELS, TOPIC_ORDER } from "./topics"
import type { Episode, EpisodeFormat } from "./types"

const PAGE_SIZE = 40

const FORMAT_OPTIONS: { id: EpisodeFormat; label: string }[] = [
  { id: "episode", label: "Episodes" },
  { id: "short", label: "Short Stuff" },
  { id: "selects", label: "Selects" },
  { id: "live", label: "Live" },
  { id: "playlist", label: "Playlists" },
]

const LENGTH_OPTIONS = [
  { value: 0, label: "Any length" },
  { value: 20, label: "20 min+" },
  { value: 40, label: "40 min+" },
  { value: 60, label: "60 min+" },
]

type SortKey = "newest" | "oldest" | "longest" | "shortest" | "title"

function formatDuration(seconds: number) {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.round((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes} min`
}

function formatDate(iso: string) {
  if (!iso) return ""
  const [year, month, day] = iso.split("-").map(Number)
  return new Date(year, month - 1, day).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

function PlayButton({ title }: { title: string }) {
  return (
    <button
      type="button"
      aria-label={`Open ${title} in Spotify`}
      title="Open in Spotify"
      onClick={(event) => {
        event.stopPropagation()
        openEpisodeInSpotify(title)
      }}
      className="grid size-9 shrink-0 place-items-center rounded-full bg-spotify text-zinc-950 shadow-sm transition hover:scale-105 hover:brightness-110"
    >
      <svg viewBox="0 0 20 20" className="size-4 translate-x-px" aria-hidden="true">
        <path d="M5 3.5v13l12-6.5-12-6.5z" fill="currentColor" />
      </svg>
    </button>
  )
}

function TopicPills({ topics }: { topics: string[] }) {
  if (topics.length === 0) {
    return <span className="text-stone-400 dark:text-stone-500">—</span>
  }
  return (
    <span className="flex flex-wrap gap-1.5">
      {topics.map((topic) => (
        <span
          key={topic}
          className="rounded-full bg-stone-200/80 px-2 py-0.5 text-xs text-stone-700 dark:bg-white/8 dark:text-stone-300"
        >
          {TOPIC_LABELS[topic] ?? topic}
        </span>
      ))}
    </span>
  )
}

export default function App() {
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading")
  const [query, setQuery] = useState("")
  const [topics, setTopics] = useState<string[]>([])
  const [formats, setFormats] = useState<EpisodeFormat[]>(["episode"])
  const [minMinutes, setMinMinutes] = useState(0)
  const [yearFrom, setYearFrom] = useState(2008)
  const [yearTo, setYearTo] = useState(2026)
  const [sort, setSort] = useState<SortKey>("newest")
  const [page, setPage] = useState(0)
  const [openId, setOpenId] = useState<string | null>(null)
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"))

  useEffect(() => {
    let cancelled = false
    fetch(`${import.meta.env.BASE_URL}episodes.json`)
      .then((response) => {
        if (!response.ok) throw new Error("catalog missing")
        return response.json() as Promise<Episode[]>
      })
      .then((data) => {
        if (!cancelled) {
          setEpisodes(data)
          setStatus("ready")
        }
      })
      .catch(() => {
        if (!cancelled) setStatus("error")
      })
    return () => {
      cancelled = true
    }
  }, [])

  const years = useMemo(() => {
    const found = episodes.map((episode) => Number(episode.date.slice(0, 4))).filter(Boolean)
    if (found.length === 0) return { min: 2008, max: 2026 }
    return { min: Math.min(...found), max: Math.max(...found) }
  }, [episodes])

  useEffect(() => {
    if (episodes.length === 0) return
    const found = episodes.map((episode) => Number(episode.date.slice(0, 4))).filter(Boolean)
    setYearFrom(Math.min(...found))
    setYearTo(Math.max(...found))
  }, [episodes])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const topicSet = new Set(topics)
    const formatSet = new Set(formats)
    const minSeconds = minMinutes * 60
    const rows = episodes.filter((episode) => {
      if (!formatSet.has(episode.format)) return false
      if (episode.duration < minSeconds) return false
      const year = Number(episode.date.slice(0, 4))
      if (year && (year < yearFrom || year > yearTo)) return false
      if (topicSet.size > 0 && !episode.topics.some((topic) => topicSet.has(topic))) return false
      if (!needle) return true
      return (
        episode.title.toLowerCase().includes(needle) ||
        episode.summary.toLowerCase().includes(needle) ||
        episode.topics.some((topic) => (TOPIC_LABELS[topic] ?? topic).toLowerCase().includes(needle))
      )
    })
    rows.sort((a, b) => {
      if (sort === "newest") return b.date.localeCompare(a.date)
      if (sort === "oldest") return a.date.localeCompare(b.date)
      if (sort === "longest") return b.duration - a.duration
      if (sort === "shortest") return a.duration - b.duration
      return a.title.localeCompare(b.title)
    })
    return rows
  }, [episodes, formats, minMinutes, query, sort, topics, yearFrom, yearTo])

  useEffect(() => {
    setPage(0)
    setOpenId(null)
  }, [query, topics, formats, minMinutes, yearFrom, yearTo, sort])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount - 1)
  const visible = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE)

  function toggleTheme() {
    const next = !dark
    setDark(next)
    document.documentElement.classList.toggle("dark", next)
    localStorage.setItem("theme", next ? "dark" : "light")
  }

  function toggleTopic(topic: string) {
    setTopics((current) =>
      current.includes(topic) ? current.filter((item) => item !== topic) : [...current, topic],
    )
  }

  function toggleFormat(format: EpisodeFormat) {
    setFormats((current) =>
      current.includes(format) ? current.filter((item) => item !== format) : [...current, format],
    )
  }

  function applyBedtime() {
    setFormats(["episode"])
    setMinMinutes(40)
    setTopics([])
    setYearFrom(years.min)
    setYearTo(years.max)
    setSort("newest")
    setQuery("")
  }

  return (
    <div className="min-h-screen bg-[#f6f1e8] text-[#241c16] dark:bg-[#12100e] dark:text-[#f4ece3]">
      <header className="border-b border-stone-300/80 bg-[#f6f1e8]/90 backdrop-blur dark:border-white/10 dark:bg-[#12100e]/90">
        <div className="mx-auto flex max-w-6xl flex-wrap items-end justify-between gap-4 px-4 py-6 sm:px-6">
          <div>
            <p className="text-xs font-medium tracking-[0.22em] text-stone-500 uppercase dark:text-stone-400">
              Stuff You Should Know
            </p>
            <h1 className="mt-1 font-serif text-4xl tracking-tight text-balance sm:text-5xl">
              Something to fall asleep to
            </h1>
            <p className="mt-2 max-w-xl text-sm text-stone-600 dark:text-stone-400">
              {episodes.length > 0 ? `${episodes.length.toLocaleString()} episodes` : "Episodes"} from
              the public show feed. Play opens Spotify.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={spotifyShowUrl()}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-stone-300 px-3 py-1.5 text-sm text-stone-700 transition hover:border-stone-500 dark:border-white/15 dark:text-stone-200 dark:hover:border-white/40"
            >
              Open show
            </a>
            <button
              type="button"
              onClick={toggleTheme}
              className="rounded-full border border-stone-300 px-3 py-1.5 text-sm text-stone-700 transition hover:border-stone-500 dark:border-white/15 dark:text-stone-200 dark:hover:border-white/40"
            >
              {dark ? "Light mode" : "Dark mode"}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        <div className="sticky top-0 z-10 -mx-4 mb-4 border-b border-transparent bg-[#f6f1e8]/95 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6 dark:bg-[#12100e]/95">
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-2 sm:flex-row">
              <label className="relative min-w-0 flex-1">
                <span className="sr-only">Search episodes</span>
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search titles and show notes"
                  className="w-full rounded-2xl border border-stone-300 bg-white px-4 py-3 text-base outline-none placeholder:text-stone-400 focus:border-lamp-deep dark:border-white/10 dark:bg-[#1c1916] dark:placeholder:text-stone-500 dark:focus:border-lamp"
                />
              </label>
              <button
                type="button"
                onClick={applyBedtime}
                className="rounded-2xl bg-lamp px-4 py-3 text-sm font-medium text-zinc-950 transition hover:brightness-105"
              >
                Bedtime length
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {FORMAT_OPTIONS.map((option) => {
                const on = formats.includes(option.id)
                return (
                  <button
                    key={option.id}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggleFormat(option.id)}
                    className={`rounded-full px-3 py-1 text-sm transition ${
                      on
                        ? "bg-[#241c16] text-[#f6f1e8] dark:bg-[#f4ece3] dark:text-[#1a1512]"
                        : "bg-stone-200/70 text-stone-600 dark:bg-white/8 dark:text-stone-300"
                    }`}
                  >
                    {option.label}
                  </button>
                )
              })}
              <select
                aria-label="Minimum length"
                value={minMinutes}
                onChange={(event) => setMinMinutes(Number(event.target.value))}
                className="rounded-full border border-stone-300 bg-white px-3 py-1 text-sm dark:border-white/10 dark:bg-[#1c1916]"
              >
                {LENGTH_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <select
                aria-label="Sort"
                value={sort}
                onChange={(event) => setSort(event.target.value as SortKey)}
                className="rounded-full border border-stone-300 bg-white px-3 py-1 text-sm dark:border-white/10 dark:bg-[#1c1916]"
              >
                <option value="newest">Newest</option>
                <option value="oldest">Oldest</option>
                <option value="longest">Longest</option>
                <option value="shortest">Shortest</option>
                <option value="title">Title</option>
              </select>
              <label className="flex items-center gap-1 text-sm text-stone-600 dark:text-stone-300">
                <span className="sr-only">From year</span>
                <select
                  aria-label="From year"
                  value={yearFrom}
                  onChange={(event) => setYearFrom(Number(event.target.value))}
                  className="rounded-full border border-stone-300 bg-white px-2 py-1 dark:border-white/10 dark:bg-[#1c1916]"
                >
                  {Array.from({ length: years.max - years.min + 1 }, (_, index) => years.min + index).map(
                    (year) => (
                      <option key={year} value={year}>
                        {year}
                      </option>
                    ),
                  )}
                </select>
                <span aria-hidden="true">–</span>
                <select
                  aria-label="To year"
                  value={yearTo}
                  onChange={(event) => setYearTo(Number(event.target.value))}
                  className="rounded-full border border-stone-300 bg-white px-2 py-1 dark:border-white/10 dark:bg-[#1c1916]"
                >
                  {Array.from({ length: years.max - years.min + 1 }, (_, index) => years.min + index).map(
                    (year) => (
                      <option key={year} value={year}>
                        {year}
                      </option>
                    ),
                  )}
                </select>
              </label>
            </div>

            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                aria-pressed={topics.length === 0}
                onClick={() => setTopics([])}
                className={`rounded-full px-2.5 py-1 text-xs ${
                  topics.length === 0
                    ? "bg-lamp text-zinc-950"
                    : "bg-stone-200/70 text-stone-600 dark:bg-white/8 dark:text-stone-300"
                }`}
              >
                Any topic
              </button>
              {TOPIC_ORDER.map((topic) => {
                const on = topics.includes(topic)
                return (
                  <button
                    key={topic}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggleTopic(topic)}
                    className={`rounded-full px-2.5 py-1 text-xs ${
                      on
                        ? "bg-lamp text-zinc-950"
                        : "bg-stone-200/70 text-stone-600 dark:bg-white/8 dark:text-stone-300"
                    }`}
                  >
                    {TOPIC_LABELS[topic]}
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        <div className="mb-3 flex items-baseline justify-between gap-3 text-sm text-stone-600 dark:text-stone-400">
          <p>
            {status === "loading"
              ? "Loading the catalog…"
              : `${filtered.length.toLocaleString()} shown`}
            {topics.length > 0 ? " · any selected topic" : ""}
          </p>
          {pageCount > 1 && (
            <p>
              Page {safePage + 1} of {pageCount}
            </p>
          )}
        </div>

        {status === "error" && (
          <p className="rounded-2xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-900 dark:bg-red-950 dark:text-red-100">
            The episode catalog didn’t load. Run <code>python3 scripts/build_catalog.py</code> and refresh.
          </p>
        )}

        {status === "ready" && filtered.length === 0 && (
          <p className="rounded-2xl border border-dashed border-stone-300 px-4 py-10 text-center text-stone-500 dark:border-white/15">
            Nothing matches. Clear a topic or include Short Stuff and Selects.
          </p>
        )}

        {visible.length > 0 && (
          <>
            <div className="hidden overflow-hidden rounded-2xl border border-stone-300 bg-white md:block dark:border-white/10 dark:bg-[#1a1714]">
              <table className="w-full border-collapse text-left">
                <thead className="text-xs tracking-wide text-stone-500 uppercase dark:text-stone-400">
                  <tr className="border-b border-stone-200 dark:border-white/10">
                    <th className="px-3 py-3 font-medium">Play</th>
                    <th className="px-3 py-3 font-medium">Date</th>
                    <th className="px-3 py-3 font-medium">Title</th>
                    <th className="px-3 py-3 font-medium">Length</th>
                    <th className="px-3 py-3 font-medium">Topics</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((episode) => {
                    const open = openId === episode.id
                    return (
                      <Fragment key={episode.id}>
                        <tr className="border-b border-stone-100 hover:bg-stone-50 dark:border-white/5 dark:hover:bg-white/5">
                          <td className="px-3 py-3">
                            <PlayButton title={episode.title} />
                          </td>
                          <td className="px-3 py-3 text-sm text-stone-500 tabular-nums dark:text-stone-400">
                            {formatDate(episode.date)}
                          </td>
                          <td className="px-3 py-3">
                            <button
                              type="button"
                              onClick={() => setOpenId(open ? null : episode.id)}
                              className="text-left font-medium underline-offset-2 hover:underline"
                            >
                              {episode.title}
                            </button>
                          </td>
                          <td className="px-3 py-3 text-sm text-stone-500 tabular-nums whitespace-nowrap dark:text-stone-400">
                            {formatDuration(episode.duration)}
                          </td>
                          <td className="px-3 py-3">
                            <TopicPills topics={episode.topics} />
                          </td>
                        </tr>
                        {open && (
                          <tr className="border-b border-stone-100 dark:border-white/5">
                            <td colSpan={5}>
                              <Notes episode={episode} />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <ul className="space-y-3 md:hidden">
              {visible.map((episode) => {
                const open = openId === episode.id
                return (
                  <li
                    key={episode.id}
                    className="rounded-2xl border border-stone-300 bg-white dark:border-white/10 dark:bg-[#1a1714]"
                  >
                    <div className="flex items-start gap-3 p-3">
                      <PlayButton title={episode.title} />
                      <button
                        type="button"
                        onClick={() => setOpenId(open ? null : episode.id)}
                        className="min-w-0 flex-1 text-left"
                      >
                        <p className="font-medium">{episode.title}</p>
                        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">
                          {formatDate(episode.date)} · {formatDuration(episode.duration)}
                        </p>
                        <div className="mt-2">
                          <TopicPills topics={episode.topics} />
                        </div>
                      </button>
                    </div>
                    {open && <Notes episode={episode} />}
                  </li>
                )
              })}
            </ul>
          </>
        )}

        {pageCount > 1 && (
          <div className="mt-4 flex items-center justify-between">
            <button
              type="button"
              disabled={safePage === 0}
              onClick={() => setPage(Math.max(0, safePage - 1))}
              className="rounded-full border border-stone-300 px-4 py-2 text-sm disabled:opacity-40 dark:border-white/15"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={safePage >= pageCount - 1}
              onClick={() => setPage(safePage + 1)}
              className="rounded-full border border-stone-300 px-4 py-2 text-sm disabled:opacity-40 dark:border-white/15"
            >
              Next
            </button>
          </div>
        )}

        <p className="mt-8 max-w-2xl text-xs leading-relaxed text-stone-500 dark:text-stone-500">
          Titles, dates, and show notes come from the public RSS feed. Topics come from Jev,
          which can assign more than one label from the title and show notes. Spotify doesn’t
          publish a full episode index without an app login, so play opens a Spotify window
          searched to that episode. Transcript links go to the show’s own transcript when one
          is published.
        </p>
      </main>
    </div>
  )
}

function Notes({ episode }: { episode: Episode }) {
  return (
    <div className="border-t border-stone-100 px-4 py-3 text-sm text-stone-600 dark:border-white/10 dark:text-stone-300">
      <p className="max-w-3xl leading-relaxed">{episode.summary || "No show notes on this one."}</p>
      <p className="mt-3 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => openEpisodeInSpotify(episode.title)}
          className="text-spotify underline-offset-2 hover:underline"
        >
          Play in Spotify
        </button>
        {episode.url && (
          <a href={episode.url} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
            Episode page
          </a>
        )}
        {episode.transcript && (
          <a
            href={episode.transcript}
            target="_blank"
            rel="noreferrer"
            className="underline-offset-2 hover:underline"
          >
            Transcript
          </a>
        )}
      </p>
    </div>
  )
}
