import spotipy
from spotipy.oauth2 import SpotifyOAuth

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id="dbc58aa242ad46afa9c8892d49df0289",
    client_secret="6ba68ebfa7334a09a231df958abe8c62",
    redirect_uri="http://127.0.0.1:5000/callback",
    scope="playlist-modify-private playlist-modify-public",
))

def get_song_link(query):
    results = sp.search(q=query, type="track", limit=1, offset=0, market="US")
    return results["tracks"]["items"][0]["uri"] if results["tracks"]["items"] else None


def create_playlist(name, track_uris, description="", public=False):
    playlist = sp.current_user_playlist_create(
        name=name, public=public, description=description
    )
    for i in range(0, len(track_uris), 100):
        sp.playlist_add_items(playlist["id"], track_uris[i:i + 100])
    return playlist["external_urls"]["spotify"]

if __name__ == "__main__":
    create_playlist("Test Playlist", ["https://open.spotify.com/search/The%20Sweetest%20Condition%20Depeche%20Mode",
                                      "https://open.spotify.com/search/Lovetheme%20Depeche%20Mode"])