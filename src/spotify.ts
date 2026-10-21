const SHOW_URL = "https://open.spotify.com/show/0ofXAdFIQQRsCYj9754UFx"

export function spotifyShowUrl() {
  return SHOW_URL
}

function opensInSpotifyApp() {
  const ua = navigator.userAgent
  if (/Android|iPhone|iPad|iPod/i.test(ua)) return true
  // iPadOS reports itself as a Mac, but it still has a touch screen.
  return navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1
}

export function openEpisodeInSpotify(title: string) {
  const query = encodeURIComponent(`${title} Stuff You Should Know`)
  // The phone app reads the last part of the path as the search text, so a
  // link ending in /episodes searches for the word "episodes".
  if (opensInSpotifyApp()) {
    window.location.assign(`https://open.spotify.com/search/${query}`)
    return
  }
  const url = `https://open.spotify.com/search/${query}/episodes`
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
