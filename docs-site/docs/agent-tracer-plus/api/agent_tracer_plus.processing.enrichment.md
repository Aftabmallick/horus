# Module: `agent_tracer_plus.processing.enrichment`

Enrichment processing for traces.

## Class `PromptVersionTracker`
Tracks prompt templates and versions them.

### `def __init__(self)`
### `def _hash_prompt(self, template)`
### `def get_version(self, template)`
Get or create a version hash for a prompt template.

## Class `TraceEnricher`
Enriches traces with derived data.

### `def __init__(self)`
### `def enrich_span(self, span)`
Enrich a single span in-place.

### `def enrich_trace(self, trace, spans)`
Enrich a trace and its spans.

