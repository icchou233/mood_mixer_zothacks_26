import asyncio
import json
import os
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import HTTPException
from fastapi.responses import JSONResponse


def _is_valid_http_url(value: str) -> bool:
    if any(character.isspace() for character in value):
        return False

    try:
        parsed_url = urlsplit(value)
        hostname = parsed_url.hostname
        _ = parsed_url.port
    except ValueError:
        return False

    return (
        parsed_url.scheme in {"http", "https"}
        and hostname is not None
        and bool(hostname)
        and (
            hostname == "theaudiodb.com"
            or hostname.endswith(".theaudiodb.com")
        )
        and parsed_url.username is None
        and parsed_url.password is None
    )


def _extract_gemini_songs(
    gemini_response: dict[str, object],
) -> list[dict[str, str]]:
    """Parse song names and URL strings from Gemini's JSON text output."""
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
                detail="Gemini song entries must include a name and URL",
            )

        parsed_songs.append({"name": name.strip(), "url": url.strip()})

    return parsed_songs


async def _check_song_url(client: httpx.AsyncClient, url: str) -> tuple[bool, str]:
    if not _is_valid_http_url(url):
        return False, "URL is not a valid TheAudioDB HTTP(S) URL"

    current_url = url
    for _ in range(6):
        try:
            async with client.stream("GET", current_url) as response:
                if 200 <= response.status_code < 300:
                    return True, ""
                if response.status_code not in {301, 302, 303, 307, 308}:
                    return False, f"URL returned HTTP {response.status_code}"

                location = response.headers.get("location")
                if not location:
                    return False, "URL redirect did not include a destination"
                current_url = urljoin(current_url, location)
                if not _is_valid_http_url(current_url):
                    return False, "URL redirects outside TheAudioDB"
        except httpx.HTTPError as exc:
            return False, f"URL request failed: {exc}"

    return False, "URL exceeded the redirect limit"


async def _check_song_urls(songs: list[dict[str, str]]) -> list[tuple[int, str]]:
    semaphore = asyncio.Semaphore(10)
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        async def check_song(index: int, song: dict[str, str]) -> tuple[int, str] | None:
            async with semaphore:
                is_working, reason = await _check_song_url(client, song["url"])
            if not is_working:
                return index, reason
            return None

        results = await asyncio.gather(
            *(check_song(index, song) for index, song in enumerate(songs))
        )

    return [result for result in results if result is not None]


async def parse_gemini_songs(gemini_response: dict[str, object]) -> JSONResponse:
    """Extract songs, verify TheAudioDB URLs, and request one correction pass.

    If any URL is malformed, unreachable, returns a non-success status, or
    redirects away from TheAudioDB, Gemini is asked once for corrected URLs
    for those same songs. Corrected links are checked before any songs are
    returned. A correction that still fails validation raises HTTP 502.
    """
    songs = _extract_gemini_songs(gemini_response)
    failures = await _check_song_urls(songs)
    if not failures:
        return JSONResponse(content=songs)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set")

    failed_songs = [
        {
            "name": songs[index]["name"],
            "url": songs[index]["url"],
            "problem": reason,
        }
        for index, reason in failures
    ]
    correction_prompt = (
        "Correct the TheAudioDB URLs for these songs. Keep every song name "
        "exactly unchanged and in the same order. Find the direct TheAudioDB "
        "page for the same song; do not substitute a different song or invent "
        "a URL. Return only a JSON array with exactly one object per input, "
        "each containing string fields `name` and `url`.\n"
        f"{json.dumps(failed_songs, ensure_ascii=False)}"
    )
    corrected_response = get_gemini_response(correction_prompt)
    corrected_songs = _extract_gemini_songs(corrected_response)

    if len(corrected_songs) != len(failures):
        raise HTTPException(
            status_code=502,
            detail="Gemini did not return a corrected URL for every failed song",
        )

    for corrected, (index, _) in zip(corrected_songs, failures):
        if corrected["name"] != songs[index]["name"]:
            raise HTTPException(
                status_code=502,
                detail="Gemini changed a song name while correcting its URL",
            )
        songs[index]["url"] = corrected["url"]

    remaining_failures = await _check_song_urls(
        [songs[index] for index, _ in failures]
    )
    if remaining_failures:
        raise HTTPException(
            status_code=502,
            detail="Gemini returned a corrected URL that could not be verified",
        )

    return JSONResponse(content=songs)


# # UPD: Use mood string as preference for what type of songs
# # Use description to understand what situation they're in
# # and generate a playlist from there
# # 50 songs
# # check url is valid before sending back to user
# async def send_to_gemini(mood: str, description: str) -> dict[str, object]:
#     """Request song recommendations from Gemini."""
#     api_key = os.getenv("GEMINI_API_KEY")
#     if not api_key:
#         raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set")

#     prompt = (
#         f"Create 5 distinct playlists for someone feeling {mood}, "
#         f"with 50 songs in each playlist. Use this description as guidance: "
#         f"{description}. Give each playlist "
#         "a unique style or theme. Return only a valid JSON array. Each item "
#         "must have exactly two string fields: `name` for the song title and "
#         "`url` for a direct link to its page on TheAudioDB. Do not invent links; "
#         "include only songs with a verified TheAudioDB link."
#     )

#     return await _request_gemini(prompt, api_key)


def get_gemini_response(content, system_instruction=""):
    from google import genai
    from google.genai import types

    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=content,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
        ),
    )
    return response.to_json_dict()


if __name__ == "__main__":
    print('d')

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