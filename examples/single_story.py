import fire

from hackernews.client import HackerNewsClient


async def main(story_id: int, max_length: int = 80) -> None:
    async with HackerNewsClient() as client:
        story = await client.fetch_story(story_id=story_id, comment_depth=5)
        print(story.tree_string(max_length=max_length))


if __name__ == "__main__":
    fire.Fire(main)