# 4.4 Evaluation Metrics Implementation

def calculate_relevance_score(query_ingredients, recommended_recipes):
    """Calculate how well recommended recipes match input ingredients"""
    # For each recommended recipe, count the overlap with query ingredients
    scores = []
    for recipe in recommended_recipes:
        # Assume recipe['main_ingredients'] is a comma-separated string
        recipe_ingredients = [i.strip().lower() for i in recipe.get('main_ingredients', '').split(',')]
        overlap = set(query_ingredients).intersection(set(recipe_ingredients))
        if recipe_ingredients:
            score = len(overlap) / len(recipe_ingredients)
        else:
            score = 0
        scores.append(score)
    # Return average relevance score across all recommended recipes
    return sum(scores) / len(scores) if scores else 0

def calculate_diversity_score(recommended_recipes):
    """Measure diversity in cuisine types and meal types"""
    cuisines = set()
    meal_types = set()
    for recipe in recommended_recipes:
        cuisines.add(recipe.get('cuisine_type', '').lower())
        meal_types.add(recipe.get('meal_type', '').lower())
    # Diversity is the average of unique cuisines and meal types present
    diversity = (len(cuisines) + len(meal_types)) / 2
    return diversity

def calculate_hit_rate(evaluation_queries, rag_responses):
    """Calculate hit rate for expected recipe types"""
    hits = 0
    total = len(evaluation_queries)
    for query, response in zip(evaluation_queries, rag_responses):
        expected = set([r.lower() for r in query.get('expected_recipes', [])])
        # Assume response is a list of recipe dicts with 'recipe_name'
        recommended = set([r['recipe_name'].lower() for r in response])
        if expected & recommended:
            hits += 1
    return hits / total if total else 0

def llm_as_judge_evaluation(query, response, client=None):
    """Use GPT-4o-mini to evaluate response quality"""
    judge_prompt = f"""
    Evaluate this recipe recommendation response on a scale of 1-5:
    Query: {query}
    Response: {response}
    
    Rate based on:
    1. Relevance to ingredients (1-5)
    2. Practicality of recipes (1-5)
    3. Clarity of instructions (1-5)
    4. Ingredient substitution suggestions (1-5)
    
    Provide scores and brief explanation.
    """
    if client is None:
        raise ValueError("OpenAI client must be provided for LLM-based evaluation.")
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": judge_prompt}]
    )
    return completion.choices[0].message.content.strip()