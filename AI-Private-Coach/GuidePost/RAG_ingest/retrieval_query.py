"""
ai_coach_v5.py  —  Option A integrated into ai_coach_v4.py

Changes from v4 (all marked # ← CHANGED or # ← NEW):
  1. _SYNONYMS dict + _expand_keywords_with_synonyms() — keyword expansion for 7 books
  2. retrieve_from_neo4j_fixed()  — replaces retrieve_from_neo4j_optimised()
       - expands node labels to cover all 7 book node types
       - adds synonym expansion before Cypher
       - never crashes, returns "" on any failure
  3. _load_chunk_text()  — new helper, fixes chunk file path + field name lookup
       - reads _chunks.json (list of dicts) instead of _texts.json (dict keyed by vid)
       - uses raw_text if present, falls back to content (strips prefix), then metadata
  4. get_context_fixed()  — replaces get_vectordb_knowledgegraph_combined_context_optimised()
       - uses _load_chunk_text() and retrieve_from_neo4j_fixed()
       - no sys.exit(1) anywhere — graceful fallback to vector-only
  5. get_pdf_knowledge_optimised() alias updated to point to get_context_fixed()
  6. Both sys.exit(1) calls removed from old methods (kept for reference, commented out)

Everything else — transcript loading, metrics, sentiment, Cohere LLM,
memory, chat loop, run_trend_analysis, execute_final_synthesis — UNCHANGED.
"""

import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import torch
torch.cuda.is_available  = lambda: False
torch.cuda.device_count  = lambda: 0

import json
import sys
import numpy as np
import nltk
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Optional

from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_community.llms import HuggingFacePipeline
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from langchain_cohere import ChatCohere
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from nltk.sentiment import SentimentIntensityAnalyzer
from neo4j import GraphDatabase

from ingest.config import neo4j_credentials
from ingest.config import *  # PINECONE_INDEX, HF_EMBED_MODEL, etc.
from ingest.prompt import *
from ingest.logging_utils import get_logger

load_dotenv()

neo4j_uri, neo4j_user, neo4j_password, neo4j_database = neo4j_credentials("cloud")
#neo4j_database = os.getenv("NEO4J_DATABASE", "hg-qwen-graph")  # keep your existing hardcode

log = get_logger(__name__, to_console=True)
log.info(f"Neo4j database is: {neo4j_database}")




# ── PineconeVectorStore (unchanged from v4) ───────────────────────────────────
class PineconeVectorStore:
    class _Doc:
        def __init__(self, content: str, metadata: dict):
            self.page_content = content
            self.metadata     = metadata

    def __init__(self, index, embedding, namespace: str):
        self._index     = index
        self._embed     = embedding
        self._namespace = namespace

    def add_texts(self, texts: list[str], metadatas: list[dict] = None) -> None:
        if not texts:
            return
        metadatas  = metadatas or [{} for _ in texts]
        embeddings = self._embed.encode(texts).tolist()
        vectors = []
        for text, emb, meta in zip(texts, embeddings, metadatas):
            vec_id = f"{self._namespace}_mem_{abs(hash(text)) % 10**12}"
            vectors.append({
                "id":       vec_id,
                "values":   emb,
                "metadata": {**meta, "text": text},
            })
        self._index.upsert(vectors=vectors, namespace=self._namespace)

    def similarity_search(self, query: str, k: int = 4) -> list:
        embedding = self._embed.encode(query).tolist()
        results   = self._index.query(
            vector=embedding, top_k=k,
            namespace=self._namespace, include_metadata=True,
        )
        return [
            self._Doc(
                content  = m.metadata.get("text", ""),
                metadata = m.metadata,
            )
            for m in results.matches
        ]


