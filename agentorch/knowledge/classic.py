from __future__ import annotations

import re
from typing import Any

from .base import ChunkingStrategy, Document, DocumentChunk


def _word_chunks(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return [text]
    size = max(chunk_size, 1)
    overlap = max(min(chunk_overlap, size - 1), 0)
    chunks: list[str] = []
    index = 0
    while index < len(words):
        chunk_words = words[index : index + size]
        chunks.append(" ".join(chunk_words))
        if index + size >= len(words):
            break
        index += max(size - overlap, 1)
    return chunks


class FixedTokenChunkingStrategy(ChunkingStrategy):
    def __init__(self, *, chunk_size: int = 600, chunk_overlap: int = 80) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def chunk(self, documents: list[Document]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for document in documents:
            for index, text in enumerate(_word_chunks(document.text, chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap), start=1):
                chunks.append(
                    DocumentChunk(
                        id=f"{document.id}:fixed:{index}",
                        document_id=document.id,
                        text=text,
                        metadata={**document.metadata, "chunking_strategy": "fixed_token_chunk"},
                    )
                )
        return chunks


class ParagraphChunkingStrategy(ChunkingStrategy):
    async def chunk(self, documents: list[Document]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for document in documents:
            paragraphs = [item.strip() for item in re.split(r"\n\s*\n", document.text) if item.strip()] or [document.text]
            for index, paragraph in enumerate(paragraphs, start=1):
                chunks.append(
                    DocumentChunk(
                        id=f"{document.id}:paragraph:{index}",
                        document_id=document.id,
                        text=paragraph,
                        metadata={**document.metadata, "chunking_strategy": "paragraph_chunk"},
                    )
                )
        return chunks


class HeadingAwareChunkingStrategy(ChunkingStrategy):
    async def chunk(self, documents: list[Document]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for document in documents:
            sections = re.split(r"(?m)^(#{1,6}\s+.+)$", document.text)
            if len(sections) == 1:
                sections = [document.text]
            heading = None
            index = 0
            for item in sections:
                if not item.strip():
                    continue
                if item.lstrip().startswith("#"):
                    heading = item.strip()
                    continue
                index += 1
                chunks.append(
                    DocumentChunk(
                        id=f"{document.id}:heading:{index}",
                        document_id=document.id,
                        text=item.strip(),
                        metadata={**document.metadata, "heading": heading, "chunking_strategy": "heading_aware_chunk"},
                    )
                )
        return chunks


class CodeSymbolChunkingStrategy(ChunkingStrategy):
    def __init__(self, *, window_lines: int = 20) -> None:
        self.window_lines = window_lines

    async def chunk(self, documents: list[Document]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        pattern = re.compile(r"^\s*(?:def|class|async def|function|interface|type)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
        for document in documents:
            lines = document.text.splitlines()
            matches = list(pattern.finditer(document.text))
            if not matches:
                chunks.append(
                    DocumentChunk(
                        id=f"{document.id}:code:1",
                        document_id=document.id,
                        text=document.text,
                        metadata={**document.metadata, "chunking_strategy": "code_symbol_chunk"},
                    )
                )
                continue
            for index, match in enumerate(matches, start=1):
                symbol = match.group(1)
                line_number = document.text[: match.start()].count("\n") + 1
                start_line = max(line_number - 1, 1)
                end_line = min(start_line + self.window_lines, len(lines))
                snippet = "\n".join(lines[start_line - 1 : end_line])
                chunks.append(
                    DocumentChunk(
                        id=f"{document.id}:code:{index}",
                        document_id=document.id,
                        text=snippet,
                        metadata={
                            **document.metadata,
                            "symbol": symbol,
                            "start_line": start_line,
                            "end_line": end_line,
                            "chunking_strategy": "code_symbol_chunk",
                        },
                    )
                )
        return chunks
