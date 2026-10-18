import re
import requests

API_BASE = "https://www.theaudiodb.com/api/v1/json/123"   # "2" is the free test key


def track_id_from_url(url: str) -> str:
    # Matches /track/2115881 and also slug forms like /track/2115881-artist-song
    m = re.search(r"/track/(\d+)", url)
    if not m:
        raise ValueError(f"No track ID found in URL: {url}")
    return m.group(1)


def get_track_by_url(url: str):
    print(f"Fetching track info for URL: {url}")
    track_id = track_id_from_url(url)
    r = requests.get(f"{API_BASE}/track.php", params={"h": track_id}, timeout=15)
    r.raise_for_status()
    tracks = r.json().get("track") or []     # null when nothing matches
    return tracks[0] if tracks else None

def create_endpoint_output(mood, ai_input):
    the_output = dict()
    the_output["mood"] = mood
    the_output["songs"] = []
    for song in ai_input:
        track = get_track_by_url(song["url"])
        if track:
            the_output["songs"].append({"title": track["strTrack"], 
                                        "artist": track["strArtist"],
                                        "url": song["url"], "album": track["strAlbum"], 
                                        "duration": track["intDuration"], 
                                        "albumCover": track["strTrackThumb"]})
    return the_output