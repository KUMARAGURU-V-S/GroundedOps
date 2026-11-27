"""
Document Chunker for GroundedOps.
Splits technical documentation, runbooks, and Markdown files into semantically
coherent chunks with section tracking and overlap for embedding and retrieval.
"""

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass
class DocumentChunk:
    """Represents an indexed chunk of documentation."""

    chunk_id: str
    doc_id: str
    doc_title: str
    section: str
    content: str
    chunk_index: int
    char_start: int
    char_end: int
    token_count_est: int
    content_hash: str
    metadata: Dict[str, str]

    def to_dict(self) -> Dict:
        return asdict(self)


class MarkdownChunker:
    """
    Splits text/markdown documents into overlapping chunks while preserving
    heading hierarchies and logical paragraphs.
    """

    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 150,
        min_chunk_size: int = 20,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate (~4 chars per token)."""
        return max(1, len(text) // 4)

    def _compute_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _extract_title(self, text: str, fallback: str) -> str:
        """Extract first H1 markdown heading or fallback to document name."""
        match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return fallback

    def chunk_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> List[DocumentChunk]:
        """
        Chunk a document into sequential segments with section awareness.
        """
        if not content or not content.strip():
            return []

        metadata = metadata or {}
        doc_title = self._extract_title(content, fallback=doc_id)

        # Parse sections separated by markdown headings (H1 - H6)
        lines = content.split("\n")
        sections: List[Dict[str, str]] = []
        current_section = "Overview"
        current_buffer: List[str] = []

        header_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

        for line in lines:
            header_match = header_pattern.match(line.strip())
            if header_match:
                # If buffer has accumulated content, flush previous section
                if current_buffer:
                    section_text = "\n".join(current_buffer).strip()
                    if section_text:
                        sections.append(
                            {"section": current_section, "text": section_text}
                        )
                    current_buffer = []
                current_section = header_match.group(2).strip()
            else:
                current_buffer.append(line)

        if current_buffer:
            section_text = "\n".join(current_buffer).strip()
            if section_text:
                sections.append({"section": current_section, "text": section_text})

        # If no markdown structure was found, treat as single section
        if not sections:
            sections = [{"section": "Content", "text": content.strip()}]

        chunks: List[DocumentChunk] = []
        chunk_index = 0
        global_char_offset = 0

        for sec in sections:
            sec_name = sec["section"]
            sec_text = sec["text"]
            sec_len = len(sec_text)

            if sec_len == 0:
                continue

            # If section fits within chunk_size
            if sec_len <= self.chunk_size:
                if sec_len >= self.min_chunk_size or not chunks:
                    chunk_id = f"{doc_id}#c{chunk_index}"
                    chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            doc_id=doc_id,
                            doc_title=doc_title,
                            section=sec_name,
                            content=sec_text,
                            chunk_index=chunk_index,
                            char_start=global_char_offset,
                            char_end=global_char_offset + sec_len,
                            token_count_est=self._estimate_tokens(sec_text),
                            content_hash=self._compute_hash(sec_text),
                            metadata={**metadata, "section": sec_name},
                        )
                    )
                    chunk_index += 1
                global_char_offset += sec_len + 1
                continue

            # Section is larger than chunk_size -> sliding window with overlap
            start = 0
            while start < sec_len:
                end = min(start + self.chunk_size, sec_len)

                # Try to break cleanly at newline or space
                if end < sec_len:
                    newline_pos = sec_text.rfind("\n", start + self.chunk_size // 2, end)
                    if newline_pos != -1:
                        end = newline_pos + 1
                    else:
                        space_pos = sec_text.rfind(" ", start + self.chunk_size // 2, end)
                        if space_pos != -1:
                            end = space_pos + 1

                chunk_text = sec_text[start:end].strip()
                if len(chunk_text) >= self.min_chunk_size or start == 0:
                    chunk_id = f"{doc_id}#c{chunk_index}"
                    chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            doc_id=doc_id,
                            doc_title=doc_title,
                            section=sec_name,
                            content=chunk_text,
                            chunk_index=chunk_index,
                            char_start=global_char_offset + start,
                            char_end=global_char_offset + end,
                            token_count_est=self._estimate_tokens(chunk_text),
                            content_hash=self._compute_hash(chunk_text),
                            metadata={**metadata, "section": sec_name},
                        )
                    )
                    chunk_index += 1

                if end >= sec_len:
                    break

                step = max(1, (end - start) - self.chunk_overlap)
                start += step

            global_char_offset += sec_len + 1

        return chunks
