import os
from pathlib import Path
import logging
import sys
from logging.handlers import RotatingFileHandler

os.environ["CUDA_VISIBLE_DEVICES"] = ""

import torch

torch.cuda.is_available = lambda : False
torch.cuda.device_count = lambda : 0

from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
import json

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from langchain_core.documents import Document 
# from pinecone import Pinecone # this is overwritten by defining Pi
#from langchain.prompts import PromptTemplate
from langchain_core.prompts import PromptTemplate

#from langchain.chains import LLMChain
#from langchain.chains import LLMChain
from langchain_community.llms import HuggingFacePipeline
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from langchain_cohere import ChatCohere  
from langchain_core.prompts import ChatPromptTemplate 
from langchain_core.output_parsers import StrOutputParser
#from langchain_pinecone import PineconeVectorStore

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.documents import Document
from collections import defaultdict
from nltk.sentiment import SentimentIntensityAnalyzer
import numpy as np
import nltk
from config import neo4j_credentials
from config import *

# calling all prompts constants
from prompt import *
from logging_utils import get_logger
#from config import *
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Comes from config.py
neo4j_uri, neo4j_user, neo4j_password, neo4j_database = neo4j_credentials("cloud")

neo4j_database = "hg-qwen-graph" # hardcoded to overwrote the config.py file and for Presentation purposes
# Load .env from project root so PINECONE_API_KEY etc. are set regardless of CWD
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

