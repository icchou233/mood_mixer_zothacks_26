import argparse
import asyncio
import json
import time

from fastapi import HTTPException
from src.ai_talk import send_to_gemini


async def run_gemini_test(mood: str, description: str) -> None:
    print("[1/3] Sending request to Gemini...", flush=True)
    started_at = time.monotonic()
    try:
        result = await send_to_gemini(mood, description)
    except HTTPException as exc:
        elapsed = time.monotonic() - started_at
        print(
            f"Gemini request failed after {elapsed:.1f}s: {exc.detail}",
            flush=True,
        )
        return

    elapsed = time.monotonic() - started_at
    print(f"[2/3] Gemini response received after {elapsed:.1f}s.", flush=True)
    print("[3/3] Response JSON:", flush=True)
    print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a sample song request to Gemini and print its response."
    )
    parser.add_argument("--mood", default="relaxed")
    parser.add_argument("--description", default="")
    args = parser.parse_args()

    print("[0/3] Starting Gemini test.", flush=True)
    print(f"Mood: {args.mood}")
    print(f"Description: {args.description or '(none)'}")
    asyncio.run(run_gemini_test(args.mood, args.description))


if __name__ == "__main__":
    main()
