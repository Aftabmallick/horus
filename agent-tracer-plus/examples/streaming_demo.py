"""Demonstrate auto-capture of streaming OpenAI calls."""
import asyncio
import agent_tracer_plus
from agent_tracer_plus import trace_agent, trace_step

agent_tracer_plus.init(service_name="streaming-demo", storage="sqlite://./streaming_traces.db", force=True)

@trace_agent(name="StreamingAgent")
async def streaming_agent(prompt: str):
    """Agent that uses streaming LLM calls."""
    import openai
    client = openai.AsyncOpenAI()
    
    assembled = []
    # This is auto-captured — streaming span with full token tracking
    async for chunk in await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    ):
        if chunk.choices and chunk.choices[0].delta.content:
            assembled.append(chunk.choices[0].delta.content)
            print(chunk.choices[0].delta.content, end="", flush=True)
    print()
    return "".join(assembled)

if __name__ == "__main__":
    asyncio.run(streaming_agent("Explain tracing in 2 sentences."))
    print("\nTrace saved. Run: agent-tracer-plus tail --storage sqlite://./streaming_traces.db")
