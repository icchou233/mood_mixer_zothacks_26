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
async def process_request(request: SongRequest) -> dict[str, str]:
    songs = await send_to_gemini(
        request.mood,
        request.description,
        request.genre,
        request.era,
    )
    track_uris = []
    unmatched_songs = []
    for song in songs:
        track_uri = get_song_link(song["name"])
        if track_uri is None:
            unmatched_songs.append(song["name"])
        else:
            track_uris.append(track_uri)

    if unmatched_songs:
        raise HTTPException(
            status_code=502,
            detail=f"Could not find Spotify tracks for: {', '.join(unmatched_songs)}",
        )

    playlist_url = create_playlist(
        "Generated Playlist",
        track_uris,
    )
    return {"playlist_url": playlist_url}
