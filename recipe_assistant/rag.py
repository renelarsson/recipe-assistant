"""
RAG pipeline for Recipe Assistant using Elasticsearch and OpenAI.
Uses advanced retrieval from retrieval.py and answer evaluation.
"""

import json
from time import time
from openai import OpenAI
from recipe_assistant import retrieval

client = OpenAI()

# Prompt templates for LLM answer generation and evaluation
prompt_template = """
You are an expert chef and culinary assistant. Answer the QUESTION based on the CONTEXT from our recipe database.
Use only the facts from the CONTEXT when answering the QUESTION.

QUESTION: {question}

CONTEXT:
{context}
""".strip()

entry_template = """
Recipe: {recipe_name}
Cuisine: {cuisine_type}
Meal Type: {meal_type}
Difficulty: {difficulty_level}
Prep Time: {prep_time_minutes} minutes
Cook Time: {cook_time_minutes} minutes
Main Ingredients: {main_ingredients}
Instructions: {instructions}
Dietary Info: {dietary_restrictions}
""".strip()

def build_prompt(query, search_results):
    """Builds the prompt for the LLM using retrieved recipes."""
    context = "\n\n".join([entry_template.format(**doc) for doc in search_results])
    prompt = prompt_template.format(question=query, context=context).strip()
    return prompt

def llm(prompt, model="gpt-4o-mini"):
    """Calls OpenAI LLM and returns answer and token stats."""
    response = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}]
    )
    answer = response.choices[0].message.content
    token_stats = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }
    return answer, token_stats

evaluation_prompt_template = """
You are an expert evaluator for a RAG system.
Your task is to analyze the relevance of the generated answer to the given question.
Based on the relevance of the generated answer, you will classify it
as "NON_RELEVANT", "PARTLY_RELEVANT", or "RELEVANT".

Here is the data for evaluation:

Question: {question}
Generated Answer: {answer}

Please analyze the content and context of the generated answer in relation to the question
and provide your evaluation in parsable JSON without using code blocks:

{{
  "Relevance": "NON_RELEVANT" | "PARTLY_RELEVANT" | "RELEVANT",
  "Explanation": "[Provide a brief explanation for your evaluation]"
}}
""".strip()

def evaluate_relevance(question, answer):
    """Evaluates answer relevance using OpenAI LLM."""
    prompt = evaluation_prompt_template.format(question=question, answer=answer)
    evaluation, tokens = llm(prompt, model="gpt-4o-mini")
    try:
        json_eval = json.loads(evaluation)
        return json_eval, tokens
    except json.JSONDecodeError:
        result = {"Relevance": "UNKNOWN", "Explanation": "Failed to parse evaluation"}
        return result, tokens

def calculate_openai_cost(model, tokens):
    """Calculates OpenAI API cost for the given token usage."""
    openai_cost = 0
    if model == "gpt-4o-mini":
        openai_cost = (
            tokens["prompt_tokens"] * 0.00015 + tokens["completion_tokens"] * 0.0006
        ) / 1000
    else:
        print("Model not recognized. OpenAI cost calculation failed.")
    return openai_cost

def es_best_rag_with_rerank(query, model="gpt-4o-mini", num_results=5, max_time=None):
    """
    Best RAG pipeline for Elasticsearch:
    1. Cover Ingredients Search for diversity/coverage.
    2. Hybrid reranking (semantic similarity).
    3. LLM reranking for final ordering.
    4. LLM answer generation and evaluation.
    """
    t0 = time()
    # Step 1 & 2: Cover + Hybrid search (returns a diverse, semantically relevant pool)
    candidates = retrieval.es_cover_then_hybrid_search(query, num_results=num_results, max_time=max_time)
    # Step 3: LLM reranking (returns best ordering for answer context)
    reranked = retrieval.rerank_with_llm(query, candidates, max_time=max_time, model=model)
    # Step 4: Build prompt and get answer
    prompt = build_prompt(query, reranked)
    answer, token_stats = llm(prompt, model=model)
    # Step 5: Evaluate answer relevance
    relevance, rel_token_stats = evaluate_relevance(query, answer)
    t1 = time()
    took = t1 - t0
    openai_cost_rag = calculate_openai_cost(model, token_stats)
    openai_cost_eval = calculate_openai_cost(model, rel_token_stats)
    openai_cost = openai_cost_rag + openai_cost_eval
    answer_data = {
        "answer": answer,
        "model_used": model,
        "response_time": took,
        "relevance": relevance.get("Relevance", "UNKNOWN"),
        "relevance_explanation": relevance.get(
            "Explanation", "Failed to parse evaluation"
        ),
        "prompt_tokens": token_stats["prompt_tokens"],
        "completion_tokens": token_stats["completion_tokens"],
        "total_tokens": token_stats["total_tokens"],
        "eval_prompt_tokens": rel_token_stats["prompt_tokens"],
        "eval_completion_tokens": rel_token_stats["completion_tokens"],
        "eval_total_tokens": rel_token_stats["total_tokens"],
        "openai_cost": openai_cost,
    }
    return answer_data

# For backward compatibility allows support of cover, hybrid and cover+hybrid search
def rag(query, model="gpt-4o-mini", approach="cover"):
    """
    Main RAG pipeline.
    approach: "cover" for cover ingredients search,
              "hybrid" for hybrid search,
              "cover_hybrid" for combined,
              "best" for cover+hybrid+LLM rerank (recommended).
    """
    if approach == "best":
        return es_best_rag_with_rerank(query, model=model)
    t0 = time()
    if approach == "cover":
        search_results = retrieval.es_cover_ingredients_search(query, num_results=5)
    elif approach == "hybrid":
        search_results = retrieval.es_hybrid_search(query, num_results=5)
    elif approach == "cover_hybrid":
        search_results = retrieval.es_cover_then_hybrid_search(query, num_results=5)
    else:
        raise ValueError("Unknown approach: choose 'cover', 'hybrid', 'cover_hybrid', or 'best'")
    prompt = build_prompt(query, search_results)
    answer, token_stats = llm(prompt, model=model)
    relevance, rel_token_stats = evaluate_relevance(query, answer)
    t1 = time()
    took = t1 - t0
    openai_cost_rag = calculate_openai_cost(model, token_stats)
    openai_cost_eval = calculate_openai_cost(model, rel_token_stats)
    openai_cost = openai_cost_rag + openai_cost_eval
    answer_data = {
        "answer": answer,
        "model_used": model,
        "response_time": took,
        "relevance": relevance.get("Relevance", "UNKNOWN"),
        "relevance_explanation": relevance.get(
            "Explanation", "Failed to parse evaluation"
        ),
        "prompt_tokens": token_stats["prompt_tokens"],
        "completion_tokens": token_stats["completion_tokens"],
        "total_tokens": token_stats["total_tokens"],
        "eval_prompt_tokens": rel_token_stats["prompt_tokens"],
        "eval_completion_tokens": rel_token_stats["completion_tokens"],
        "eval_total_tokens": rel_token_stats["total_tokens"],
        "openai_cost": openai_cost,
    }
    return answer_data