"""
This file defines the FastAPI app for the API and all of its routes.
To run this API, use the FastAPI CLI
$ fastapi dev src/api.py
"""

import os
import random

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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

# Currently it is designed to take in 2 parameters:
# mood and numSongs, but this can be changed
# For example, if user gives an elaborate description instead
# need to pin down what mood/genre to feed
# NEED GEMINI API KEY!!!!!

class SongRequest(BaseModel):
    mood: str
    numSongs: int

# This function processes a POST request; will change later
@app.post("/items")
async def process_request(request: SongRequest) -> dict[str, object]:
    return await send_to_gemini(request)

async def send_to_gemini(request: SongRequest) -> dict[str, object]:
    '''
    Takes in a mood and number of songs, then sends a request to 
    Gemini to get song recommendations. Create 5 separate playlists
    '''
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set")

    prompt = (
        f"Create 5 distinct playlists for someone feeling {request.mood}, "
        f"with {request.numSongs} songs in each playlist. Give each playlist "
        "a unique style or theme. For every song, include its title, artist, "
        "and a direct link to its page on TheAudioDB. Do not invent links; "
        "if you cannot provide a verified TheAudioDB link, say it is unavailable."
    )

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/interactions",
                headers={"x-goog-api-key": api_key},
                json={
                    "model": "gemini-3.8-flash",
                    "input": prompt,
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Gemini returned HTTP {exc.response.status_code}: "
                f"{exc.response.text[:1000]}"
            ),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Gemini: {exc}",
        ) from exc

    return response.json()