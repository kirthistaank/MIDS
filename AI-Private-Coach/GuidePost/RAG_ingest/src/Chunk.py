from typing import Optional,List
from dataclasses import dataclass
"""
Why we use @dataclass 

    @dataclass automatically generates:
    __init__
    __repr__
    __eq__
    and more
"""
@dataclass
class Chunk:
    """Enhanced chunk with metadata"""
    text: str
    chunk_id: int
    start_char: int
    end_char: int
    section_title: Optional[str] = None
    chunk_type: str = "paragraph"  # paragraph, code, table, list
    semantic_density: float = 0.0
    parent_chunk_id: Optional[int] = None
    child_chunk_ids: List[int] = None
    
    def __post_init__(self):
        if self.child_chunk_ids is None:
            self.child_chunk_ids = []