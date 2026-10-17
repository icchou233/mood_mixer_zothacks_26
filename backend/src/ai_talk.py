import json
import os
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from fastapi.responses import JSONResponse


def parse_gemini_songs(gemini_response: dict[str, object]) -> JSONResponse:
    """Extract song names and URLs from a Gemini Interactions API response."""
    outputs = gemini_response.get("outputs")
    if not isinstance(outputs, list):
        raise HTTPException(status_code=502, detail="Gemini response has no outputs")

    text_parts = [
        output["text"]
        for output in outputs
        if isinstance(output, dict)
        and output.get("type") == "text"
        and isinstance(output.get("text"), str)
    ]
    if not text_parts:
        raise HTTPException(status_code=502, detail="Gemini response contains no text")

    text = "\n".join(text_parts).strip()
    if text.startswith("```"):
        text = (
            text.removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )

    try:
        songs = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Gemini returned invalid song JSON",
        ) from exc

    if not isinstance(songs, list):
        raise HTTPException(
            status_code=502,
            detail="Gemini song response must be a JSON array",
        )

    parsed_songs: list[dict[str, str]] = []
    for song in songs:
        if not isinstance(song, dict):
            raise HTTPException(
                status_code=502,
                detail="Gemini returned an invalid song entry",
            )

        name = song.get("name")
        url = song.get("url")
        if not isinstance(name, str) or not name.strip() or not isinstance(url, str):
            raise HTTPException(
                status_code=502,
                detail="Gemini song entries must include a name and valid URL",
            )

        url = url.strip()
        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise HTTPException(
                status_code=502,
                detail="Gemini song entries must include a name and valid URL",
            )

        parsed_songs.append({"name": name.strip(), "url": url})

    return JSONResponse(content=parsed_songs)


async def send_to_gemini(mood: str, num_songs: int) -> dict[str, object]:
    """Request song recommendations from Gemini."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set")

    prompt = (
        f"Create 5 distinct playlists for someone feeling {mood}, "
        f"with {num_songs} songs in each playlist. Give each playlist "
        "a unique style or theme. Return only a valid JSON array. Each item "
        "must have exactly two string fields: `name` for the song title and "
        "`url` for a direct link to its page on TheAudioDB. Do not invent links; "
        "include only songs with a verified TheAudioDB link."
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


def run_gemini_demo() -> None:
    from google import genai
    from google.genai import types

    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents="My name is Areeb",
        config=types.GenerateContentConfig(
            system_instruction=(
                "if the user enters a name, send back only the name in all caps, "
                "no other text. If the user enters anything else, send back the word IN"
            ),
            temperature=0.7,
        ),
    )
    print(response.text)


if __name__ == "__main__":
    run_gemini_demo()

"""
response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="My name is Areeb",
    config=types.GenerateContentConfig(
        system_instruction="if the user enters a name, send back only the name in all caps, no other text. If the user enters anything else, send back the word IN",
        temperature=0.7,
    ),
)
print(response.text)
"""