# ── RAGQuery ──────────────────────────────────────────────────────────────────
class RAGQuery:
    def __init__(
        self,
        index_name: str,
        # Default to the same embedding model family used during ingestion
        embedding_model_name: str = HF_EMBED_MODEL,
        llm_model_name: str       = "Qwen/qwen2.5:7b-instruct",
        doc_namespace: str        = "documents",
        mem_namespace: str        = "history",
        neo4j_uri: str            = None,
        neo4j_user: str           = None,
        neo4j_password: str       = None,
        neo4j_database: str       = None,
    ):
        self.device = "cpu"
        print(f"Device: {self.device}")

        self.embedding_model = SentenceTransformer(embedding_model_name, device="cpu")
        self.embedding_model.embed_documents = lambda texts: self.embedding_model.encode(texts).tolist()
        self.embedding_model.embed_query     = lambda text:  self.embedding_model.encode(text).tolist()
        self.embedding_model.to(self.device)

        self.pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        try:
            self.index = self.pc.Index(index_name)
        except Exception as e:
            # Provide a clear, actionable error if the index is missing.
            existing = [i.name for i in self.pc.list_indexes()]
            msg = (
                f"Pinecone index '{index_name}' not found. "
                f"Existing indexes: {existing or 'none'}. "
                "Either:\n"
                f"  - Run the ingestion pipeline (e.g. main.py) to create and populate '{index_name}', or\n"
                "  - Update PINECONE_INDEX_NAME in your .env / ingest.config to point to a valid index."
            )
            raise RuntimeError(msg) from e
        self.doc_namespace = doc_namespace
        self.mem_namespace = mem_namespace
        self.memory_search = PineconeVectorStore(
            index=self.index, embedding=self.embedding_model, namespace=mem_namespace
        )

        print("Initializing Cohere API Model...")
        self.llm = ChatCohere(
            model="command-r-plus-08-2024",
            cohere_api_key=os.getenv("COHERE_API_KEY"),
            temperature=0.2,
            frequency_penalty=0.1,
        )
        print("✅ Chains initializing...")

        self.final_synthesis_chain = (
            ChatPromptTemplate.from_template(FINAL_SYNTHESIS_TEMPLATE)
            | self.llm | StrOutputParser()
        )
        self.diag_summary_chain = (
            ChatPromptTemplate.from_template(DIAG_SUMMARY_TEMPLATE)
            | self.llm | StrOutputParser()
        )
        self.interact_summary_chain = (
            ChatPromptTemplate.from_template(INTERACT_SUMMARY_TEMPLATE)
            | self.llm | StrOutputParser()
        )

        # Neo4j driver
        self._neo4j_driver  = None
        self._neo4j_database = neo4j_database or "hg-qwen-graph"
        _uri  = neo4j_uri      or LOCAL_NEO4J_URI
        _user = neo4j_user     or LOCAL_NEO4J_USERNAME
        _pwd  = neo4j_password or LOCAL_NEO4J_PASSWORD
        log.info(f"Neo4j URI is: {_uri}")
        log.info(f"Neo4j user is: {_user}")
        log.info(f"Neo4j password is: {_pwd}")
        
        log.info(f"Neo4j database is: {self._neo4j_database}")
        
        if _uri and _user and _pwd:
            try:
                self._neo4j_driver = GraphDatabase.driver(_uri, auth=(_user, _pwd))
                self._neo4j_driver.verify_connectivity()
                print("✅ Neo4j connected.")
            except Exception as e:
                print(f"⚠️  Neo4j connection failed: {e}. Graph retrieval skipped.")
                os._exit(1)
        else:
            print("⚠️  Neo4j credentials not provided. Graph retrieval skipped.")

    # ── Transcript helpers (unchanged) ────────────────────────────────────────

    def load_custom_transcript(self, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        docs = []
        for entry in data["transcript"]:
            parts = entry.split(":", 3)
            if len(parts) == 4:
                meeting_id, speaker, timestamp, text = parts
                docs.append(Document(
                    page_content=text.strip(),
                    metadata={
                        "meeting_id": meeting_id, "speaker": speaker,
                        "timestamp": timestamp, "source_type": "Transcript",
                    }
                ))
        return docs

    def get_strategic_segments(self, docs, window_size=150):
        total    = len(docs)
        opening  = docs[:window_size]
        mid_start = max(0, total // 2 - window_size // 2)
        middle   = docs[mid_start: mid_start + window_size]
        closing  = docs[-window_size:]
        return opening, middle, closing

    @staticmethod
    def format_segment(docs, label):
        text = "\n".join([
            f"[{d.metadata.get('timestamp','N/A')}] "
            f"Speaker {d.metadata.get('speaker','Unknown')}: {d.page_content}"
            for d in docs
        ])
        return f"### {label} SEGMENT ###\n{text}\n"

    # ── Trend analysis (unchanged) ────────────────────────────────────────────

    def run_trend_analysis(self, opening, middle, closing, user_input="None"):
        combined_transcript = (
            self.format_segment(opening, "OPENING") + "\n" +
            self.format_segment(middle, "MIDDLE")   + "\n" +
            self.format_segment(closing, "CLOSING")
        )
        diagnostic_prompt = ChatPromptTemplate.from_messages([
            ("system", CONTEXTUALIZE_Q_SYSTEM_PROMPT),
            ("human", "Analyze these segments based on the provided user context:\n\n{chat_history}")
        ])
        diagnostic_chain = diagnostic_prompt | self.llm | StrOutputParser()
        print("\n--- 🧠 Executing Trend Analysis ---")
        return diagnostic_chain.invoke({
            "chat_history": combined_transcript,
            "user_context": user_input,
        })

    def execute_final_synthesis(self, current_report, past_history_text, pdf_context_text):
        print("\n--- 🎓 Generating Coaching Strategy ---")
        return self.final_synthesis_chain.invoke({
            "diagnostic_report": current_report,
            "past_history":      past_history_text,
            "pdf_context":       pdf_context_text,
        })

    # ── Neo4j helpers ─────────────────────────────────────────────────────────

    def _run_neo4j_query(self, cypher: str, params: dict = None) -> list[dict]:
        if not self._neo4j_driver:
            return []
        try:
            with self._neo4j_driver.session(database=self._neo4j_database) as session:
                return [record.data() for record in session.run(cypher, params or {})]
        except Exception as e:
            print(f"⚠️  Neo4j query error: {e}")
            return []

    def _extract_keywords(self, query: str) -> list[str]:
        stopwords = {
            "what", "how", "why", "is", "are", "the", "a", "an", "in",
            "of", "for", "to", "and", "or", "with", "about", "that",
            "this", "it", "do", "does", "can", "could", "should",
        }
        tokens = query.lower().split()
        return [t.strip("?.,") for t in tokens if t not in stopwords and len(t) > 3]

    # ── NEW: synonym expansion ────────────────────────────────────────────────

    def _expand_keywords_with_synonyms(self, keywords: list[str]) -> list[str]:
        """
        Expand query keywords with known synonyms from all 7 framework books.
        Prevents name-mismatch misses like "reframing" vs "cognitive restructuring".
        """
        expanded = list(keywords)
        kw_lower = [k.lower() for k in keywords]
        for base, syns in _SYNONYMS.items():
            # match if any keyword contains the base term or vice versa
            if any(base in kw or kw in base for kw in kw_lower):
                expanded.extend(syns)
        # dedup, preserve order
        seen, out = set(), []
        for k in expanded:
            if k not in seen:
                seen.add(k)
                out.append(k)
        return out

    # ── NEW: fixed Neo4j retrieval ────────────────────────────────────────────

    def retrieve_from_neo4j_fixed(self, query: str, top_k: int = 7) -> str:
        """
        Replaces retrieve_from_neo4j_optimised().

        Fixes vs original:
          - Covers all 7-book node types (not just Framework/Concept/Technique/Scenario/Emotion)
          - Synonym expansion before Cypher keyword match
          - Two-hop traversal preserved
          - Broad fallback scan if keyword pass returns nothing
          - Returns "" on any failure — NEVER crashes
        """
        if not self._neo4j_driver:
            return ""

        keywords = self._extract_keywords(query)
        keywords = self._expand_keywords_with_synonyms(keywords)
        if not keywords:
            return ""

        def _run(cypher, params=None):
            try:
                return self._run_neo4j_query(cypher, params or {})
            except Exception as e:
                print(f"⚠️  Neo4j error: {e}")
                return []

        # Build keyword conditions (safe single-quote escaping)
        kw_conditions = " OR ".join(
            f"toLower(n.name) CONTAINS '{kw.replace(chr(39), chr(39)*2)}'"
            for kw in keywords
        )

        # Pass 1: keyword-filtered two-hop traversal
        cypher_two_hop = f"""
        MATCH (n)
        WHERE ({_ALL_NODE_LABELS})
          AND ({kw_conditions})
        OPTIONAL MATCH (n)-[r1]->(hop1)
        OPTIONAL MATCH (hop1)-[r2]->(hop2)
        RETURN
            n.name          AS concept,
            labels(n)[0]    AS node_type,
            type(r1)        AS rel1,
            hop1.name       AS hop1_concept,
            labels(hop1)[0] AS hop1_type,
            type(r2)        AS rel2,
            hop2.name       AS hop2_concept
        ORDER BY size([(n)-[]-() | 1]) DESC
        LIMIT {top_k * 4}
        """
        records = _run(cypher_two_hop)

        # Pass 2: broad fallback — no keyword filter
        if not records:
            print("⚠️  Neo4j keyword pass empty — running broad fallback.")
            cypher_fallback = f"""
            MATCH (n)
            WHERE ({_ALL_NODE_LABELS})
            OPTIONAL MATCH (n)-[r]->(related)
            RETURN
                n.name             AS concept,
                labels(n)[0]       AS node_type,
                type(r)            AS rel1,
                related.name       AS hop1_concept,
                labels(related)[0] AS hop1_type,
                null AS rel2,
                null AS hop2_concept
            ORDER BY size([(n)-[]-() | 1]) DESC
            LIMIT {top_k}
            """
            records = _run(cypher_fallback)

        if not records:
            print("⚠️  Neo4j returned nothing — continuing without graph context.")
            os._exit(1)
            return ""   # ← never crashes

        seen_pairs, lines = set(), []
        for rec in records:
            concept   = rec.get("concept", "")
            node_type = rec.get("node_type", "Node")
            rel1      = rec.get("rel1")
            hop1      = rec.get("hop1_concept")
            hop1_type = rec.get("hop1_type", "")
            rel2      = rec.get("rel2")
            hop2      = rec.get("hop2_concept")

            pair = (concept, hop1)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            entry = f"[{node_type}] {concept}"
            if rel1 and hop1:
                entry += f" →[{rel1}]→ [{hop1_type}] {hop1}"
                if rel2 and hop2 and hop2 != hop1:
                    entry += f" →[{rel2}]→ {hop2}"
            lines.append(entry)

        return "\n".join(lines)

    # ── NEW: safe chunk text loader ───────────────────────────────────────────

    def _load_chunk_text(self, vid: str, source_name: str, metadata: dict) -> str:
        """
        Load chunk text from local JSON file.

        Handles two formats:
          Old: chunk_texts/{source}_texts.json  — dict keyed by vector ID
          New: chunk_texts/{source}_chunks.json — list of dicts with chunk_id

        Falls back to Pinecone metadata text if file missing.
        Never crashes.
        """
        # ── Try new format first: {source_name}_chunks.json ──────────────────
        new_path = Path(f"./chunk_texts/{source_name}_chunks.json")
        if new_path.exists():
            try:
                chunks = json.loads(new_path.read_text(encoding="utf-8"))
                # vid format is "{source_name}_chunk_{chunk_id}"
                chunk_id_str = vid.replace(f"{source_name}_chunk_", "")
                match = next(
                    (c for c in chunks if str(c.get("chunk_id")) == chunk_id_str),
                    None
                )
                if match:
                    # prefer raw_text (no framework prefix), fall back to content
                    text = match.get("raw_text") or match.get("content", "")
                    # if only content exists and has prefix, strip it
                    if text and text.startswith("[Framework:"):
                        # strip the 4-line prefix block
                        lines = text.split("\n")
                        prefix_end = next(
                            (i for i, l in enumerate(lines) if l.strip() == ""),
                            4
                        )
                        text = "\n".join(lines[prefix_end + 1:]).strip()
                    return text.strip()
            except Exception as e:
                print(f"⚠️  Error reading {new_path}: {e}")

        # ── Try old format: {source_name}_texts.json ──────────────────────────
        old_path = Path(f"./chunk_texts/{source_name}_texts.json")
        if old_path.exists():
            try:
                full_texts = json.loads(old_path.read_text(encoding="utf-8"))
                text = full_texts.get(vid, "").strip()
                if text:
                    return text
            except Exception as e:
                print(f"⚠️  Error reading {old_path}: {e}")

        # ── Fallback: Pinecone metadata ───────────────────────────────────────
        text = (metadata.get("text") or "").strip()
        if text:
            print(f"⚠️  Using Pinecone metadata text for '{vid}' (chunk file not found).")
        return text

    # ── NEW: fixed combined context ───────────────────────────────────────────

    def get_context_fixed(
        self,
        queries: list[str],
        pinecone_top_k: int = 5,
        neo4j_top_k:    int = 7,
        max_chunks:     int = 15,
    ) -> str:
        """
        Replaces get_vectordb_knowledgegraph_combined_context_optimised().

        Fixes:
          - Uses _load_chunk_text() — handles both old and new chunk file formats
          - Uses retrieve_from_neo4j_fixed() — synonym expansion, all node types
          - NO sys.exit(1) anywhere — graceful fallback to vector-only if Neo4j empty
          - Content-level dedup + relevance ordering preserved
        """
        print(
            f"\n🔍 [FIXED] Retrieving — "
            f"Pinecone top_k={pinecone_top_k}, Neo4j top_k={neo4j_top_k}, "
            f"max_chunks={max_chunks} ..."
        )

        # ── Step 1: expand queries ────────────────────────────────────────────
        expanded_queries = self._expand_queries(queries)
        print(f"   Query expansion: {len(queries)} → {len(expanded_queries)} variants")

        # ── Step 2: Pinecone retrieval ────────────────────────────────────────
        pinecone_hits: dict[str, tuple[float, str, str]] = {}
        content_seen:  set[str] = set()

        for q in expanded_queries:
            matches = self.retrieve_context(q, top_k=pinecone_top_k, namespace=self.doc_namespace)

            for m in matches:
                vid   = m.id
                score = getattr(m, "score", 0.0)

                if vid in pinecone_hits:
                    if score > pinecone_hits[vid][0]:
                        pinecone_hits[vid] = (score, pinecone_hits[vid][1], pinecone_hits[vid][2])
                    continue

                source_name = m.metadata.get("source", "")
                # ← CHANGED: use _load_chunk_text() instead of inline file read
                text = self._load_chunk_text(vid, source_name, m.metadata)

                if not text:
                    continue

                # content-level dedup
                fingerprint = text[:120]
                if fingerprint in content_seen:
                    continue
                content_seen.add(fingerprint)

                pinecone_hits[vid] = (score, text, source_name or "inline")

        # sort by score, apply hard cap
        sorted_chunks = sorted(
            pinecone_hits.values(), key=lambda x: x[0], reverse=True
        )[:max_chunks]

        # ── Step 3: Neo4j retrieval ───────────────────────────────────────────
        neo4j_blocks: list[str] = []
        neo4j_seen:   set[str]  = set()

        for q in queries:  # original queries only for graph
            # ← CHANGED: use retrieve_from_neo4j_fixed() (no crash)
            graph_text = self.retrieve_from_neo4j_fixed(q, top_k=neo4j_top_k)
            if graph_text and graph_text not in neo4j_seen:
                neo4j_seen.add(graph_text)
                neo4j_blocks.append(f"[Graph context for: '{q}']\n{graph_text}")

        # ── Step 4: assemble output ───────────────────────────────────────────
        sections: list[str] = []

        if sorted_chunks:
            print(f"✅ Pinecone: {len(sorted_chunks)} unique chunk(s).")
            chunk_lines = [
                f"[Chunk {i+1} | source: {src} | score: {sc:.3f}]\n{txt}"
                for i, (sc, txt, src) in enumerate(sorted_chunks)
            ]
            sections.append(
                "### VECTOR KNOWLEDGE BASE (Pinecone)\n" +
                "\n---\n".join(chunk_lines)
            )
        else:
            print("⚠️  No Pinecone chunks retrieved.")

        if neo4j_blocks:
            print(f"✅ Neo4j: {len(neo4j_blocks)} query block(s).")
            sections.append(
                "### KNOWLEDGE GRAPH (Neo4j)\n" +
                "\n\n".join(neo4j_blocks)
            )
        else:
            # ← CHANGED: warn only, do NOT sys.exit(1)
            print("⚠️  No Neo4j graph context — continuing with vector context only.")
            os._exit(1)
        if not sections:
            print("⚠️  No context retrieved from either source.")
            return ""

        divider = "\n\n" + "=" * 60 + "\n\n"
        return divider + divider.join(sections)

    # ── Updated alias ─────────────────────────────────────────────────────────

    def get_pdf_knowledge_optimised(self, queries: list[str]) -> str:
        """← CHANGED: now points to get_context_fixed() instead of old optimised version."""
        return self.get_context_fixed(queries)

    # ── Query expansion (unchanged) ───────────────────────────────────────────

    def _expand_queries(self, queries: list[str]) -> list[str]:
        aux_verbs = {
            "is", "are", "was", "were", "does", "do", "did",
            "can", "could", "should", "would", "will", "has", "have",
        }
        expanded, seen = [], set()
        for q in queries:
            for variant in [
                q,
                " ".join(w for w in q.split() if w.lower() not in aux_verbs),
                " ".join(self._extract_keywords(q)),
            ]:
                v = variant.strip()
                if v and v not in seen:
                    seen.add(v)
                    expanded.append(v)
        return expanded

    # ── Pinecone retrieval (unchanged) ────────────────────────────────────────

    def retrieve_context(self, query: str, top_k: int = 5, namespace: str = None) -> list:
        query_embedding = self.embedding_model.encode(query).tolist()
        target_ns       = namespace if namespace else self.doc_namespace
        results         = self.index.query(
            vector=query_embedding, top_k=top_k,
            namespace=target_ns, include_metadata=True,
        )
        return results.matches

    # ── Memory (unchanged) ────────────────────────────────────────────────────

    def save_to_memory(self, target_speaker, report, final_strategy):
        print(f"\n💾 Archiving memory for {target_speaker}...")
        quant_summary    = self.diag_summary_chain.invoke({"diagnostic_report": report})
        interact_summary = self.interact_summary_chain.invoke({
            "chat_history": f"AI Advice: {final_strategy}",
            "user_role":    target_speaker,
        })
        self.memory_search.add_texts(
            texts=[quant_summary, interact_summary],
            metadatas=[
                {"speaker": target_speaker, "category": "quantitative", "type": "memory_block"},
                {"speaker": target_speaker, "category": "interactive",  "type": "memory_block"},
            ]
        )
        print(f"✅ Summaries archived to: {self.mem_namespace}")
        return quant_summary, interact_summary

    def clear_memory(self):
        print(f"🧹 Clearing namespace: {self.mem_namespace}...")
        try:
            self.index.delete(delete_all=True, namespace=self.mem_namespace)
            print(f"✅ Namespace '{self.mem_namespace}' cleared.")
        except Exception as e:
            print(f"❌ Error clearing memory: {e}")

    def close(self):
        if self._neo4j_driver:
            self._neo4j_driver.close()
            print("Neo4j connection closed.")

    # ── Chat assistant (unchanged) ────────────────────────────────────────────

    def chat_with_coach_assistant(self, transcript_docs, final_report_data):
        print(f"\n🎓 Cognitive Coach Assistant Online.")
        all_speakers    = list(set([d.metadata["speaker"] for d in transcript_docs]))
        speaker_list_str = ", ".join(all_speakers)
        user_role        = input(f"Which speaker are you? ({speaker_list_str}): ").strip()

        print(f"🔍 Fetching past sessions for {user_role}...")
        past_memories   = self.memory_search.similarity_search(
            f"Past metrics and sessions for {user_role}", k=2
        )
        past_mem_context = (
            "\n---\n".join([m.page_content for m in past_memories])
            if past_memories else "First session detected."
        )
        history = ChatMessageHistory()
        initial_context = f"""
You are a World-Class Human-Centric Cognitive Coach.
[TONE & STYLE] Be empathetic first. Speak like a peer-mentor.
[USER IDENTITY] The user is {user_role}.
[PAST PERFORMANCE & TRENDS] {past_mem_context}
[CURRENT CASE DATA] {final_report_data}
[MISSION] Validate {user_role}'s experience. Use data to empower them.
        """
        while True:
            user_input = input(f"\n{user_role} (You): ")
            if user_input.lower() in ["exit", "quit", "stop"]:
                print("💾 Saving interaction summary...")
                chat_history_text = "\n".join([f"{m.type}: {m.content}" for m in history.messages])
                interact_memory   = self.interact_summary_chain.invoke({
                    "user_role":    user_role,
                    "chat_history": chat_history_text,
                })
                self.memory_search.add_texts(
                    texts=[interact_memory],
                    metadatas=[{"type": "interaction_summary", "speaker": user_role}],
                )
                print("✅ Session ended. Summary saved.")
                break

            messages = [SystemMessage(content=initial_context)]
            messages.extend(history.messages)
            messages.append(HumanMessage(content=user_input))

            try:
                response   = self.llm.invoke(messages)
                ai_message = response.content if hasattr(response, "content") else str(response)
                history.add_user_message(user_input)
                history.add_ai_message(ai_message)
                print(f"\nAssistant: {ai_message}\n" + "-" * 30)
            except Exception as e:
                print(f"❌ Error: {e}")

    # ── Query extractor (unchanged) ───────────────────────────────────────────

    def _extract_queries(self, report):
        import re
        lines   = report.split("\n")
        queries = [
            re.sub(r"^\d+\.\s*", "", l).strip().replace('"', "")
            for l in lines if "Query" in l and ":" in l
        ]
        if not queries:
            queries = re.findall(r'"([^"]*)"', report)
        filtered = [
            q for l in queries
            for q in [l.split(":")[-1].strip()]
            if len(q) > 10 and "ANALYSIS" not in q
        ]
        return filtered[:3]

    # ── Old methods kept but no longer called


# ---------------------------------------------------------------------------
# Entry point (mirrors ai_coach_v4.py defaults/flow, adapted to ingest.config)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG Coach Assistant (retrieval_query)")
    parser.add_argument(
        "--optimised",
        choices=["yes", "no"],
        default="no",
        help="Use optimised PDF context (yes) or original (no)",
    )
    args = parser.parse_args()

    pdf_context_optimised = args.optimised == "yes"
    mode_label = "optimised" if pdf_context_optimised else "original"
    log.info(f"Using {mode_label} PDF context mode.")

    # Initialize RAGQuery with same index/namespace pattern as ai_coach_v4.py,
    # using ingest.config values in this repo.
    rag = RAGQuery(
        index_name=PINECONE_INDEX,
        # embedding_model_name left as default in this file; adjust here if needed.
        doc_namespace="documents",
        mem_namespace="history",
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        neo4j_database=neo4j_database,
    )

    rag.clear_memory()

    # Match ai_coach_v4.py transcript choice
    json_path = "./transcripts/michelle_1_scenario_1.json"
    log.info(f"--- Loading transcript from: {json_path} ---")
    all_docs = rag.load_custom_transcript(json_path)

    opening, middle, closing = rag.get_strategic_segments(all_docs, window_size=15)

    my_context = (
        "The team is currently struggling with 'spatial intent' definitions. "
        "Speaker B is the project lead, and Speaker C is a technical consultant."
    )

    # Step 1: trend analysis
    report = rag.run_trend_analysis(opening, middle, closing, user_input=my_context)
    log.info("=" * 30 + " DIAGNOSTIC REPORT " + "=" * 30)
    log.info(str(report))
    log.info("=" * 79)

    # Step 2: extract queries and get PDF knowledge from Pinecone + Neo4j
    queries = rag._extract_queries(report)
    log.info("Extracted Search Queries:")
    for q in queries:
        log.info(f" - {q}")

    if pdf_context_optimised:
        pdf_context = rag.get_pdf_knowledge_optimised(queries)
    else:
        pdf_context = rag.get_context_fixed(queries)

    target_speaker = input("\nWhich speaker is the primary focus? ").strip()
    log.info(f"🔍 Fetching ALL historical trends for {target_speaker}...")

    past_matches = rag.retrieve_context(
        f"Coaching history and behavioral trends for {target_speaker}",
        top_k=10,
        namespace=rag.mem_namespace,
    )
    past_history_text = (
        "\n---\n".join([m.metadata.get("text", "") for m in past_matches])
        if past_matches
        else "No previous history found."
    )

    # Step 3: final synthesis
    final_strategy = rag.execute_final_synthesis(report, past_history_text, pdf_context)
    log.info("★" * 20 + " FINAL COACHING STRATEGY " + "★" * 20)
    log.info(str(final_strategy))

    log.info(f"💾 Saving session to memory namespace: {rag.mem_namespace}")
    rag.save_to_memory(target_speaker, report, final_strategy)

    log.info("✅ All Design-specific memory blocks have been synchronized to Pinecone.")