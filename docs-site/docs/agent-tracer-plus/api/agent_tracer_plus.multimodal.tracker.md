# Module: `agent_tracer_plus.multimodal.tracker`

Multi-modal tracing for vision, audio, and document inputs.

Detects and records non-text content (images, audio, documents) in LLM calls
without storing the actual blobs — only metadata (hash, type, dimensions, URL).

Usage::

    from agent_tracer_plus.multimodal.tracker import MultiModalTracker

    tracker = MultiModalTracker()
    refs = tracker.extract_from_messages(messages)
    # refs: [&#123;"type": "image", "hash": "abc123", "url": "...", "mime_type": "image/jpeg"&#125;]

## Class `MultiModalRef`
Reference to a non-text modality in a trace — metadata only, no blobs.

### `def __init__(self, ref_type, url, content_hash, mime_type, width, height, size_bytes, format_hint)`
### `def to_dict(self)`
## Class `MultiModalTracker`
Extracts and records multimodal content metadata from LLM message payloads.

Integrates with the OpenAI message format (which is also used by Anthropic,
Gemini, and others).

### `def extract_from_messages(self, messages)`
Scan a messages list for non-text content parts and return metadata refs.

Args:
    messages: List of OpenAI-style message dicts.

Returns:
    List of MultiModalRef objects (empty if no non-text content found).

### `def _extract_part(self, part)`
Extract a MultiModalRef from a single content part dict.

### `def _get_image_dimensions_from_b64(self, b64data, mime_type)`
Attempt to extract image dimensions using PIL if available.

### `def _calculate_image_tokens(self, width, height, detail)`
Calculate LLM token cost for an image based on dimensions and detail level.

### `def _redact_image_pii(self, raw_bytes)`
Run OCR and blur bounding boxes containing PII.

### `def _guess_mime_from_url(self, url)`
Guess MIME type from URL extension.

