const SHOW_URL = "https://open.spotify.com/show/0ofXAdFIQQRsCYj9754UFx"

export function spotifyShowUrl() {
  return SHOW_URL
}

export function openEpisodeInSpotify(title: string) {
  const query = `${title} Stuff You Should Know`
  const url = `https://open.spotify.com/search/${encodeURIComponent(query)}/episodes`
  const width = 460
  const height = 780
  const left = Math.max(0, window.screenX + (window.outerWidth - width) / 2)
  const top = Math.max(0, window.screenY + (window.outerHeight - height) / 2)
  const features = [
    "popup=yes",
    `width=${width}`,
    `height=${height}`,
    `left=${Math.round(left)}`,
    `top=${Math.round(top)}`,
  ].join(",")
  const popup = window.open(url, "sysk-spotify", features)
  if (!popup) {
    window.open(url, "_blank", "noopener,noreferrer")
  }
}
