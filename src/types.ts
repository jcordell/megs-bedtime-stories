export type EpisodeFormat = "episode" | "short" | "selects" | "live" | "playlist"

export type Episode = {
  id: string
  title: string
  date: string
  duration: number
  summary: string
  topics: string[]
  format: EpisodeFormat
  url: string
  transcript: string | null
}
