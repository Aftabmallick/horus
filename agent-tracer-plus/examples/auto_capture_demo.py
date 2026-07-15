"""Example of zero-code auto-capture with OpenAI."""

import asyncio
import os

# 1. ONE LINE INIT - Everything after this is automatically traced
import agent_tracer_plus

agent_tracer_plus.init(service_name="auto-capture-demo")

# 2. Standard OpenAI code (no changes needed)
import openai


async def main():
    if not os.environ.get("OPENAI_API_KEY"):
        print("Please set OPENAI_API_KEY to run this example")
        return

    print("Calling OpenAI...")
    client = openai.AsyncClient()

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": "Tell me a very short joke about observability."}
        ]
    )

    print("\nResponse:", response.choices[0].message.content)
    print("\nDone! Check agent_traces.db for the automatically captured trace, including token usage and costs.")

if __name__ == "__main__":
    asyncio.run(main())
