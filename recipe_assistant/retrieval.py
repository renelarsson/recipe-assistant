"""
Advanced retrieval module for the Recipe Assistant using Elasticsearch.
Implements cover ingredients search, hybrid search (keyword + embedding), and reranking.
"""

import os
import numpy as np
import re
from elasticsearch import Elasticsearch
from openai import OpenAI

# Elasticsearch index and embedding config
ES_INDEX = os.getenv("ES_INDEX", "recipes")
EMBEDDING_DIM = 1536  # OpenAI text-embedding-3-small

# Initialize Elasticsearch and OpenAI clients
es_client = Elasticsearch(os.getenv("ES_URL", "http://localhost:9200"))
openai_client = OpenAI()

def get_embedding(text):
    """Get OpenAI embedding for a given text (for semantic search)."""
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=[text]
    )
    return np.array(response.data[0].embedding)

def filter_by_max_time(results, max_time=None):
    """Filter recipes by total prep + cook time."""
    if max_time is None:
        return results
    filtered = []
    for doc in results:
        try:
            total_time = int(doc.get('prep_time_minutes', 0)) + int(doc.get('cook_time_minutes', 0))
        except Exception:
            total_time = 99999
        if total_time <= max_time:
            filtered.append(doc)
    return filtered

def deduplicate_results(results):
    """Deduplicate results by unique id or recipe_name+times."""
    seen = set()
    deduped = []
    for doc in results:
        key = doc.get('id') or (doc.get('recipe_name'), doc.get('prep_time_minutes'), doc.get('cook_time_minutes'))
        if key not in seen:
            seen.add(key)
            deduped.append(doc)
    return deduped

def es_basic_search(query, num_results=5, max_time=None):
    """Basic keyword search using Elasticsearch's multi_match."""
    search_query = {
        "size": num_results * 2,
        "query": {
            "multi_match": {
                "query": query,
                "fields": [
                    "recipe_name",
                    "main_ingredients^2",
                    "all_ingredients^3",
                    "instructions^1.5",
                    "cuisine_type",
                    "dietary_restrictions^1.5"
                ],
                "type": "best_fields"
            }
        }
    }
    response = es_client.search(index=ES_INDEX, body=search_query)
    result_docs = [hit['_source'] for hit in response['hits']['hits']]
    if max_time is not None:
        result_docs = filter_by_max_time(result_docs, max_time)
    return result_docs[:num_results]

def es_hybrid_search(query, num_results=5, max_time=None):
    """
    Hybrid search: combines keyword and embedding similarity.
    Requires all_ingredients_vector field in ES.
    """
    query_vector = get_embedding(query).tolist()
    search_query = {
        "size": num_results * 2,
        "query": {
            "script_score": {
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": [
                            "main_ingredients^2",
                            "all_ingredients^3",
                            "instructions^1.5",
                            "cuisine_type",
                            "dietary_restrictions^1.5",
                            "recipe_name"
                        ],
                        "type": "best_fields"
                    }
                },
                "script": {
                    "source": "cosineSimilarity(params.query_vector, 'all_ingredients_vector') + 1.0",
                    "params": {"query_vector": query_vector},
                }
            }
        }
    }
    response = es_client.search(index=ES_INDEX, body=search_query)
    result_docs = [hit['_source'] for hit in response['hits']['hits']]
    if max_time is not None:
        result_docs = filter_by_max_time(result_docs, max_time)
    deduped_results = deduplicate_results(result_docs)
    return deduped_results[:num_results]

def es_cover_ingredients_search(query, num_results=5, max_time=None, candidate_pool_size=200):
    """
    Cover Ingredients Search: select a set of recipes that together cover as many query ingredients as possible.
    Uses a greedy set cover algorithm on a candidate pool from ES.
    """
    # Step 1: Get a large pool of candidates from ES
    candidates = es_basic_search(query, num_results=candidate_pool_size)
    if max_time is not None:
        candidates = filter_by_max_time(candidates, max_time)
    # Step 2: Greedy cover
    query_tokens = set(re.sub(r'[^\w\s]', '', query.lower()).replace(',', ' ').split())
    uncovered = set(query_tokens)
    selected = []
    docs = candidates.copy()
    while uncovered and len(selected) < num_results and docs:
        best_doc = None
        best_overlap = 0
        for doc in docs:
            ingredients = set(re.sub(r'[^\w\s]', '', str(doc.get('all_ingredients', '')).lower()).replace(',', ' ').split())
            overlap = len(uncovered & ingredients)
            if overlap > best_overlap:
                best_overlap = overlap
                best_doc = doc
        if best_doc and best_overlap > 0:
            selected.append(best_doc)
            ingredients = set(re.sub(r'[^\w\s]', '', str(best_doc.get('all_ingredients', '')).lower()).replace(',', ' ').split())
            uncovered -= ingredients
            docs.remove(best_doc)
        else:
            break
    deduped_results = deduplicate_results(selected)
    return deduped_results

def es_cover_then_hybrid_search(query, num_results=5, max_time=None, hybrid_top_k=5, candidate_pool_size=200):
    """
    Combined Cover + Hybrid: 
    1. Run cover ingredients search for diversity.
    2. Rerank by semantic similarity (embedding) for relevance.
    """
    cover_results = es_cover_ingredients_search(query, num_results=candidate_pool_size, max_time=max_time)
    if not cover_results:
        return []
    query_emb = get_embedding(query)
    cover_embeddings = [
        np.array(doc['all_ingredients_vector']) for doc in cover_results if 'all_ingredients_vector' in doc
    ]
    similarities = [np.dot(query_emb, emb) for emb in cover_embeddings]
    top_indices = np.argsort(similarities)[-hybrid_top_k:][::-1]
    hybrid_results = [cover_results[i] for i in top_indices]
    for doc in hybrid_results:
        doc.pop('all_ingredients_vector', None)
    return hybrid_results[:num_results]

def rerank_with_llm(query, candidates, max_time=None, model="gpt-4o-mini"):
    """
    Rerank a list of candidate recipes using OpenAI LLM.
    Returns the candidates in LLM-ranked order.
    """
    if max_time is not None:
        candidates = filter_by_max_time(candidates, max_time)
    context = "\n\n".join([f"Recipe: {doc['recipe_name']}\nIngredients: {doc['main_ingredients']}" for doc in candidates])
    prompt = f"""
Given the following user query and candidate recipes, rank the recipes from most to least relevant.

Query: {query}

Candidates:
{context}

Return a JSON list of recipe names in ranked order.
""".strip()
    response = openai_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    import json
    content = response.choices[0].message.content
    json_match = re.search(r'\[.*\]', content, re.DOTALL)
    if json_match:
        ranked_names = json.loads(json_match.group())
    else:
        return candidates
    ranked_docs = [doc for name in ranked_names for doc in candidates if doc['recipe_name'] == name]
    return ranked_docs