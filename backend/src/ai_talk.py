import asyncio
import json
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import HTTPException

from src.audiodbinfo import create_endpoint_output

GEMINI_TIMEOUT_MS = 300_000
MODEL1 = "gemini-3.8-flash"
MODEL2 = "gemini-3.7-flash"

def _is_valid_http_url(value: str) -> bool:
    """Return whether value is a well-formed HTTP(S) URL hosted by TheAudioDB."""
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
    """Parse Gemini's response envelope into song-name and URL dictionaries.
    Checks each entry has a song name and url
    Raises HTTP 502 if the response has no text output, invalid JSON, or entries
    that do not contain a string name and URL.
    """
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
    """Check one TheAudioDB URL, following only valid TheAudioDB redirects.

    Returns a success flag and an empty reason on success, or a failure reason
    when the URL is invalid, unreachable, or returns a non-success status.
    """
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
    """Check all song URLs with at most ten concurrent requests.

    Returns (song index, failure reason) pairs for URLs that did not pass
    validation or return a successful HTTP response.
    """
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


# async def parse_gemini_songs(gemini_response: dict[str, object]):
#     """Extract songs and verify their TheAudioDB URLs.
# UPD: Use mood string as preference for what type of songs
# Use description to understand what situation they're in
# and generate a playlist from there
# 50 songs
# check url is valid before sending back to user
async def send_to_gemini(mood: str, description: str, genre: str = "", era: str = "") -> dict[str, object]:
    """Request song recommendations from Gemini."""
    prompt = (
        f"Create a list of 50 songs with a {mood} feeling. "
        f"Tailor list to someone in this situation: {description}."
        f"Songs should be from the genre: ({genre}), and from the era: {era}."
        f"If the genre or era is not specified, you can choose any genre or era that fits the mood and situation."
        f"Return only a valid JSON array. Each item "
        "must have exactly two string fields: `name` for the song title and "
        "`url` for a direct link to its page on TheAudioDB. Do not invent links; "
        "include only songs with a verified TheAudioDB link."
    )

    return create_endpoint_output(mood, get_gemini_response(prompt))


def get_gemini_response(content, system_instruction="", model=""):
    """Send content and an optional system instruction to Gemini.

    Try MODEL1 first and retry once with MODEL2 if it times out.
    Returns the Gemini SDK response object.
    """
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError

    print(content)
    try:
        client = genai.Client(
            api_key="AQ.Ab8RN6IZro0q7RAvUgXDANGBiBKpMCk_XZ85sJcDoa4yKgBzgw",
            http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_MS)
        )
        for model in (MODEL1, MODEL2):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=content,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                    ),
                )
                break
            except httpx.TimeoutException:
                if model == MODEL2:
                    print("Model took too long")
                    raise HTTPException(
                        status_code=503,
                        detail="server unavailable",
                    )
    except APIError as exc:
        print(exc.code, exc.message)
        if exc.code == 429 or 500 <= exc.code < 600:
            raise HTTPException(
                status_code=503,
                detail="server unavailable",
            ) from exc
        raise
    except httpx.RequestError as exc:
        print("Some form of network error")
        raise HTTPException(
            status_code=503,
            detail="server unavailable",
        ) from exc

    return json.loads(response.text)  


if __name__ == "__main__":
    print(send_to_gemini("stressed", "I just want to relax and feel better"))

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