"""
Ingestion pipeline for Recipe Assistant using Prefect.
Automates loading recipes from CSV, computing embeddings, and indexing into Elasticsearch.
Designed to be scheduled or triggered as part of a larger data workflow.
"""

import time
import os
import logging
import pandas as pd
from elasticsearch import Elasticsearch
from openai import OpenAI
from prefect import flow, task
# Prometheus metrics for monitoring
from prometheus_client import start_http_server, Counter

# Monitoring: Logging for Grafana/Loki
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

# Prometheus metrics
ingest_runs_total = Counter('ingest_runs_total', 'Total ingest.py runs')
ingest_errors_total = Counter('ingest_errors_total', 'Total ingest.py errors')

DATA_PATH = os.getenv("DATA_PATH", "data/recipes_clean.csv")
ES_INDEX = os.getenv("ES_INDEX", "recipes")
EMBEDDING_DIM = 1536

@task
def load_data_task(data_path):
    """Load recipes from CSV file."""
    logging.info("Ingestion started: loading data from %s", data_path)
    df = pd.read_csv(data_path)
    # Limit to 100 rows for test/dev runs
    df = df.head(100)
    if 'id' not in df.columns:
        df['id'] = range(len(df))
    logging.info("Loaded %d recipes from CSV", len(df))
    return df

@task
def compute_embeddings_task(df):
    """Compute OpenAI embeddings for all_ingredients."""
    openai_client = OpenAI()
    logging.info("Computing embeddings for %d recipes", len(df))
    df['all_ingredients_vector'] = df['all_ingredients'].apply(
        lambda x: OpenAI().embeddings.create(
            model="text-embedding-3-small",
            input=[x]
        ).data[0].embedding
    )
    logging.info("Embeddings computed for all recipes")
    return df

@task
def create_es_index_task(es_index):
    """Create Elasticsearch index with appropriate mapping if it doesn't exist."""
    es_client = Elasticsearch(os.getenv("ES_URL", "http://localhost:9200"))
    index_settings = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "properties": {
                "recipe_name": {"type": "text"},
                "main_ingredients": {"type": "text"},
                "all_ingredients": {"type": "text"},
                "instructions": {"type": "text"},
                "cuisine_type": {"type": "text"},
                "dietary_restrictions": {"type": "text"},
                "meal_type": {"type": "keyword"},
                "difficulty_level": {"type": "keyword"},
                "prep_time_minutes": {"type": "integer"},
                "cook_time_minutes": {"type": "integer"},
                "all_ingredients_vector": {
                    "type": "dense_vector",
                    "dims": EMBEDDING_DIM
                }
            }
        }
    }
    if not es_client.indices.exists(index=es_index):
        es_client.indices.create(index=es_index, body=index_settings)
        logging.info("Created Elasticsearch index: %s", es_index)
    else:
        logging.info("Elasticsearch index already exists: %s", es_index)

@task
def index_to_es_task(df, es_index):
    """Index recipes into Elasticsearch."""
    es_client = Elasticsearch(os.getenv("ES_URL", "http://localhost:9200"))
    for doc in df.to_dict(orient="records"):
        es_client.index(index=es_index, document=doc)
    logging.info("Ingested %d recipes into Elasticsearch index '%s'", len(df), es_index)

@flow(name="Recipe Ingestion Pipeline")
def prefect_ingest_flow(
    data_path: str = DATA_PATH,
    es_index: str = ES_INDEX
):
    """Prefect flow to orchestrate the ingestion pipeline."""
    df = load_data_task(data_path)
    df = compute_embeddings_task(df)
    create_es_index_task(es_index)
    index_to_es_task(df, es_index)

if __name__ == "__main__":
    import sys
    logging.info("Ingestion pipeline started (main entry point)")
    # Start Prometheus metrics server on port 8003
    start_http_server(8003, "0.0.0.0")
    ingest_runs_total.inc()
    try:
        if "--no-prefect" in sys.argv:
            # Run as plain script (no Prefect)
            df = load_data_task.fn(DATA_PATH)
            df = compute_embeddings_task.fn(df)
            create_es_index_task.fn(ES_INDEX)
            index_to_es_task.fn(df, ES_INDEX)
        else:
            # Run as Prefect flow (default)
            prefect_ingest_flow()
        logging.info("Ingestion pipeline completed")
    except Exception as e:
        ingest_errors_total.inc()
        logging.error(f"Ingestion pipeline failed: {e}")
        raise
    time.sleep(60) # Only for testing in Docker to keep the container alive briefly