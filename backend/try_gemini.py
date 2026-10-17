import argparse
import asyncio
import json

from src.ai_talk import send_to_gemini


async def run_gemini_test(mood: str, description: str) -> None:
    result = await send_to_gemini(mood, description)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a sample song request to Gemini and print its response."
    )
    parser.add_argument("--mood", default="relaxed")
    parser.add_argument("--description", default="")
    args = parser.parse_args()

    asyncio.run(run_gemini_test(args.mood, args.description))


if __name__ == "__main__":
    main()
