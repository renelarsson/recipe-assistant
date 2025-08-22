# 4.2 Implement Three Different Retrieval Approaches
# to compare and evaluate how well each method finds relevant recipes for a user’s query

# Approach 1: Basic Keyword Search
def basic_search(query, index):
    """Basic minsearch with ingredients as keywords: 
    e.g. ["shrimp", "rice"] -> Only recipes that mention both 
    "shrimp" and "rice" directly (in any indexed field) are likely to be retrieved."""
    return index.search(query, num_results=5)

# Approach 2: Ingredient-Focused Search with Boosting
def ingredient_search(query, index):
    """Boost main_ingredients and all_ingredients fields: 
    e.g. ["shrimp", "rice"] -> Recipes where "shrimp" or "rice" are main 
    ingredients will rank higher than those where they are just mentioned elsewhere."""
    return index.search(
        query, 
        num_results=5,
        boost={'main_ingredients': 2.0, 'all_ingredients': 1.5}
    )

# Approach 3: Query Expansion
def query_expansion(query, index):
    """Expand query with related culinary terms: 
    e.g. ["shrimp", "rice"] -> The search will match recipes that mention 
    "shrimp" and "rice", but also "prawns", "shellfish", "seafood", or specific rice types, 
    increasing recall for recipes that use alternative ingredient names."""
    # Add common culinary synonyms and related terms
    expanded_query = expand_culinary_query(query)
    return index.search(expanded_query, num_results=5)

def expand_culinary_query(query):
    # Implement ingredient synonyms and related terms    
    synonyms = {
        'chicken': ['poultry', 'fowl'],
        'pasta': ['noodles', 'spaghetti', 'linguine', 'vermicelli', 'orzo', 'macaroni'],
        'tomatoes': ['tomato', 'roma tomatoes', 'heirloom tomatoes', 'cherry tomatoes'],
        'beef': ['steak', 'ground beef', 'brisket', 'sirloin'],
        'potatoes': ['spuds', 'russet potatoes', 'yukon gold', 'sweet potatoes'],
        'cheese': ['cheddar', 'mozzarella', 'parmesan', 'feta', 'gruyere', 'cream cheese', 'goat cheese'],
        'shrimp': ['prawns', 'shellfish'],
        'eggplant': ['aubergine'],
        'cilantro': ['coriander'],
        'zucchini': ['courgette'],
        'bell pepper': ['capsicum', 'pepper'],
        'rice': ['basmati', 'jasmine', 'arborio', 'brown rice'],
        'fish': ['salmon', 'tuna', 'cod', 'tilapia'],
        'eggs': ['egg', 'yolk', 'egg whites'],
        'spinach': ['greens', 'baby spinach'],
        'lentils': ['dal', 'red lentils', 'green lentils'],
        'tofu': ['bean curd'],
        'mushrooms': ['fungi', 'button mushrooms', 'shiitake', 'portobello'],
        'pork': ['ham', 'bacon', 'sausage'],
        'cream': ['heavy cream', 'double cream'],
        'yogurt': ['greek yogurt', 'curd'],
        'bread': ['loaf', 'toast', 'baguette'],
        'onion': ['red onion', 'yellow onion', 'shallot'],
        'garlic': ['clove', 'garlic paste'],
        'butter': ['margarine', 'ghee'],
        'flour': ['all-purpose flour', 'whole wheat flour'],
        'milk': ['whole milk', 'skim milk', 'dairy'],
        'nuts': ['almonds', 'cashews', 'walnuts', 'pecans'],
        'oil': ['olive oil', 'vegetable oil', 'canola oil'],
        'herbs': ['basil', 'oregano', 'thyme', 'parsley', 'dill'],
        'sugar': ['brown sugar', 'white sugar'],
        'honey': ['nectar'],
        'cucumber': ['gherkin'],
        'carrots': ['baby carrots'],
        'peas': ['snap peas', 'snow peas'],
        'lettuce': ['romaine', 'iceberg'],
        'beets': ['beetroot'],
        'feta': ['feta cheese'],
        'parmesan': ['parmesan cheese'],
        'mozzarella': ['mozzarella cheese'],
        'gruyere': ['gruyere cheese'],
        'cream cheese': ['soft cheese'],
        'goat cheese': ['chèvre'],
        'sour cream': ['creme fraiche'],
        'tortillas': ['wraps', 'flatbread'],
        'basil': ['holy basil'],
        'lime': ['lemon'],
        'avocado': ['guacamole'],
        'cabbage': ['savoy', 'red cabbage'],
        'beans': ['black beans', 'kidney beans', 'pinto beans'],
        'corn': ['maize'],
        'orzo': ['pasta'],
        'noodles': ['ramen', 'udon', 'soba'],
        'nori': ['seaweed'],
        'bacon': ['pancetta'],
        'sausage': ['chorizo'],
        'turkey': ['ground turkey'],
        'duck': ['poultry'],
        'lamb': ['mutton'],
        'apple': ['apples'],
        'banana': ['bananas'],
        'oats': ['oatmeal'],
        'maple syrup': ['syrup'],
        'soy sauce': ['tamari'],
        'vinegar': ['red wine vinegar', 'balsamic'],
        'olives': ['kalamata olives'],
        'pita': ['pita bread'],
        'tahini': ['sesame paste'],
        'cumin': ['jeera'],
        'coriander': ['cilantro'],
        'parsley': ['herbs'],
        'dill': ['herbs'],
        'thyme': ['herbs'],
        'oregano': ['herbs'],
        'basil': ['herbs'],
        'rosemary': ['herbs'],
        'sage': ['herbs'],
        'bay leaf': ['herbs'],
        'chili': ['chili pepper', 'red chili'],
        'pepper': ['black pepper'],
        'salt': ['sea salt'],
        'salsa': ['sauce'],
        'mayonnaise': ['mayo'],
        'mustard': ['dijon'],
        'ketchup': ['tomato sauce'],
        'jam': ['jelly'],
        'pancetta': ['bacon'],
        'parmesan': ['cheese'],
        'feta': ['cheese'],
        'gruyere': ['cheese'],
        'mozzarella': ['cheese'],
        'ricotta': ['cheese'],
        'cheddar': ['cheese'],
        'cream cheese': ['cheese'],
        'goat cheese': ['cheese'],
        'shrimp': ['seafood'],
        'fish': ['seafood'],
        'crab': ['seafood'],
        'lobster': ['seafood'],
        'salmon': ['fish'],
        'tuna': ['fish'],
        'cod': ['fish'],
        'tilapia': ['fish'],
        'prawns': ['shrimp'],
    }

    # Tokenize the query (split by spaces or commas)
    tokens = []
    if isinstance(query, list):
        tokens = query
    elif isinstance(query, str):
        tokens = [q.strip() for q in query.replace(',', ' ').split()]
    else:
        tokens = []

    expanded_tokens = set(tokens)
    for token in tokens:
        lower_token = token.lower()
        if lower_token in synonyms:
            expanded_tokens.update(synonyms[lower_token])

    # Join back into a string for searching
    expanded_query = ' '.join(expanded_tokens)
    return expanded_query