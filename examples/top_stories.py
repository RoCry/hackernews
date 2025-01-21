import asyncio
from hackernews.client import HackerNewsClient


async def fetch_top_stories(top_n: int = 10, fetch_comment_levels_count: int = 1):
    async with HackerNewsClient() as client:
        return await client.fetch_top_stories(top_n, fetch_comment_levels_count)


async def main():
    cache_db_path = "hn_cache.sqlite"
    async with HackerNewsClient(cache_db_path=cache_db_path) as client:
        response = await client.fetch_top_stories(top_n=10)
        for story in response.stories:
            print(story.tree_string())


if __name__ == "__main__":
    asyncio.run(main())
