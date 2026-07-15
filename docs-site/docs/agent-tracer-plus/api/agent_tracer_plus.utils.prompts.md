# Module: `agent_tracer_plus.utils.prompts`

Dynamic Prompt Management.

## Class `PromptManager`
Fetches and caches prompts dynamically from the Agent Tracer Platform.

### `def __init__(self, api_url, api_key)`
### `def get_prompt(self, name, fallback)`
Fetch a prompt by name. Returns the fallback if the fetch fails.

## Function `init_prompt_manager(api_url, api_key)`
## Function `get_prompt(name, fallback)`
Global helper to fetch a prompt.

