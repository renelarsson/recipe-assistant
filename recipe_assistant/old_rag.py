import json
import re
from time import time
from openai import OpenAI
import ingest

# Initialize OpenAI client and load the recipe index
client = OpenAI()
index = ingest.load_index()

# Query Rewriting with LLM
def rewrite_query(query, model="gpt-4o-mini"):
    """
    Rewrite the user query to be more specific and clear using the LLM.
    This helps improve retrieval relevance.
    """
    prompt = f"Rewrite this user query for a recipe search system to be more specific and clear: '{query}'"
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# Ingredient Coverage Search (default production retrieval) 
def cover_ingredients_search(query, index, num_results=5, max_time=None):
    """
    Selects recipes that together cover as many query ingredients as possible.
    This is the default retrieval method for production, as it maximizes ingredient coverage and diversity.
    """
    query_tokens = set(re.sub(r'[^\w\s]', '', query.lower()).replace(',', ' ').split())
    uncovered = set(query_tokens)
    selected = []
    docs = index.documents.copy()
    while uncovered and len(selected) < num_results and docs:
        best_doc = None
        best_overlap = 0
        for doc in docs:
            # Optionally filter out recipes that take too long
            if max_time is not None:
                try:
                    total_time = int(doc.get('prep_time_minutes', 0)) + int(doc.get('cook_time_minutes', 0))
                except Exception:
                    total_time = 99999
                if total_time > max_time:
                    continue
            # Compute overlap between uncovered ingredients and this recipe's ingredients
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
    return selected

# LLM-based Re-ranking 
def rerank_with_llm(query, candidates, model="gpt-4o-mini"):
    """
    Re-rank candidate recipes using the LLM based on their relevance to the rewritten query.
    The LLM returns a ranked list of recipe names, which is mapped back to the candidate docs.
    """
    if not candidates:
        return []
    context = "\n\n".join([f"Recipe: {doc['recipe_name']}\nIngredients: {doc['main_ingredients']}" for doc in candidates])
    prompt = f"""
Given the following user query and candidate recipes, rank the recipes from most to least relevant.

Query: {query}

Candidates:
{context}

Return a JSON list of recipe names in ranked order.
""".strip()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message.content
    json_match = re.search(r'\[.*\]', content, re.DOTALL)
    if json_match:
        try:
            ranked_names = json.loads(json_match.group())
            ranked_docs = [doc for name in ranked_names for doc in candidates if doc['recipe_name'] == name]
            return ranked_docs
        except Exception:
            return candidates
    return candidates

# Prompt Templates for LLM Generation
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

prompt_template = """
You're a culinary expert and chef. Answer the QUESTION based on the CONTEXT from our recipe database.
Use only the facts from the CONTEXT when answering the QUESTION.

QUESTION: {question}

CONTEXT:
{context}
""".strip()

def build_prompt(query, search_results):
    """
    Build the prompt for the LLM using the selected recipes as context.
    """
    context = ""
    for doc in search_results:
        context += entry_template.format(**doc) + "\n\n"
    prompt = prompt_template.format(question=query, context=context).strip()
    return prompt

def llm(prompt, model="gpt-4o-mini"):
    """
    Call the LLM with the given prompt and return the answer and token usage stats.
    """
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

# LLM-based Answer Evaluation
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
    """
    Use the LLM to evaluate the relevance of the generated answer to the question.
    Returns a JSON with relevance and explanation.
    """
    prompt = evaluation_prompt_template.format(question=question, answer=answer)
    evaluation, tokens = llm(prompt, model="gpt-4o-mini")
    try:
        json_eval = json.loads(evaluation)
        return json_eval, tokens
    except json.JSONDecodeError:
        result = {"Relevance": "UNKNOWN", "Explanation": "Failed to parse evaluation"}
        return result, tokens

def calculate_openai_cost(model, tokens):
    """
    Estimate the OpenAI API cost for the given token usage.
    """
    openai_cost = 0
    if model == "gpt-4o-mini":
        openai_cost = (
            tokens["prompt_tokens"] * 0.00015 + tokens["completion_tokens"] * 0.0006
        ) / 1000
    else:
        print("Model not recognized. OpenAI cost calculation failed.")
    return openai_cost

def rag(query, model="gpt-4o-mini", num_results=5, max_time=None):
    """
    Full RAG pipeline for recipe recommendation:
    1. Rewrite query with LLM for clarity and specificity.
    2. Retrieve recipes using ingredient coverage search (default for production).
    3. Re-rank retrieved recipes with LLM for best relevance.
    4. Build prompt and generate answer with LLM.
    5. Evaluate answer relevance with LLM.
    Returns a dict with answer, stats, and evaluation.
    """
    t0 = time()

    # 1. Query rewriting
    rewritten_query = rewrite_query(query, model=model)

    # 2. Ingredient coverage search (production default)
    search_results = cover_ingredients_search(rewritten_query, index, num_results=num_results, max_time=max_time)

    # 3. LLM-based re-ranking
    reranked_results = rerank_with_llm(rewritten_query, search_results, model=model)

    # 4. Build prompt and get answer from LLM
    prompt = build_prompt(rewritten_query, reranked_results)
    answer, token_stats = llm(prompt, model=model)

    # 5. Evaluate answer relevance
    relevance, rel_token_stats = evaluate_relevance(rewritten_query, answer)

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

# This file implements a full RAG pipeline for recipe recommendations:
# * It rewrites the user query with the LLM for clarity, retrieves recipes using 
#   an ingredient coverage search (to maximize ingredient usage and diversity), 
# * re-ranks the results with the LLM, 
# * builds a prompt for the LLM to generate a final answer, 
# * and evaluates the answer's relevance using the LLM.