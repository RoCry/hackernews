import asyncio
from hackernews.client import HackerNewsClient


async def fetch_top_stories(top_n: int = 10, comment_depth: int = 2):
    async with HackerNewsClient() as client:
        return await client.fetch_top_stories(top_n, comment_depth)


def main() -> None:
    response = asyncio.run(fetch_top_stories(2))
    for story in response.stories:
        print(story.tree_string())


if __name__ == "__main__":
    main()
