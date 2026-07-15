# Module: `agent_tracer_plus.intelligence.hallucination`

Hallucination and Faithfulness scoring engines.

## Class `ClaimScore`
Evaluation of a single factual claim.

## Class `HallucinationScore`
Overall hallucination score for a generated span against context.

## Class `HallucinationEngine`
## Class `LLMJudgeEngine`
Uses an LLM to extract claims and verify entailment.

### `def __init__(self, model, api_key)`
## Class `CrossEncoderEngine`
Uses a local NLI model (e.g. cross-encoder/nli-deberta-v3-small) to check entailment.

### `def __init__(self, model_name)`
### `def _load_model(self)`
