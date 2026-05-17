"""
Why not split by paragraph for each section?

Splitting only by paragraph can result in chunks that are too large, too small, or not semantically meaningful.
The hybrid method aims to create chunks that are:
More semantically coherent (using sentence similarity).
Respectful of document structure (sections, lists, code, tables).
Sized appropriately for downstream tasks (like embeddings or retrieval).
This approach improves retrieval quality and context preservation compared to naive paragraph splitting.
"""
from sentence_transformers import SentenceTransformer
from typing import List, Dict
from dataclasses import dataclass
from .Chunk import Chunk
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sklearn.metrics.pairwise import cosine_similarity


class HybridChunker:
    """
    Advanced hybrid chunking strategy combining:
    1. Semantic chunking (meaning-based boundaries)
    2. Document structure awareness (headers, sections)
    3. Content-type specific splitting (code, tables, text)
    4. Sliding window with overlap
    5. Parent-child relationships for context
    """

    def __init__(self,
                 base_chunk_size: int = 512,
                 overlap_size: int = 128,
                 semantic_threshold: float = 0.5,
                 min_chunk_size: int = 100,
                 max_chunk_size: int = 1000,
                 embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):

        self.base_chunk_size = base_chunk_size
        self.overlap_size = overlap_size
        self.semantic_threshold = semantic_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

        self.embedding_model = SentenceTransformer(embedding_model)

        self.separators = {
            'section':   ['\n## ', '\n### ', '\n#### ', '\n# '],
            'paragraph': ['\n\n\n', '\n\n'],
            'sentence':  ['. ', '! ', '? ', '.\n', '!\n', '?\n'],
            'clause':    [', ', '; ', ': '],
            'word':      [' '],
            'char':      [''],
        }

    def detect_content_type(self, text: str) -> str:
        if re.search(r'```[\w]*\n', text) or re.match(r'^\s{4,}', text, re.MULTILINE):
            return 'code'
        if '|' in text and text.count('|') > 4:
            lines = text.split('\n')
            if any('|' in line for line in lines[:3]):
                return 'table'
        if re.search(r'^\s*[-*•]\s', text, re.MULTILINE) or \
           re.search(r'^\s*\d+\.\s', text, re.MULTILINE):
            return 'list'
        return 'paragraph'

    def extract_sections(self, text: str) -> List[Dict]:
        sections = []
        header_pattern = r'^(#{1,6})\s+(.+)$'
        lines = text.split('\n')

        current_section = {'title': None, 'level': 0, 'start_idx': 0, 'content': []}

        for i, line in enumerate(lines):
            match = re.match(header_pattern, line)
            if match:
                if current_section['content']:
                    current_section['text'] = '\n'.join(current_section['content'])
                    sections.append(current_section.copy())
                current_section = {
                    'title':     match.group(2),
                    'level':     len(match.group(1)),
                    'start_idx': i,
                    'content':   [line],
                }
            else:
                current_section['content'].append(line)

        if current_section['content']:
            current_section['text'] = '\n'.join(current_section['content'])
            sections.append(current_section)

        if not sections:
            sections.append({
                'title': None, 'level': 0, 'start_idx': 0,
                'text': text, 'content': lines,
            })

        return sections

    def semantic_split(self, text: str, sentences: List[str]) -> List[int]:
        if len(sentences) <= 1:
            return []
        embeddings   = self.embedding_model.encode(sentences)
        split_points = []
        for i in range(len(sentences) - 1):
            sim = cosine_similarity(
                embeddings[i].reshape(1, -1),
                embeddings[i + 1].reshape(1, -1),
            )[0][0]
            if sim < self.semantic_threshold:
                split_points.append(i + 1)
        return split_points

    def split_by_content_type(self, text: str, content_type: str) -> List[str]:
        if content_type == 'code':
            return self._split_code(text)
        elif content_type == 'table':
            return [text] if len(text) < self.max_chunk_size else self._split_table(text)
        elif content_type == 'list':
            return self._split_list(text)
        else:
            return self._split_paragraph(text)

    def _split_code(self, text: str) -> List[str]:
        patterns = [r'\ndef ', r'\nclass ', r'\nfunction ', r'\n\n']
        chunks = [text]
        for pattern in patterns:
            new_chunks = []
            for chunk in chunks:
                parts = re.split(f'({pattern})', chunk)
                for i in range(0, len(parts), 2):
                    new_chunks.append(
                        parts[i] + parts[i + 1] if i + 1 < len(parts) else parts[i]
                    )
            chunks = [c for c in new_chunks if c.strip()]
        return chunks

    def _split_table(self, text: str) -> List[str]:
        lines  = text.split('\n')
        header = lines[:2]
        rows   = lines[2:]
        if len(text) <= self.max_chunk_size:
            return [text]
        chunks, current_rows, current_size = [], [], len('\n'.join(header))
        for row in rows:
            if current_size + len(row) > self.max_chunk_size and current_rows:
                chunks.append('\n'.join(header + current_rows))
                current_rows = [row]
                current_size = len('\n'.join(header)) + len(row)
            else:
                current_rows.append(row)
                current_size += len(row)
        if current_rows:
            chunks.append('\n'.join(header + current_rows))
        return chunks

    def _split_list(self, text: str) -> List[str]:
        lines, chunks, current_chunk, current_size = text.split('\n'), [], [], 0
        for line in lines:
            is_item = re.match(r'^\s*[-*•]\s', line) or re.match(r'^\s*\d+\.\s', line)
            if is_item and current_size + len(line) > self.base_chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = ([current_chunk[-1], line] if current_chunk else [line])
                current_size  = sum(len(s) for s in current_chunk)
            else:
                current_chunk.append(line)
                current_size += len(line)
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        return chunks

    def _split_paragraph(self, text: str) -> List[str]:
        sentences      = re.split(r'(?<=[.!?])\s+', text)
        semantic_breaks = self.semantic_split(text, sentences)
        chunks, current_chunk, current_size = [], [], 0
        for i, sentence in enumerate(sentences):
            should_split = (
                current_size + len(sentence) > self.base_chunk_size and
                (i in semantic_breaks or current_size > self.min_chunk_size)
            )
            if should_split and current_chunk:
                chunks.append(' '.join(current_chunk))
                overlap_start = max(0, len(current_chunk) - 2)
                current_chunk = current_chunk[overlap_start:] + [sentence]
                current_size  = sum(len(s) for s in current_chunk)
            else:
                current_chunk.append(sentence)
                current_size += len(sentence)
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        return chunks

    def create_parent_child_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        parent_size    = self.base_chunk_size * 2
        text           = ' '.join(c.text for c in chunks)
        parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_size, chunk_overlap=self.overlap_size * 2
        )
        parent_texts   = parent_splitter.split_text(text)
        parent_id_offset = len(chunks)

        for i, parent_text in enumerate(parent_texts):
            parent_chunk = Chunk(
                text=parent_text,
                chunk_id=parent_id_offset + i,
                start_char=0,
                end_char=len(parent_text),
                chunk_type='parent',
            )
            for child in chunks:
                if child.text in parent_text:
                    parent_chunk.child_chunk_ids.append(child.chunk_id)
                    child.parent_chunk_id = parent_chunk.chunk_id
            chunks.append(parent_chunk)

        return chunks

    def chunk_document(self, text: str) -> List[Chunk]:
        """
        Main chunking pipeline:
        1. Extract sections
        2. Detect content type per section
        3. Apply content-specific splitting
        4. Create parent-child relationships
        5. Add metadata
        """
        all_chunks, chunk_id, char_position = [], 0, 0
        sections = self.extract_sections(text)

        for section in sections:
            section_text  = section['text']
            section_title = section.get('title')
            content_type  = self.detect_content_type(section_text)
            text_chunks   = self.split_by_content_type(section_text, content_type)

            for text_chunk in text_chunks:
                if len(text_chunk.strip()) < self.min_chunk_size:
                    continue
                all_chunks.append(Chunk(
                    text=text_chunk,
                    chunk_id=chunk_id,
                    start_char=char_position,
                    end_char=char_position + len(text_chunk),
                    section_title=section_title,
                    chunk_type=content_type,
                ))
                chunk_id      += 1
                char_position += len(text_chunk)

        all_chunks = self.create_parent_child_chunks(all_chunks)

        for chunk in all_chunks:
            chunk.semantic_density = self._calculate_semantic_density(chunk.text)

        return all_chunks

    def _calculate_semantic_density(self, text: str) -> float:
        words = text.lower().split()
        if not words:
            return 0.0
        density      = len(set(words)) / len(words)
        length_bonus = min(len(text) / self.base_chunk_size, 1.0) * 0.2
        return min(density + length_bonus, 1.0)