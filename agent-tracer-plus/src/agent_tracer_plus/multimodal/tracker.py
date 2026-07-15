"""Multi-modal tracing for vision, audio, and document inputs.

Detects and records non-text content (images, audio, documents) in LLM calls
without storing the actual blobs — only metadata (hash, type, dimensions, URL).

Usage::

    from agent_tracer_plus.multimodal.tracker import MultiModalTracker

    tracker = MultiModalTracker()
    refs = tracker.extract_from_messages(messages)
    # refs: [{"type": "image", "hash": "abc123", "url": "...", "mime_type": "image/jpeg"}]
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agent_tracer_plus.multimodal")


class MultiModalRef:
    """Reference to a non-text modality in a trace — metadata only, no blobs."""

    __slots__ = ("ref_type", "url", "content_hash", "mime_type", "width", "height", "size_bytes", "format_hint")

    def __init__(
        self,
        ref_type: str,  # "image" | "audio" | "document" | "video"
        url: Optional[str] = None,
        content_hash: Optional[str] = None,
        mime_type: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        size_bytes: Optional[int] = None,
        format_hint: Optional[str] = None,
    ) -> None:
        self.ref_type = ref_type
        self.url = url
        self.content_hash = content_hash
        self.mime_type = mime_type
        self.width = width
        self.height = height
        self.size_bytes = size_bytes
        self.format_hint = format_hint
        self.estimated_tokens = None
        self.pii_redacted = False

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__slots__ if getattr(self, k) is not None}


class MultiModalTracker:
    """Extracts and records multimodal content metadata from LLM message payloads.

    Integrates with the OpenAI message format (which is also used by Anthropic,
    Gemini, and others).
    """

    def extract_from_messages(self, messages: List[Dict[str, Any]]) -> List[MultiModalRef]:
        """Scan a messages list for non-text content parts and return metadata refs.

        Args:
            messages: List of OpenAI-style message dicts.

        Returns:
            List of MultiModalRef objects (empty if no non-text content found).
        """
        refs: List[MultiModalRef] = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    ref = self._extract_part(part)
                    if ref:
                        refs.append(ref)
            # Plain string content — no multimodal refs
        return refs

    def _extract_part(self, part: Dict[str, Any]) -> Optional[MultiModalRef]:
        """Extract a MultiModalRef from a single content part dict."""
        part_type = part.get("type", "")

        if part_type == "image_url":
            image_url = part.get("image_url", {})
            url = image_url.get("url", "") if isinstance(image_url, dict) else str(image_url)
            detail = image_url.get("detail", "auto") if isinstance(image_url, dict) else "auto"

            # Detect base64 embedded images
            mime_type = None
            content_hash = None
            width = None
            height = None
            size_bytes = None

            if url.startswith("data:"):
                # data:image/jpeg;base64,<data>
                try:
                    header, b64data = url.split(",", 1)
                    mime_type = header.split(":")[1].split(";")[0]
                    size_bytes = len(b64data) * 3 // 4  # approx decoded size
                    content_hash = hashlib.sha256(b64data.encode()).hexdigest()[:16]

                    # Try to get image dimensions if PIL is available
                    width, height = self._get_image_dimensions_from_b64(b64data, mime_type)
                    url = f"[base64:{mime_type}]"  # Don't store the full base64
                except Exception:
                    pass
            else:
                # URL reference — extract filename extension as hint
                mime_type = self._guess_mime_from_url(url)

            # Calculate Image Tokens based on OpenAI math
            tokens = self._calculate_image_tokens(width, height, detail)
            
            ref = MultiModalRef(
                ref_type="image",
                url=url if not url.startswith("[base64") else None,
                content_hash=content_hash,
                mime_type=mime_type,
                width=width,
                height=height,
                size_bytes=size_bytes,
                format_hint=detail,
            )
            ref.estimated_tokens = tokens
            return ref

        elif part_type == "input_audio":
            audio = part.get("input_audio", {})
            return MultiModalRef(
                ref_type="audio",
                mime_type=f"audio/{audio.get('format', 'unknown')}",
                content_hash=hashlib.sha256(
                    str(audio.get("data", "")).encode()
                ).hexdigest()[:16] if audio.get("data") else None,
            )

        elif part_type == "document":
            doc = part.get("document", {})
            return MultiModalRef(
                ref_type="document",
                mime_type=doc.get("media_type"),
                format_hint=doc.get("type"),
            )

        return None

    def _get_image_dimensions_from_b64(
        self, b64data: str, mime_type: str
    ) -> tuple[Optional[int], Optional[int]]:
        """Attempt to extract image dimensions using PIL if available."""
        try:
            import base64
            import io
            from PIL import Image
            raw = base64.b64decode(b64data + "==")
            
            # Optional PII Redaction
            # self._redact_image_pii(raw)
            
            img = Image.open(io.BytesIO(raw))
            return img.width, img.height
        except Exception:
            return None, None
            
    def _calculate_image_tokens(self, width: Optional[int], height: Optional[int], detail: str) -> Optional[int]:
        """Calculate LLM token cost for an image based on dimensions and detail level."""
        if not width or not height:
            return 85 # fallback low res

        if detail == "low":
            return 85

        # high detail math
        # 1. scale to fit 2048x2048
        # 2. scale such that shortest side is 768
        # 3. count 512x512 tiles, 170 tokens each, + 85 base
        import math
        
        w, h = width, height
        if max(w, h) > 2048:
            ratio = 2048 / max(w, h)
            w = int(w * ratio)
            h = int(h * ratio)
            
        if min(w, h) > 768:
            ratio = 768 / min(w, h)
            w = int(w * ratio)
            h = int(h * ratio)
            
        tiles_w = math.ceil(w / 512)
        tiles_h = math.ceil(h / 512)
        
        return (tiles_w * tiles_h * 170) + 85
        
    def _redact_image_pii(self, raw_bytes: bytes) -> bytes:
        """Run OCR and blur bounding boxes containing PII."""
        try:
            import pytesseract
            import cv2
            import numpy as np
            import re
            
            nparr = np.frombuffer(raw_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Run OCR
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            
            # Simple regex for Credit Cards and SSN
            patterns = [
                r"\b(?:\d[ -]*?){13,16}\b", # CC
                r"\b\d{3}-\d{2}-\d{4}\b"    # SSN
            ]
            
            for i in range(len(data['text'])):
                text = data['text'][i]
                for p in patterns:
                    if re.search(p, text):
                        (x, y, w, h) = (data['left'][i], data['top'][i], data['width'][i], data['height'][i])
                        # Blur the region
                        roi = img[y:y+h, x:x+w]
                        roi = cv2.GaussianBlur(roi, (23, 23), 30)
                        img[y:y+h, x:x+w] = roi
                        
            success, encoded_img = cv2.imencode('.png', img)
            if success:
                return encoded_img.tobytes()
        except ImportError:
            logger.debug("cv2 or pytesseract not installed. Skipping PII redaction.")
        except Exception as e:
            logger.debug(f"PII redaction failed: {e}")
            
        return raw_bytes

    def _guess_mime_from_url(self, url: str) -> Optional[str]:
        """Guess MIME type from URL extension."""
        ext_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".webp": "image/webp", ".svg": "image/svg+xml",
            ".pdf": "application/pdf",
            ".mp3": "audio/mpeg", ".wav": "audio/wav",
            ".mp4": "video/mp4", ".webm": "video/webm",
        }
        lower_url = url.lower().split("?")[0]  # Strip query params
        for ext, mime in ext_map.items():
            if lower_url.endswith(ext):
                return mime
        return None
