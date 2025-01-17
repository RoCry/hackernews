import fire

from hackernews.client import HackerNewsClient


async def main(story_id: int, fetch_comment_levels_count: int = 1, max_length: int = 80) -> None:
    async with HackerNewsClient(cache_path="hn_cache.sqlite3") as client:
        story = await client.fetch_story(story_id=story_id, fetch_comment_levels_count=fetch_comment_levels_count)
        print(story.tree_string(max_length=max_length))


if __name__ == "__main__":
    fire.Fire(main)
