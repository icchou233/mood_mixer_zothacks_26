import argparse
import asyncio
import json

from src.ai_talk import send_to_gemini
from src.api import SongRequest


async def run_gemini_test(request: SongRequest) -> None:
    result = await send_to_gemini(request.mood, request.numSongs)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a sample song request to Gemini and print its response."
    )
    parser.add_argument("--mood", default="relaxed")
    parser.add_argument("--num-songs", type=int, default=5)
    args = parser.parse_args()

    request = SongRequest(mood=args.mood, numSongs=args.num_songs)
    asyncio.run(run_gemini_test(request))


if __name__ == "__main__":
    main()
