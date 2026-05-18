"""
SNOMED CT Data Loader for Neo4j Aura DB
This script reads SNOMED CT data files and loads them into Neo4j Aura database.
"""

import csv
import logging
import os
from pathlib import Path
from typing import Dict, List

import pandas as pd
from dotenv import load_dotenv
from langchain_community.graphs import Neo4jGraph
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SNOMEDLoader:
    """Load SNOMED CT data into Neo4j Aura database"""
    
    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        """
        Initialize connection to Neo4j Aura
        
        Args:
            uri: Neo4j Aura URI (e.g., 'neo4j+s://xxxxx.databases.neo4j.io')
            username: Neo4j username
            password: Neo4j password
            database: Database name (default: 'neo4j')
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        
        # Initialize LangChain Neo4j graph
        self.graph = Neo4jGraph(
            url=uri,
            username=username,
            password=password,
            database=database
        )
        
        # Also keep direct driver for batch operations
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        
    def close(self):
        """Close database connection"""
        self.driver.close()
        
    def create_indexes(self):
        """Create indexes for better performance"""
        logger.info("Creating indexes...")
        
        indexes = [
            "CREATE INDEX concept_id IF NOT EXISTS FOR (c:Concept) ON (c.conceptId)",
            "CREATE INDEX description_id IF NOT EXISTS FOR (d:Description) ON (d.descriptionId)",
            "CREATE INDEX relationship_id IF NOT EXISTS FOR (r:Relationship) ON (r.relationshipId)",
        ]
        
        for index in indexes:
            self.graph.query(index)
            
        logger.info("Indexes created successfully")
    
    def load_concepts(self, concepts_file: str, batch_size: int = 1000):
        """
        Load SNOMED CT concepts from file
        
        Args:
            concepts_file: Path to concepts file (TSV format)
            batch_size: Number of records to process in each batch
        """
        logger.info(f"Loading concepts from {concepts_file}...")
        
        # Read concepts file
        df = pd.read_csv(concepts_file, sep='\t', dtype=str, low_memory=False)
        
        # Filter active concepts
        df = df[df['active'] == '1']
        
        query = """
        UNWIND $batch AS row
        MERGE (c:Concept {conceptId: row.id})
        SET c.effectiveTime = row.effectiveTime,
            c.active = row.active,
            c.moduleId = row.moduleId,
            c.definitionStatusId = row.definitionStatusId
        """
        
        # Process in batches
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]
            batch_data = [
                {
                    'id': row['id'],
                    'effectiveTime': row['effectiveTime'],
                    'active': row['active'],
                    'moduleId': row['moduleId'],
                    'definitionStatusId': row['definitionStatusId']
                }
                for _, row in batch.iterrows()
            ]
            
            self.graph.query(query, {'batch': batch_data})
            
            if (i + batch_size) % 10000 == 0:
                logger.info(f"Processed {i + batch_size} concepts...")
        
        logger.info(f"Loaded {len(df)} concepts successfully")
    
    def load_descriptions(self, descriptions_file: str, batch_size: int = 1000):
        """
        Load SNOMED CT descriptions
        
        Args:
            descriptions_file: Path to descriptions file (TSV format)
            batch_size: Number of records to process in each batch
        """
        logger.info(f"Loading descriptions from {descriptions_file}...")
        
        df = pd.read_csv(descriptions_file, sep='\t', dtype=str, low_memory=False)
        df = df[df['active'] == '1']
        
        query = """
        UNWIND $batch AS row
        MERGE (d:Description {descriptionId: row.id})
        SET d.effectiveTime = row.effectiveTime,
            d.active = row.active,
            d.moduleId = row.moduleId,
            d.conceptId = row.conceptId,
            d.languageCode = row.languageCode,
            d.typeId = row.typeId,
            d.term = row.term,
            d.caseSignificanceId = row.caseSignificanceId
        WITH d, row
        MATCH (c:Concept {conceptId: row.conceptId})
        MERGE (c)-[:HAS_DESCRIPTION]->(d)
        """
        
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]
            batch_data = [
                {
                    'id': row['id'],
                    'effectiveTime': row['effectiveTime'],
                    'active': row['active'],
                    'moduleId': row['moduleId'],
                    'conceptId': row['conceptId'],
                    'languageCode': row['languageCode'],
                    'typeId': row['typeId'],
                    'term': row['term'],
                    'caseSignificanceId': row['caseSignificanceId']
                }
                for _, row in batch.iterrows()
            ]
            
            self.graph.query(query, {'batch': batch_data})
            
            if (i + batch_size) % 10000 == 0:
                logger.info(f"Processed {i + batch_size} descriptions...")
        
        logger.info(f"Loaded {len(df)} descriptions successfully")
    
    def load_relationships(self, relationships_file: str, batch_size: int = 1000):
        """
        Load SNOMED CT relationships
        
        Args:
            relationships_file: Path to relationships file (TSV format)
            batch_size: Number of records to process in each batch
        """
        logger.info(f"Loading relationships from {relationships_file}...")
        
        df = pd.read_csv(relationships_file, sep='\t', dtype=str, low_memory=False)
        df = df[df['active'] == '1']
        
        query = """
        UNWIND $batch AS row
        MATCH (source:Concept {conceptId: row.sourceId})
        MATCH (dest:Concept {conceptId: row.destinationId})
        MERGE (source)-[r:RELATED_TO {relationshipId: row.id}]->(dest)
        SET r.effectiveTime = row.effectiveTime,
            r.active = row.active,
            r.moduleId = row.moduleId,
            r.typeId = row.typeId,
            r.characteristicTypeId = row.characteristicTypeId,
            r.modifierId = row.modifierId
        """
        
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]
            batch_data = [
                {
                    'id': row['id'],
                    'effectiveTime': row['effectiveTime'],
                    'active': row['active'],
                    'moduleId': row['moduleId'],
                    'sourceId': row['sourceId'],
                    'destinationId': row['destinationId'],
                    'typeId': row['typeId'],
                    'characteristicTypeId': row['characteristicTypeId'],
                    'modifierId': row['modifierId']
                }
                for _, row in batch.iterrows()
            ]
            
            self.graph.query(query, {'batch': batch_data})
            
            if (i + batch_size) % 10000 == 0:
                logger.info(f"Processed {i + batch_size} relationships...")
        
        logger.info(f"Loaded {len(df)} relationships successfully")
    
    def verify_load(self):
        """Verify the data load with some statistics"""
        logger.info("Verifying data load...")
        
        stats = {
            'concepts': self.graph.query("MATCH (c:Concept) RETURN count(c) as count")[0]['count'],
            'descriptions': self.graph.query("MATCH (d:Description) RETURN count(d) as count")[0]['count'],
            'relationships': self.graph.query("MATCH ()-[r:RELATED_TO]->() RETURN count(r) as count")[0]['count']
        }
        
        logger.info(f"Load Statistics: {stats}")
        return stats


def main():
    """Main execution function"""
    load_dotenv()

    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USERNAME = os.getenv("NEO4J_USER", os.getenv("NEO4J_USERNAME", "neo4j"))
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

    if not NEO4J_URI or not NEO4J_PASSWORD:
        raise SystemExit(
            "Set NEO4J_URI and NEO4J_PASSWORD (and optionally NEO4J_USER) in the environment or .env"
        )

    
    # SNOMED CT file paths - Update with your file locations
    SNOMED_DIR = Path("./snomed_data")
    CONCEPTS_FILE = SNOMED_DIR / "sct2_Concept_Snapshot_INT_20230901.txt"
    DESCRIPTIONS_FILE = SNOMED_DIR / "sct2_Description_Snapshot-en_INT_20230901.txt"
    RELATIONSHIPS_FILE = SNOMED_DIR / "sct2_Relationship_Snapshot_INT_20230901.txt"
    
    # Initialize loader
    loader = SNOMEDLoader(
        uri=NEO4J_URI,
        username=NEO4J_USERNAME or "neo4j",
        password=NEO4J_PASSWORD,
    )
    
    try:
        # Create indexes first
        loader.create_indexes()
        
        # Load data
        loader.load_concepts(str(CONCEPTS_FILE), batch_size=1000)
        loader.load_descriptions(str(DESCRIPTIONS_FILE), batch_size=1000)
        loader.load_relationships(str(RELATIONSHIPS_FILE), batch_size=1000)
        
        # Verify
        loader.verify_load()
        
        logger.info("SNOMED CT data loaded successfully!")
        
    except Exception as e:
        logger.error(f"Error loading SNOMED data: {e}")
        raise
    finally:
        loader.close()


if __name__ == "__main__":
    main()