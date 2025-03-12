import asyncio

from agents import Agent, Runner, WebSearchTool, trace


async def main():
    agent = Agent(
        name="Web searcher",
        instructions="You are a helpful agent.",
        tools=[WebSearchTool(user_location={"type": "approximate", "city": "Manhattan"})],
    )

    with trace("Web search example"):
        result = await Runner.run(
            agent,
            "推荐一些曼哈顿的人均50刀以下的评分高的可以打卡的特色美食",
        )
        print(result.final_output)
        # The New York Giants are reportedly pursuing quarterback Aaron Rodgers after his ...


if __name__ == "__main__":
    asyncio.run(main())