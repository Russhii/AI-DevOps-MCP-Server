import asyncio
import json

from client import connect, result_to_dict


async def main():
    async with connect() as client:
        result = await client.call_tool("get_tasks", {})
        print(json.dumps(result_to_dict(result), indent=2))


asyncio.run(main())