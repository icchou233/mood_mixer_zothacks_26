"""
This file defines the FastAPI app for the API and all of its routes.
To run this API, use the FastAPI CLI
$ fastapi dev src/api.py
"""

import random

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.ai_talk import send_to_gemini
from src.spotify import create_playlist, get_song_link

# The app which manages all of the API routes
app = FastAPI()


# The decorator declares the function as a FastAPI route on the given path.
# This route in particular is a GET route at "/hello" which returns the example
# dictionary as a JSON response with the status code 200 by default.
@app.get("/hello")
async def hello() -> dict[str, str]:
    """Get hello message."""
    return {"message": "Hello from FastAPI"}


# The route can also handle query parameters encoded in the URL after the path,
# e.g. `/random?maximum=1000`
# If the value isn't an integer, FastAPI will return an error response
# with a validation error describing the invalid input.
@app.get("/random")
async def get_random_item(maximum: int) -> dict[str, int]:
    """Get an item with a random ID."""
    return {"itemId": random.randint(0, maximum)}

class SongRequest(BaseModel):
    mood: str
    description: str
    genre: str = ""
    era: str = ""

# This function processes a POST request; will change later
@app.post("/items")
async def process_request(request: SongRequest):
    return await send_to_gemini(
        request.mood,
        request.description,
        request.genre,
        request.era,
    )

@app.post("/names")
async def process_request(request) -> dict[str, str]:
    track_uris = []
    unmatched_songs = []
    songs = request.get("songs")
    for song in songs:
        track_uri = get_song_link(song["title"])
        if track_uri is None:
            unmatched_songs.append(song["title"])
        else:
            track_uris.append(track_uri)

    playlist_url = create_playlist(
        request.get("mood"),
        track_uris,
        description="Created by Mood Mixer",
    )
    if len(unmatched_songs) == 0:
        return {"playlist_url": playlist_url, "message":
                f"All songs were successfully added to the playlist."}
    return {"playlist_url": playlist_url, "message":
            f"Could not find Spotify tracks for: {', '.join(unmatched_songs)}"}