def _setup_kg_logger() -> logging.Logger:
    """Logger for KG pipeline: stdout + rotating file under /tmp/KG."""
    logger = logging.getLogger("KG")
    if logger.handlers:
        return logger  # avoid duplicate handlers on repeated imports

    logger.setLevel(logging.DEBUG)

    log_dir = Path("/tmp/KG")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        # If /tmp is not writable, still allow stdout logging.
        pass

    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Stdout handler
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # Rotating file handler: 500KB each, keep 3 files total (current + 2 backups)
    try:
        fh_path = log_dir / "KG.log"
        fh = RotatingFileHandler(
            filename=str(fh_path),
            maxBytes=500 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        # If file handler can't be created, stdout logging still works.
        pass

    logger.propagate = False
    logger.debug("KG logger initialized (stdout + rotating file in /tmp/KG).")
    return logger


logger = _setup_kg_logger()


# ---------------------------------------------------------------------------
# PineconeVectorStore drop-in replacement
# Replicates only the methods used in this file:
#   .add_texts(texts, metadatas)
#   .similarity_search(query, k)
# No langchain-pinecone / simsimd dependency required.
# ---------------------------------------------------------------------------

class PineconeVectorStore:
    """
    Minimal Pinecone vector store that matches the langchain-pinecone interface
    used in this file. Backed entirely by the native pinecone-client SDK.
    """

    class _Doc:
        """Mimics langchain Document so existing .page_content access works."""
        def __init__(self, content: str, metadata: dict):
            self.page_content = content
            self.metadata     = metadata

    def __init__(self, index, embedding, namespace: str):
        self._index     = index
        self._embed     = embedding   # SentenceTransformer instance
        self._namespace = namespace

    def add_texts(self, texts: list[str], metadatas: list[dict] = None) -> None:
        """Embed texts and upsert into Pinecone under self._namespace."""
        if not texts:
            return
        metadatas = metadatas or [{} for _ in texts]
        embeddings = self._embed.encode(texts).tolist()

        vectors = []
        for i, (text, emb, meta) in enumerate(zip(texts, embeddings, metadatas)):
            # Use a stable ID based on namespace + position to allow re-runs
            # without creating duplicate vectors
            vec_id = f"{self._namespace}_mem_{abs(hash(text)) % 10**12}"
            vectors.append({
                "id"      : vec_id,
                "values"  : emb,
                "metadata": {**meta, "text": text},   # store text for retrieval
            })

        self._index.upsert(vectors=vectors, namespace=self._namespace)

    def similarity_search(self, query: str, k: int = 4) -> list:
        """Return top-k results as pseudo-Document objects with .page_content."""
        embedding = self._embed.encode(query).tolist()
        results   = self._index.query(
            vector          = embedding,
            top_k           = k,
            namespace       = self._namespace,
            include_metadata= True,
        )
        return [
            self._Doc(
                content  = m.metadata.get("text", ""),
                metadata = m.metadata,
            )
            for m in results.matches
        ]
calculated_metrics = ""
# ----------------------------- RAGQuery -----------------------------
class RAGQuery:
    def __init__(self, 
                    index_name: str,
                    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
                    llm_model_name: str = "Qwen/Qwen2.5-1.5B-Instruct",
                    doc_namespace: str = "documents",
                    mem_namespace: str = "history",
                    neo4j_uri: str = None,
                    neo4j_user: str = None,
                    neo4j_password: str = None,
                    neo4j_database: str = None,
                    ): # 
        """
        Initialize RAG query system
        
        Args:
            index_name: Pinecone index name
            embedding_model_name: Model for query embeddings
            llm_model_name: Local LLM model
            namespace: Pinecone namespace
        """
        # Always use CPU to avoid GPU compatibility issues
        self.device = "cpu"
        logger.info("Forcing device to: %s to bypass 5070 Ti compatibility issue", self.device)
        # Initialize embedding model
        # Initialize the embedding model for text encoding
        logger.debug("embedding_model_name is: %s", embedding_model_name)
        self.embedding_model = SentenceTransformer(embedding_model_name,device = 'cpu')
        logger.debug("embedding_model is: %s", self.embedding_model)
        self.embedding_model.embed_documents = lambda texts: self.embedding_model.encode(texts).tolist()
        logger.debug("embedding_model.embed_documents is: %s", self.embedding_model.embed_documents)
        self.embedding_model.embed_query = lambda text: self.embedding_model.encode(text).tolist()
        logger.debug("embedding_model.embed_query is: %s", self.embedding_model.embed_query)
        self.embedding_model.to(self.device)
        logger.debug("embedding_model.to(self.device) is: %s", self.embedding_model.to(self.device))
        # Initialize Pinecone vector database and memory search
        pinecone_key = (os.getenv("PINECONE_API_KEY") or "").strip().strip('"').strip("'")
        if not pinecone_key:
            raise ValueError(
                "PINECONE_API_KEY is not set or is empty. "
                "Set it in .env or your environment and ensure it is loaded (e.g. in Docker, pass the env var or mount .env)."
            )
        # 401 = key wrong, expired, or from a different project than the index
        if not pinecone_key.startswith("pcsk_") and not pinecone_key.startswith("psk_"):
            logger.warning("PINECONE_API_KEY does not look like a Pinecone key (expected pcsk_ or psk_ prefix).")
        self.pc = Pinecone(api_key=pinecone_key)
        logger.debug("pc is: %s", self.pc)
        try:
            logger.info("index_name is: %s", index_name.strip().strip('"').strip("'"))
            self.index = self.pc.Index(index_name.strip().strip('"').strip("'"))
            logger.debug("index is: %s", self.index)
        except Exception as e:
            err_msg = str(e).lower()
            if "401" in err_msg or "unauthorized" in err_msg:
                raise RuntimeError(
                    "Pinecone returned 401 Unauthorized. Check that PINECONE_API_KEY is correct, not expired, "
                    "and from the same Pinecone project that owns the index. Verify the key at https://app.pinecone.io/"
                ) from e
            if "404" in err_msg or "not found" in err_msg:
                try:
                    # List indexes this API key can see (each key is tied to one project)
                    index_list = list(self.pc.list_indexes().names()) if hasattr(self.pc.list_indexes(), "names") else []
                    hint = f" Indexes visible with this API key: {index_list}." if index_list else " This API key has no indexes in its project."
                except Exception:
                    hint = ""
                raise RuntimeError(
                    f"Pinecone index {index_name!r} not found (404). The index may exist in a different Pinecone project than this API key.{hint} "
                    "Use an index from the list above, or create the index in the project that owns this key. See https://app.pinecone.io/"
                ) from e
            logger.error("Error initializing index: %s", e)
            raise e
        logger.debug("index is: %s", self.index)
        self.doc_namespace = doc_namespace
        logger.debug("doc_namespace is: %s", self.doc_namespace)
        self.mem_namespace = mem_namespace
        logger.debug("mem_namespace is: %s", self.mem_namespace)
        self.memory_search = PineconeVectorStore(
            index=self.index, 
            embedding=self.embedding_model, 
            namespace=mem_namespace  
        )
        logger.debug("memory_search is: %s", self.memory_search)
        # Initialize the LLM (Cohere API) for text generation
        logger.info("Initializing Cohere API Model...")
        self.llm = ChatCohere(
            model="command-r-plus-08-2024",
            cohere_api_key=os.getenv("COHERE_API_KEY").strip().strip('"').strip("'"),
            temperature=0.2, # Lower randomness for more deterministic output
            frequency_penalty=0.1 # Penalize repetition
        )
        logger.info("✅ Initializing Final Synthesis and Archive Chains...")
        logger.debug(
            "cohere_api_key present: %s",
            bool((os.getenv("COHERE_API_KEY") or "").strip().strip('"').strip("'")),
        )
        self.final_synthesis_chain = (
            ChatPromptTemplate.from_template(FINAL_SYNTHESIS_TEMPLATE) 
            | self.llm 
            | StrOutputParser()
        )

        self.diag_summary_chain = (
            ChatPromptTemplate.from_template(DIAG_SUMMARY_TEMPLATE) 
            | self.llm 
            | StrOutputParser()
        )

        self.interact_summary_chain = (
            ChatPromptTemplate.from_template(INTERACT_SUMMARY_TEMPLATE) 
            | self.llm 
            | StrOutputParser()
        )
        # Neo4j driver (optional — gracefully disabled if credentials not provided)
        self._neo4j_driver = None
        neo4j_uri      = neo4j_uri      or os.getenv("NEO4J_URI")
        neo4j_user     = neo4j_user     or os.getenv("NEO4J_USER")
        neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD")
        neo4j_uri = neo4j_uri.strip().strip('"').strip("'")
        neo4j_user = neo4j_user.strip().strip('"').strip("'")
        neo4j_password = neo4j_password.strip().strip('"').strip("'")
        logger.debug("neo4j_uri is: %s", neo4j_uri)
        logger.debug("neo4j_user is: %s", neo4j_user)
        logger.debug("neo4j_password is set: %s", bool(neo4j_password))
        if neo4j_uri and neo4j_user and neo4j_password:
            try:
                from neo4j import GraphDatabase
                logger.info("Connecting to Neo4j at %s with user %s", neo4j_uri, neo4j_user)
                self._neo4j_driver = GraphDatabase.driver(
                    neo4j_uri, auth=(neo4j_user, neo4j_password)
                )
                self._neo4j_driver.verify_connectivity()
                logger.info("✅ Neo4j connected successfully.")
            except Exception as e:
                logger.warning("⚠️  Neo4j connection failed: %s. Graph retrieval will be skipped.", e)
        else:
            logger.warning("⚠️  Neo4j credentials not provided. Graph retrieval will be skipped.")


    # ----------------------------- Transcript Loader ----------------------------         
    def load_custom_transcript(self, path):
        """
        Load a custom transcript JSON file and convert entries to Document objects.
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        docs = []
        for entry in data['transcript']:
            parts = entry.split(':', 3)
            if len(parts) == 4:
                meeting_id, speaker, timestamp, text = parts
                doc = Document(
                    page_content=text.strip(),
                    metadata={
                        "meeting_id": meeting_id,
                        "speaker": speaker,
                        "timestamp": timestamp,
                        "source_type": "Transcript"
                    }
                )
                docs.append(doc)
        return docs

    def get_strategic_segments(self, docs, window_size=150):
        """
        Split the transcript into opening, middle, and closing segments for analysis.
        """
        total = len(docs)
        # 1. Opening
        opening = docs[:window_size]
        # 2. Middle
        mid_start = max(0, total // 2 - (window_size // 2))
        middle = docs[mid_start : mid_start + window_size]
        # 3. Closing
        closing = docs[-window_size:]
        
        return opening, middle, closing

    @staticmethod
    def format_segment(docs, label):
        """
        Format a list of Document objects into a readable string segment.
        """
        text = "\n".join([
            f"[{d.metadata.get('timestamp', 'N/A')}] Speaker {d.metadata.get('speaker', 'Unknown')}: {d.page_content}"
            for d in docs
        ])
        return f"### {label} SEGMENT ###\n{text}\n"

    # ----------------------------- Trend Analysis -----------------------------
    def run_trend_analysis(self, opening, middle, closing, segments = "", user_input="None"):
        """
        Run a trend analysis on the transcript segments using the LLM and user context.
        """

        combined_transcript = (
            self.format_segment(opening, "OPENING") + "\n" +
            self.format_segment(middle, "MIDDLE") + "\n" +
            self.format_segment(closing, "CLOSING")
        )

        # Get Metrics
        turn_counts, turnCounts, wordCounts, turnPercentages, wordPercentages, interruptionsResult, interruptionRate, convoScore = obtainBaseMetrics(segments)
        normalized_sentiment_scores, speaker_sentiments = sentimentBaseAnalysis(segments, turn_counts)
        speaker_volaitility = speakerBaseVolatility(speaker_sentiments)
        calculated_metrics = COACHING_SCORE_DEFINITION + "\n" + turnCounts + "\n" + wordCounts + "\n" + turnPercentages + "\n" + wordPercentages + "\n" + interruptionsResult + "\n" + interruptionRate + "\n" + convoScore \
        + "\n" + SENTIMENT_SCORE_DEFINITION + "\n" + normalized_sentiment_scores + "\n" + VOLATILITY_SCORE_DEFINITION + "\n" + speaker_volaitility

        # ----------------------------- Diagnostic Prompt -----------------------------
        
        diagnostic_prompt = ChatPromptTemplate.from_messages([
            ("system", getSystemPrompt(calculated_metrics)),
            ("human", "Analyze these segments based on the provided user context:\n\n{chat_history}")
        ])


        diagnostic_chain = diagnostic_prompt | self.llm | StrOutputParser()

        logger.info("--- 🧠 Executing Trend Analysis with User Context ---")
        full_report = diagnostic_chain.invoke({
            "chat_history": combined_transcript,
            "user_context": user_input 
        })
        
        return full_report
    
    def execute_final_synthesis(self, current_report, past_history_text, pdf_context_text):
        """
        Generate a final coaching strategy by synthesizing current, past, and scientific context.
        """
        logger.info("--- 🎓 Generating History-Aware Coaching Strategy ---")
        
        final_response = self.final_synthesis_chain.invoke({
            "diagnostic_report": current_report,
            "past_history": past_history_text,
            "pdf_context": pdf_context_text
        })
        return final_response
    
    # ----------------------------- Neo4j Helpers -----------------------------

    def _run_neo4j_query(self, cypher: str, params: dict = None) -> list[dict]:
        """Execute a Cypher query and return results as a list of dicts."""
        if not self._neo4j_driver:
            return []
        with self._neo4j_driver.session() as session:
            result = session.run(cypher, params or {})
            return [record.data() for record in result]

    def _extract_keywords(self, query: str) -> list[str]:
        """
        Lightweight keyword extractor — strips stopwords and returns
        the most meaningful tokens for Neo4j CONTAINS matching.
        Replace with spaCy / YAKE if you need something more robust.
        """
        stopwords = {
            "what", "how", "why", "is", "are", "the", "a", "an", "in",
            "of", "for", "to", "and", "or", "with", "about", "that",
            "this", "it", "do", "does", "can", "could", "should"
        }
        tokens = query.lower().split()
        return [t.strip("?.,") for t in tokens if t not in stopwords and len(t) > 3]
    # Can be deleted later as we are using the optimised version
    def retrieve_from_neo4j(self, query: str, top_k: int = 5) -> str:
        """
        Query Neo4j knowledge graph for concepts and relationships relevant
        to the input query. Returns a formatted string ready for prompt injection.

        Graph schema: Framework, Concept, Technique, Scenario, Emotion — each with {name} only.
        """
        if not self._neo4j_driver:
            return ""

        keywords = self._extract_keywords(query)
        if not keywords:
            return ""

        # Filter by keyword on node name only (no description property),
        # using a parameterized list to avoid manual string-escaping issues.
        cypher = f"""
        MATCH (n)
        WHERE (n:Framework OR n:Concept OR n:Technique OR n:Scenario OR n:Emotion)
          AND any(kw IN $keywords WHERE toLower(n.name) CONTAINS kw)
        OPTIONAL MATCH (n)-[r]->(related)
        RETURN
            n.name        AS concept,
            labels(n)[0]  AS node_type,
            type(r)       AS relationship,
            related.name  AS related_concept
        LIMIT {top_k * 3}
        """

        try:
            records = self._run_neo4j_query(
                cypher,
                {"keywords": [kw.lower() for kw in keywords]},
            )
        except Exception as e:
            logger.warning("⚠️  Neo4j query error: %s", e)
            return ""

        if not records:
            return ""

        # Format results into readable text blocks
        seen = set()
        lines = []
        for rec in records:
            concept = rec.get("concept", "")
            if concept in seen:
                continue
            seen.add(concept)

            node_type  = rec.get("node_type", "Node")
            definition = rec.get("definition") or ""
            rel        = rec.get("relationship")
            related    = rec.get("related_concept")

            entry = f"[{node_type}] {concept}"
            if definition:
                entry += f": {definition}"
            if rel and related:
                entry += f" → ({rel}) → {related}"
            lines.append(entry)

        return "\n".join(lines)


    def retrieve_from_neo4j_optimised(self, query: str, top_k: int = 5) -> str:
        """
        OPTIMISED version of retrieve_from_neo4j.

        Improvements over original:
        1. Two-hop graph traversal  — captures indirect relationships
            (e.g. Concept → Technique → Scenario), not just direct neighbours.
        2. Relationship label included in output for richer prompt context.
        3. Fallback broad scan — if keyword matching yields nothing, runs a
            label-only scan to return at least `top_k` nodes, avoiding silent
            empty returns that starve the prompt.
        4. Deduplication on (concept, related) pairs — prevents the same
            relationship appearing multiple times from different keyword hits.
        5. Scoring hint — nodes with more outgoing relationships are surfaced
            first (degree-based soft ranking inside Cypher).
        """
        if not self._neo4j_driver:
            return ""

        keywords = self._extract_keywords(query)

        def _run(cypher, params=None):
            try:
                return self._run_neo4j_query(cypher, params or {})
            except Exception as e:
                logger.warning("⚠️  Neo4j query error: %s", e)
                return []

        # ── Pass 1: keyword-filtered two-hop traversal ──────────────────────────
        records = []
        if keywords:
            cypher_two_hop = f"""
            MATCH (n)
            WHERE (n:Framework OR n:Concept OR n:Technique OR n:Scenario OR n:Emotion)
            AND any(kw IN $keywords WHERE toLower(n.name) CONTAINS kw)

            // First hop
            OPTIONAL MATCH (n)-[r1]->(hop1)

            // Second hop
            OPTIONAL MATCH (hop1)-[r2]->(hop2)

            RETURN
                n.name          AS concept,
                labels(n)[0]    AS node_type,
                type(r1)        AS rel1,
                hop1.name       AS hop1_concept,
                labels(hop1)[0] AS hop1_type,
                type(r2)        AS rel2,
                hop2.name       AS hop2_concept

            // Prefer nodes with more connections (richer context first)
            ORDER BY size([(n)-[]-() | 1]) DESC
            LIMIT {top_k * 4}
            """
            logger.debug("*" * 50)
            logger.debug("The Cypher query for two hop traversal is: %s", cypher_two_hop)
            logger.debug("*" * 50)
            records = _run(
                cypher_two_hop,
                {"keywords": [kw.lower() for kw in keywords]},
            )

            # ── Pass 2: fallback broad scan (no keyword filter) ─────────────────────
            if not records:
                logger.info("⚠️  Neo4j keyword pass returned nothing — running broad fallback scan.")
                cypher_fallback = f"""
                MATCH (n)
                WHERE (n:Framework OR n:Concept OR n:Technique OR n:Scenario OR n:Emotion)
                OPTIONAL MATCH (n)-[r]->(related)
                RETURN
                    n.name        AS concept,
                    labels(n)[0]  AS node_type,
                    type(r)       AS rel1,
                    related.name  AS hop1_concept,
                    labels(related)[0] AS hop1_type,
                    null AS rel2,
                    null AS hop2_concept
                ORDER BY size([(n)-[]-() | 1]) DESC
                LIMIT {top_k}
                """
                records = _run(cypher_fallback)

            if not records:
                return ""

            # ── Format — deduplicate on (concept, hop1_concept) pairs ───────────────
            seen_pairs = set()
            lines = []

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

                # Build entry: always show the anchor node
                entry = f"[{node_type}] {concept}"

                # First hop
                if rel1 and hop1:
                    entry += f" →[{rel1}]→ [{hop1_type}] {hop1}"

                    # Second hop (only add if distinct from first hop)
                    if rel2 and hop2 and hop2 != hop1:
                        entry += f" →[{rel2}]→ {hop2}"

                lines.append(entry)

            return "\n".join(lines)

    # ----------------------------- Combined Context -----------------------------
    # Can be deleted later as we are using the optimised version
    def get_vectordb_knowledgegraph_combined_context(self, queries: list) -> str:
        """
        Fuses context from TWO sources for each query:
          1. Pinecone (vector similarity) — chunk texts from local JSON files
          2. Neo4j    (graph traversal)   — concepts, frameworks, relationships

        Returns a single merged string for prompt injection.
        """
        logger.info("🔍 Retrieving from Pinecone (namespace: %r) + Neo4j...", self.doc_namespace)

        pinecone_texts = {}   # vector_id -> text  (dedup)
        neo4j_blocks   = []

        for q in queries:
            # --- 1. Pinecone retrieval ---
            matches = self.retrieve_context(q, top_k=2, namespace=self.doc_namespace)
            for m in matches:
                vid = m.id
                if vid in pinecone_texts:
                    continue

                source_name = m.metadata.get('source')
                if not source_name:
                    inline = m.metadata.get('text', '').strip()
                    if inline:
                        pinecone_texts[vid] = inline
                    continue

                text = ""
                try:
                    chunk_file_path = f"../chunk_texts/{source_name}_texts.json"
                    with open(chunk_file_path, 'r', encoding='utf-8') as f:
                        full_texts = json.load(f)
                    text = full_texts.get(vid, '').strip()
                except FileNotFoundError:
                    logger.debug("Chunk file not found: %s", chunk_file_path)
                    # Fallback: use text stored in Pinecone metadata (e.g. ingestion stores first 300 chars)
                    text = (m.metadata.get('text') or '').strip()
                    if text:
                        logger.info("⚠️  Chunk file not found for source: %s; using metadata preview.", source_name)
                    #os._exit(1)
                except Exception as e:
                    logger.warning("⚠️  Error loading chunk: %s", e)
                    text = (m.metadata.get('text') or '').strip()
                if text:
                    pinecone_texts[vid] = text

            # --- 2. Neo4j retrieval ---
            graph_text = self.retrieve_from_neo4j(q, top_k=5)
            if graph_text:
                neo4j_blocks.append(f"[Graph context for: '{q}']\n{graph_text}")

        # --- Merge and format ---
        sections = []

        if pinecone_texts:
            logger.info("✅ Pinecone: %s unique chunk(s) retrieved.", len(pinecone_texts))
            sections.append(
                "### VECTOR KNOWLEDGE BASE (Pinecone)\n" +
                "\n---\n".join(pinecone_texts.values())
            )
        else:
            logger.info("⚠️  No Pinecone chunks retrieved.")

        if neo4j_blocks:
            logger.info("✅ Neo4j: %s query block(s) retrieved.", len(neo4j_blocks))
            sections.append(
                "### KNOWLEDGE GRAPH (Neo4j)\n" +
                "\n\n".join(neo4j_blocks)
            )
        else:
            logger.info("⚠️  No Neo4j graph context retrieved.")

        return "\n\n" + "="*60 + "\n\n".join(sections) if sections else ""
    
    def _expand_queries(self, queries: list[str]) -> list[str]:
        """
        Lightweight query expansion:
        - Keeps original queries
        - Adds a noun-phrase focused variant (strips verbs/aux words)
        - Adds a keyword-only variant using _extract_keywords()
        This increases recall without requiring an extra LLM call.
        """
        aux_verbs = {"is", "are", "was", "were", "does", "do", "did",
                    "can", "could", "should", "would", "will", "has", "have"}
        expanded = []
        seen = set()

        for q in queries:
            for variant in [
                q,
                # noun-phrase variant: drop aux verbs
                " ".join(w for w in q.split() if w.lower() not in aux_verbs),
                # keyword-only variant
                " ".join(self._extract_keywords(q)),
            ]:
                v = variant.strip()
                if v and v not in seen:
                    seen.add(v)
                    expanded.append(v)

        return expanded

    
    # Can be deleted later as we are using the optimised version
    # ---Optimised version of get_vectordb_knowledgegraph_combined_context---

    def get_vectordb_knowledgegraph_combined_context_optimised(
    self,
    queries: list[str],
    pinecone_top_k: int = 5,       # raised from 2 → 5 per query
    neo4j_top_k: int = 7,          # raised from 5 → 7 per query
    max_chunks: int = 15,          # hard cap on total Pinecone chunks returned
) -> str:
        """
        OPTIMISED version of get_vectordb_knowledgegraph_combined_context.

        Improvements over original:
        1. Query expansion  — each input query spawns up to 3 variants
            (original + noun-phrase + keyword-only) before hitting both DBs,
            significantly increasing recall.
        2. Higher top_k    — 5 Pinecone chunks and 7 Neo4j nodes per query
            (configurable) vs the original 2 / 5.
        3. Content-level dedup for Pinecone — deduplicates on text fingerprint
            (first 120 chars) in addition to vector ID, so near-duplicate
            chunks from different queries don't bloat the context.
        4. Relevance-ordered output — Pinecone chunks are sorted by their
            Pinecone similarity score (descending) so the strongest signal
            appears first in the prompt.
        5. Hard cap (`max_chunks`) — prevents context overflow on large query
            sets while still maximising coverage up to the cap.
        6. Uses optimised Neo4j function — two-hop traversal + fallback.
        7. Metadata-enriched chunk headers — each chunk shows its source
            file and score so the LLM can weight evidence appropriately.
        """
        logger.info(
            f"🔍 [OPTIMISED] Retrieving — Pinecone top_k={pinecone_top_k}, "
            f"Neo4j top_k={neo4j_top_k}, max_chunks={max_chunks} ..."
        )

        # ── Step 1: expand queries ───────────────────────────────────────────────
        expanded_queries = self._expand_queries(queries)
        logger.debug("Query expansion: %s → %s variants", len(queries), len(expanded_queries))

        # ── Step 2: Pinecone retrieval ───────────────────────────────────────────
        # keyed by vector_id; value = (score, text, source)
        pinecone_hits: dict[str, tuple[float, str, str]] = {}
        # content fingerprint dedup (catches same text under different vector IDs)
        content_seen: set[str] = set()

        for q in expanded_queries:
            matches = self.retrieve_context(q, top_k=pinecone_top_k, namespace=self.doc_namespace)

            for m in matches:
                vid   = m.id
                score = getattr(m, "score", 0.0)
                #print("\n ****************** Score is: ", score,"\n")
                #print("\n ****************** vid is: ", vid,"\n")
                if vid in pinecone_hits:
                    #print("\n ****************** vid is in pinecone_hits\n")
                    # keep the higher score if we've seen this ID before
                    if score > pinecone_hits[vid][0]:
                        pinecone_hits[vid] = (score, pinecone_hits[vid][1], pinecone_hits[vid][2])
                    continue

                source_name = m.metadata.get("source")
                text = ""

                if not source_name:
                    text = m.metadata.get("text", "").strip()
                else:
                    try:
                        # Resolve chunk_texts path relative to this project, not the current working directory.
                        # In Docker, WORKDIR is /app and chunk_texts is copied to /app/chunk_texts.
                        chunk_file_path = (
                            Path(__file__).resolve().parent.parent
                            / "chunk_texts"
                            / f"{source_name}_texts.json"
                        )
                        with open(chunk_file_path, "r", encoding="utf-8") as f:
                            full_texts = json.load(f)
                        text = full_texts.get(vid, "").strip()
                        if not text:
                            text = (m.metadata.get("text") or "").strip()
                    except FileNotFoundError:
                        text = (m.metadata.get("text") or "").strip()
                        if text:
                            logger.info("⚠️  Chunk file missing for %r; using metadata preview.", source_name)
                        else:
                            logger.debug("❌  No text found for vector %r — skipping.", vid)
                            continue
                    except Exception as e:
                        logger.warning("⚠️  Error loading chunk %r: %s", vid, e)
                        text = (m.metadata.get("text") or "").strip()

                if not text:
                    continue

                # Content-level dedup
                fingerprint = text[:120]
                if fingerprint in content_seen:
                    continue
                content_seen.add(fingerprint)

                pinecone_hits[vid] = (score, text, source_name or "inline")

        # Sort by score descending, then apply hard cap
        sorted_chunks = sorted(pinecone_hits.values(), key=lambda x: x[0], reverse=True)[:max_chunks]

        # ── Step 3: Neo4j retrieval ──────────────────────────────────────────────
        neo4j_blocks: list[str] = []
        neo4j_seen: set[str] = set()

        for q in queries:  # use original queries only for graph — expansion less useful here
            graph_text = self.retrieve_from_neo4j_optimised(q, top_k=neo4j_top_k)
            if graph_text and graph_text not in neo4j_seen:
                neo4j_seen.add(graph_text)
                neo4j_blocks.append(f"[Graph context for: '{q}']\n{graph_text}")

        # ── Step 4: Assemble final context string ────────────────────────────────
        sections: list[str] = []

        if sorted_chunks:
            logger.info("✅ Pinecone: %s unique chunk(s) after dedup & cap.", len(sorted_chunks))
            chunk_lines = []
            for rank, (score, text, source) in enumerate(sorted_chunks, 1):
                header = f"[Chunk {rank} | source: {source} | score: {score:.3f}]"
                chunk_lines.append(f"{header}\n{text}")
            sections.append(
                "### VECTOR KNOWLEDGE BASE (Pinecone)\n" +
                "\n---\n".join(chunk_lines)
            )
        else:
            logger.info("⚠️  No Pinecone chunks retrieved.")

        if neo4j_blocks:
            logger.info("✅ Neo4j: %s query block(s) retrieved.", len(neo4j_blocks))
            sections.append(
                "### KNOWLEDGE GRAPH (Neo4j)\n" +
                "\n\n".join(neo4j_blocks)
            )
        else:
            logger.info("⚠️  No Neo4j graph context retrieved.")

        if not sections:
            return ""

        divider = "\n\n" + "=" * 60 + "\n\n"
        return divider + divider.join(sections)

    # ----------------------------- PDF Knowledge Base Context & RAG Retrieval-----------------------------
    def get_pdf_knowledge(self, queries):
        """Backward-compatible alias for get_knowledge_graph_context."""
        return self.get_vectordb_knowledgegraph_combined_context(queries)
    
    # ── Update get_pdf_knowledge alias to point at optimised version ─────────────
    # Can be deleted later as we are using the optimised version
    def get_pdf_knowledge_optimised(self, queries: list[str]) -> str:
        """Optimised alias replacing get_pdf_knowledge."""
        return self.get_vectordb_knowledgegraph_combined_context_optimised(queries)
    def retrieve_context_from_knowledge_graph(self, query: str, top_k: int = 5) -> list:
        """Returns raw Pinecone match objects. Use get_knowledge_graph_context() for text."""
        return self.retrieve_context(query, top_k=top_k, namespace=self.doc_namespace)

    def close(self):
        """Call this on shutdown to cleanly close the Neo4j driver."""
        if self._neo4j_driver:
            self._neo4j_driver.close()
            logger.info("Neo4j connection closed.")
    
    # ----------------------------- Save to Memory -----------------------------
    def save_to_memory(self, target_speaker, report, final_strategy):
        """
        Save the quantitative and interaction summaries to the memory vector store.
        """

        logger.info("💾 Archiving Dual-Memory Blocks for %s...", target_speaker)

        quant_summary = self.diag_summary_chain.invoke({"diagnostic_report": report})
        
        interact_summary = self.interact_summary_chain.invoke({
            "chat_history": f"AI Advice: {final_strategy}",
            "user_role": target_speaker
        })

        self.memory_search.add_texts(
            texts=[quant_summary, interact_summary],
            metadatas=[
                {"speaker": target_speaker, "category": "quantitative", "type": "memory_block"},
                {"speaker": target_speaker, "category": "interactive", "type": "memory_block"}
            ]
        )
        
        logger.info("✅ Quantitative & Interaction summaries archived to: %s", self.mem_namespace)
        return quant_summary, interact_summary

    # ----------------------------- Chat with Coach Assistant -----------------------------
    def chat_with_coach_assistant(self, transcript_docs, final_report_data):
        """
        Interactive chat loop with the cognitive coach assistant, using memory and context.
        """
        logger.info("🎓 Cognitive Coach Assistant is Online (Memory-Enabled).")
        
        # 1. Identify all speakers in the transcript
        all_speakers = list(set([d.metadata['speaker'] for d in transcript_docs]))
        speaker_list_str = ", ".join(all_speakers)
        user_role = input(f"Which speaker are you? ({speaker_list_str}): ").strip()

        # 2. Retrieve past coaching sessions for the selected user from memory
        logger.info("🔍 Searching for past coaching sessions for %s...", user_role)
        past_memories = self.memory_search.similarity_search(f"Past metrics and sessions for {user_role}", k=2)
        past_mem_context = "\n---\n".join([m.page_content for m in past_memories]) if past_memories else "First session detected."

        # 3. Initialize chat history
        history = ChatMessageHistory()
        
        # 4. Build system prompt with empathy and historical context
        initial_context = f"""
        You are a World-Class Human-Centric Cognitive Coach.
        [TONE & STYLE]
        - Be Empathetic First: If the user expresses frustration, validate feelings BEFORE giving advice.
        - Speak like a Peer-Mentor: Use a conversational, supportive, and grounded tone.
        [USER IDENTITY] The user is {user_role}.
        [PAST PERFORMANCE & TRENDS] {past_mem_context}
        [CURRENT CASE DATA] {final_report_data}
        [MISSION] Validate {user_role}'s experience. Use data to empower them.
        """

        # 5. Chat loop for user interaction
        while True:
            user_input = input(f"\n{user_role} (You): ")

            if user_input.lower() in ['exit', 'quit', 'stop']:
                # Save chat summary to memory and exit
                logger.info("💾 Saving interaction summary to memory...")
                chat_history_text = "\n".join([f"{m.type}: {m.content}" for m in history.messages])
                interact_memory = self.interact_summary_chain.invoke({
                    "user_role": user_role,
                    "chat_history": chat_history_text
                })
                self.memory_search.add_texts(
                    texts=[interact_memory],
                    metadatas=[{"type": "interaction_summary", "speaker": user_role}]
                )
                logger.info("✅ Chat session ended. Summary saved to history.")
                break

            # Build message flow for Cohere LLM
            messages = [SystemMessage(content=initial_context)]
            messages.extend(history.messages)
            messages.append(HumanMessage(content=user_input))

            try:
                response = self.llm.invoke(messages)
                ai_message = response.content if hasattr(response, 'content') else str(response)

                history.add_user_message(user_input)
                history.add_ai_message(ai_message)

                logger.info("Assistant: %s\n%s", ai_message, "-" * 30)
            except Exception as e:
                logger.error("❌ Execution Error: %s", e)

                
    def _extract_queries(self, report):
        """
        Extract up to 3 search queries from the diagnostic report for further knowledge retrieval.
        """
        import re
        lines = report.split('\n')
        queries = [re.sub(r'^\d+\.\s*', '', l).strip().replace('"', '') 
                   for l in lines if 'Query' in l and ':' in l]
        
        if not queries:
            queries = re.findall(r'"([^"]*)"', report)
            
        filtered = [q for l in queries for q in [l.split(':')[-1].strip()] 
                    if len(q) > 10 and "ANALYSIS" not in q]
        
        return filtered[:3]
            

    
    def retrieve_context_from_knowledge_graph(self, query: str, top_k: int = 5) -> list:
        """
        Retrieve top-k most relevant context chunks from knowledge graph for a given query.
        """
        return self.get_knowledge_graph_context([query])
    
    def retrieve_context(self, query: str, top_k: int = 5, namespace: str = None) -> list:
        """
        Retrieve top-k most relevant context chunks from Pinecone for a given query.
        """

        query_embedding = self.embedding_model.encode(query).tolist()
        
        #  (doc_namespace)
        target_ns = namespace if namespace else self.doc_namespace
        
        results = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=target_ns,
            include_metadata=True
        )
        return results.matches
 
    # ----------------------------- Clear Memory -----------------------------
    def clear_memory(self):
        """
        Clear all records in the memory namespace. Use with caution!
        """
        logger.warning("🧹 DANGER: Clearing all records in namespace: %s...", self.mem_namespace)
        try:
            self.index.delete(delete_all=True, namespace=self.mem_namespace)
            logger.info("✅ Namespace %r is now empty.", self.mem_namespace)
        except Exception as e:
            logger.error("❌ Error clearing memory: %s", e)

# ----------------------------- Metrics -----------------------------
def load_custom_transcript(path):
    with open(path, 'r') as f:
        data = json.load(f)

    docs = []
    # Loop through each string in the transcript list
    for entry in data['transcript']:
        # Split by ':' to separate ID, Speaker, Timestamp, and Text
        # Based on your image: "MeetingID : Speaker : Timestamp : Text"
        parts = entry.split(':', 3)

        if len(parts) == 4:
            meeting_id, speaker, timestamp, text = parts

            # Create a LangChain Document
            doc = Document(
                page_content=text.strip(),
                metadata={
                    "meeting_id": meeting_id,
                    "speaker": speaker,
                    "timestamp": timestamp,
                    "source_type": "Transcript"
                }
            )
            docs.append(doc)

    return docs

def obtainMetrics():
    turn_counts = defaultdict(int)
    word_counts = defaultdict(int)
    interruptions = 0

    previous_speaker = None
    previous_end_time = 0.0  # track timestamp of last turn

    # Process each transcript entry
    for doc in transcripts:
        speaker = doc.metadata['speaker']
        timestamp = float(doc.metadata['timestamp'])
        text = doc.page_content

        # Count turn
        turn_counts[speaker] += 1

        # Count words
        words = [w for w in text.split() if w.strip()]
        word_counts[speaker] += len(words)

        # Count interruption: speaker changes and next turn starts within 0.5 seconds (adjustable)
        if previous_speaker and speaker != previous_speaker:
            if timestamp - previous_end_time < 0.5:
                interruptions += 1

        previous_speaker = speaker
        previous_end_time = timestamp

    total_turns = sum(turn_counts.values())
    total_words = sum(word_counts.values())

    # Compute turn share score (closer to equal is better)
    num_speakers = len(turn_counts)
    ideal_share = 100 / num_speakers

    turn_percentages = {s: (c / total_turns) * 100 for s, c in turn_counts.items()}
    turnshare_score = 100 - sum(abs(ideal_share - p) for p in turn_percentages.values())

    # Compute word share score
    word_percentages = {s: (c / total_words) * 100 for s, c in word_counts.items()}
    wordshare_score = 100 - sum(abs(ideal_share - p) for p in word_percentages.values())

    # Compute interruption rate
    interruption_rate = (interruptions / total_turns) * 100 if total_turns > 0 else 0

    # Raw conversational balance score
    #print(turnshare_score)
    #print(wordshare_score)
    raw_score = turnshare_score + wordshare_score - interruption_rate

    # Normalize to 0-100
    # Maximum possible score: turnshare_score=100, wordshare_score=100, interruption_rate=0 => 200
    # Minimum possible score: turnshare_score=0, wordshare_score=0, interruption_rate=100 => -100
    # So range = 200 - (-100) = 300
    normalized_score = ((raw_score + 100) / 300) * 100
    normalized_score = max(0, min(100, normalized_score))  # clamp to 0-100

    # Print results
    turnCounts = "Turn counts: " + str(dict(turn_counts))
    #print(turnCounts)
    wordCounts = "Word counts: " + str(dict(word_counts))
    #print(wordCounts)
    turnPercentages = "Turn percentages: " + str({k: round(v, 2) for k, v in turn_percentages.items()})
    #print(turnPercentages)
    wordPercentages = "Word percentages: " + str({k: round(v, 2) for k, v in word_percentages.items()})
    #print(wordPercentages)
    interruptionsResult = "Interruptions: " + str(interruptions)
    #print(interruptionsResult)
    interruptionRate = "Interruption rate: " + str(round(interruption_rate, 2))
    #print(interruptionRate)
    convoScore = "Normalized Conversational Balance Score (0-100): Formula = raw_score = turnshare_score + wordshare_score - interruption_rate \
                  normalized_score = ((raw_score + 100) / 300) * 100 normalized_score = max(0, min(100, normalized_score))  # clamp to 0-100 " + str(round(normalized_score, 2))
    #print(convoScore)

    return turn_counts, turnCounts, wordCounts, turnPercentages, wordPercentages, interruptionsResult, interruptionRate, convoScore

def sentimentAnalysis(turn_counts):
    #nltk.download('vader_lexicon')

    try:
        logger.info("Loading sentiment analyzer...")
        lexicon_file='nltk_data/sentiment/vader_lexicon.txt'
        sia = SentimentIntensityAnalyzer( lexicon_file=lexicon_file)
    except Exception as e:
        if "vader_lexicon not found" in str(e):
            logger.info("Vader lexicon not found, downloading...")
            nltk.download('vader_lexicon', quiet=True)
            lexicon_file='nltk_data/sentiment/vader_lexicon.txt'
            sia = SentimentIntensityAnalyzer( lexicon_file=lexicon_file)
        else:
            logger.error("Error loading sentiment analyzer: %s", e)
            return "Error loading sentiment analyzer", {}
        logger.error("Error loading sentiment analyzer: %s", e)
        return "Error loading sentiment analyzer", {}

    speaker_sentiments = {}

    for i, doc in enumerate(transcripts):
        speaker = doc.metadata["speaker"]
        text = doc.page_content

        score = sia.polarity_scores(text)["compound"]

        if speaker not in speaker_sentiments:
            speaker_sentiments[speaker] = []

        speaker_sentiments[speaker].append((i, score))  # keep time index

    from sklearn.linear_model import LinearRegression

    speaker_slopes = {}

    for speaker, values in speaker_sentiments.items():
        indices = np.array([v[0] for v in values]).reshape(-1, 1)
        scores = np.array([v[1] for v in values])

        model = LinearRegression()
        model.fit(indices, scores)

        slope = model.coef_[0]
        speaker_slopes[speaker] = slope

    #print(speaker_slopes)
    #print(turn_counts)
    normalized_scores = {}
    for key in turn_counts:
      score = speaker_slopes[key] * turn_counts[key]
      #print(score)
      normalized_score = (score + 1) / len(turn_counts)
      normalized_scores[key] = normalized_score

    #for key in normalized_scores:
      #print("Speaker " + key + " Sentiment: " + str(normalized_scores[key]))

    return "Speaker Sentiment: " + str(normalized_scores), speaker_sentiments

def speakerVolatility(speaker_sentiments):
    speaker_volatility = {}

    for speaker, values in speaker_sentiments.items():
        scores = np.array([v[1] for v in values])
        volatility = np.std(scores)
        speaker_volatility[speaker] = volatility

    #print(speaker_volatility)

    return "Speaker volatility: " + str(speaker_volatility)

def obtainBaseMetrics(segments):
    turn_counts = defaultdict(int)
    word_counts = defaultdict(int)
    interruptions = 0

    previous_speaker = None
    previous_end_time = 0.0

    for doc in segments:
        speaker = doc['speaker']
        start_time = float(doc['start'])
        end_time = float(doc['end'])
        text = doc['text']

        # Count turn
        turn_counts[speaker] += 1

        # Count words
        words = [w for w in text.split() if w.strip()]
        word_counts[speaker] += len(words)

        # Interruption detection
        if previous_speaker and speaker != previous_speaker:
            if start_time - previous_end_time < 0.1:
                interruptions += 1

        previous_speaker = speaker
        previous_end_time = end_time

    total_turns = sum(turn_counts.values())
    total_words = sum(word_counts.values())

    num_speakers = len(turn_counts)
    ideal_share = 100 / num_speakers if num_speakers > 0 else 0

    turn_percentages = {s: (c / total_turns) * 100 for s, c in turn_counts.items()}
    word_percentages = {s: (c / total_words) * 100 for s, c in word_counts.items()}

    turnshare_score = 100 - sum(abs(ideal_share - p) for p in turn_percentages.values())
    wordshare_score = 100 - sum(abs(ideal_share - p) for p in word_percentages.values())

    interruption_rate = (interruptions / total_turns) * 100 if total_turns > 0 else 0

    raw_score = turnshare_score + wordshare_score - interruption_rate

    normalized_score = ((raw_score + 100) / 300) * 100
    normalized_score = max(0, min(100, normalized_score))

    return (
        dict(turn_counts),
        "Turn counts: " + str(dict(turn_counts)),
        "Word counts: " + str(dict(word_counts)),
        "Turn percentages: " + str({k: round(v, 2) for k, v in turn_percentages.items()}),
        "Word percentages: " + str({k: round(v, 2) for k, v in word_percentages.items()}),
        "Interruptions: " + str(interruptions),
        "Interruption rate: " + str(round(interruption_rate, 2)),
        "Normalized Conversational Balance Score (0-100): " + str(round(normalized_score, 2))
    )

def sentimentBaseAnalysis(segments, turn_counts):
    from nltk.sentiment import SentimentIntensityAnalyzer
    from sklearn.linear_model import LinearRegression
    import numpy as np

    sia = SentimentIntensityAnalyzer()

    speaker_sentiments = {}

    for i, doc in enumerate(segments):
        speaker = doc["speaker"]
        text = doc["text"]

        score = sia.polarity_scores(text)["compound"]

        if speaker not in speaker_sentiments:
            speaker_sentiments[speaker] = []

        speaker_sentiments[speaker].append((i, score))  # keep order index

    speaker_slopes = {}

    for speaker, values in speaker_sentiments.items():
        indices = np.array([v[0] for v in values]).reshape(-1, 1)
        scores = np.array([v[1] for v in values])

        model = LinearRegression()
        model.fit(indices, scores)

        slope = model.coef_[0]
        speaker_slopes[speaker] = slope

    normalized_scores = {}

    for key in turn_counts:
        score = speaker_slopes.get(key, 0) * turn_counts[key]
        normalized_score = (score + 1) / len(turn_counts)
        normalized_scores[key] = normalized_score

    return "Speaker Sentiment: " + str(normalized_scores), speaker_sentiments

def speakerBaseVolatility(speaker_sentiments):

    speaker_volatility = {}

    for speaker, values in speaker_sentiments.items():
        scores = np.array([v[1] for v in values])
        volatility = np.std(scores)
        speaker_volatility[speaker] = volatility

    return "Speaker volatility: " + str(speaker_volatility)



# Example usage
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RAG Coach Assistant")
    parser.add_argument("--optimised", choices=["yes", "no"], default="yes", help="Choose between yes (optimised - yes will use the optimised version of the pdf context) and no (original) for pdf context")
    args = parser.parse_args()

    if args.optimised == "yes":
        logger.info("!!Using optimised mode")
        logger.info("%s", "-" * 50)
        pdf_context_optimised = True
    else:
        logger.info("!!Using original mode")
        logger.info("%s", "-" * 50)
        pdf_context_optimised = False
    # Initialize RAG
    rag = RAGQuery(
            index_name=PINECONE_INDEX_NAME,
            embedding_model_name=RETRIEVAL_EMBED_MODEL,
            llm_model_name=RETRIEVAL_MODEL,
            doc_namespace="documents", 
            mem_namespace="history" 
        )
    
    rag.clear_memory()

    #json_path = "./transcripts/Bed002_meeting_transcript.json"    
    json_path = "./michelle_1_scenario_1.json"
    logger.info("--- Loading transcript from: %s ---", json_path)
    all_docs = rag.load_custom_transcript(json_path)

    # ----------------------------- Metrics -----------------------------
    # Definitions are found in prompt.py
    transcripts = load_custom_transcript(json_path)
    turn_counts, turnCounts, wordCounts, turnPercentages, wordPercentages, interruptionsResult, interruptionRate, convoScore = obtainMetrics()
    normalized_sentiment_scores, speaker_sentiments = sentimentAnalysis(turn_counts)
    speaker_volaitility = speakerVolatility(speaker_sentiments)
    # ----------------------------- Calculated Metrics -----------------------------
    logger.info("Calculated Metrics: %s", calculated_metrics)
    calculated_metrics = COACHING_SCORE_DEFINITION + "\n" + turnCounts + "\n" + wordCounts + "\n" + turnPercentages + "\n" + wordPercentages + "\n" + interruptionsResult + "\n" + interruptionRate + "\n" + convoScore \
+ "\n" + SENTIMENT_SCORE_DEFINITION + "\n" + normalized_sentiment_scores + "\n" + VOLATILITY_SCORE_DEFINITION + "\n" + speaker_volaitility
    calculated_metrics = calculated_metrics.replace("{", "{{").replace("}", "}}")
    opening, middle, closing = rag.get_strategic_segments(all_docs, window_size=15)
    
    my_context = "The team is currently struggling with 'spatial intent' definitions. Speaker B is the project lead, and Speaker C is a technical consultant."

    report = rag.run_trend_analysis(opening, middle, closing, user_input=my_context)
    
    logger.info("%s DIAGNOSTIC REPORT %s", "=" * 30, "=" * 30)
    logger.info("%s", report)
    logger.info("%s", "=" * 79)

    queries = rag._extract_queries(report)
    logger.info("Extracted Search Queries:")
    for q in queries:
        logger.info(" - %s", q)

    # We want to exit for now
    #sys.exit(1)


    # ---  Step 2  ---
    
    #pdf_context = rag.get_pdf_knowledge(queries)
    #print("pdf_context: ", pdf_context)
    if pdf_context_optimised:
        logger.info("%s", "*" * 50)
        logger.info("pdf_context_optimised is chosen and will be used")
        logger.info("%s", "*" * 50)
        
        pdf_context_optimised = rag.get_pdf_knowledge_optimised(queries)
        
    else:
        logger.info("%s", "*" * 50)
        logger.info("pdf_context is chosen and will be used")
        logger.info("%s", "*" * 50)
        
        pdf_context = rag.get_pdf_knowledge(queries)

    
    
    #target_speaker = input("\nWhich speaker is the primary focus? ").strip()
    target_speaker = "B" # commenting to store logs 
    
    logger.info("🔍 Fetching ALL historical trends for %s...", target_speaker)
    
    past_matches = rag.retrieve_context(
        f"Coaching history and behavioral trends for {target_speaker}", 
        top_k=10, 
        namespace=rag.mem_namespace
    )

    past_history_text = "\n---\n".join([m.metadata.get('text', "") for m in past_matches]) if past_matches else "No previous history found."

    #final_strategy = rag.execute_final_synthesis(report, past_history_text, pdf_context)
    final_strategy = rag.execute_final_synthesis(report, past_history_text, pdf_context_optimised)
    logger.info("%s FINAL COACHING STRATEGY %s", "★" * 20, "★" * 20)
    logger.info("%s", final_strategy)

    logger.info("💾 Saving session to memory namespace: %s", rag.mem_namespace)
    rag.save_to_memory(target_speaker, report, final_strategy)
    

    logger.info("✅ All Design-specific memory blocks have been synchronized to Pinecone.")

    # 
    # test_mem = rag.memory_search.similarity_search("C", k=2)
    # for i, m in enumerate(test_mem):
    #     print(f"\n--- Memory Block {i} ---\n{m.page_content}")

    # ---  Step 3  ---
    # Commented for comparing evaluatiobn metrics 
    #rag.chat_with_coach_assistant(all_docs, final_strategy)


        
