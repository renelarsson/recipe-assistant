
"""
Automated feedback generator for Recipe Assistant API.
- Sends 100 random questions from data/ground-truth-retrieval.csv to the API.
- Evaluates the relevance of each answer using the LLM-as-judge prompt (RELEVANT, PARTLY_RELEVANT, NON_RELEVANT).
- Only sends negative feedback (-1) for NON_RELEVANT answers; otherwise sends positive feedback (+1).
- Designed to populate monitoring dashboards with realistic feedback and relevance data.
"""

import pandas as pd
import requests
import time
import random
import os

API_URL = os.getenv("API_URL", "http://localhost:5000")
GT_PATH = os.getenv("GT_PATH", "data/ground-truth-retrieval.csv")
N = 100

# LLM-as-judge prompt (should match the one used in evaluation)
JUDGE_PROMPT = """
You are an expert evaluator for a RAG system.\nYour task is to analyze the relevance of the generated answer to the given question.\nBased on the relevance of the generated answer, you will classify it\nas \"NON_RELEVANT\", \"PARTLY_RELEVANT\", or \"RELEVANT\".\n\nHere is the data for evaluation:\n\nQuestion: {question}\nGenerated Answer: {answer}\n\nPlease analyze the content and context of the generated answer in relation to the question\nand provide your evaluation in parsable JSON without using code blocks:\n\n{{\n  \"Relevance\": \"NON_RELEVANT\" | \"PARTLY_RELEVANT\" | \"RELEVANT\",\n  \"Explanation\": \"[Provide a brief explanation for your evaluation]\"\n}}\n+"""

# Use OpenAI API for LLM-as-judge
from openai import OpenAI
client = OpenAI()

# Load 100 random questions
df = pd.read_csv(GT_PATH)
questions = df.sample(n=N, random_state=42).reset_index(drop=True)

results = []

for i, row in questions.iterrows():
    question = row["question"]
    print(f"[{i+1}/{N}] Q: {question}")
    # Send question to API
    try:
        resp = requests.post(f"{API_URL}/question", json={"question": question}, timeout=30)
        resp.raise_for_status()
        answer_data = resp.json()
        answer = answer_data.get("answer") or answer_data.get("llm_answer")
        conversation_id = answer_data.get("conversation_id")
    except Exception as e:
        print(f"  [ERROR] API call failed: {e}")
        continue
    if not answer or not conversation_id:
        print("  [ERROR] Missing answer or conversation_id in API response.")
        continue
    # Judge answer relevance
    prompt = JUDGE_PROMPT.format(question=question, answer=answer)
    try:
        judge_resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=256
        )
        judge_text = judge_resp.choices[0].message.content
        # Parse JSON from LLM response
        import json
        judge_json = json.loads(judge_text)
        relevance = judge_json.get("Relevance") or judge_json.get("relevance")
    except Exception as e:
        print(f"  [ERROR] LLM judge failed: {e}")
        relevance = None
    # Send feedback: -1 for NON_RELEVANT, +1 otherwise
    feedback = -1 if relevance == "NON_RELEVANT" else 1
    try:
        fb_resp = requests.post(f"{API_URL}/feedback", json={"conversation_id": conversation_id, "feedback": feedback}, timeout=10)
        fb_resp.raise_for_status()
        print(f"  [FEEDBACK] Sent {feedback} ({relevance})")
    except Exception as e:
        print(f"  [ERROR] Feedback failed: {e}")
    # Log result
    results.append({
        "question": question,
        "answer": answer,
        "relevance": relevance,
        "feedback": feedback,
        "conversation_id": conversation_id
    })
    # Optional: sleep to avoid rate limits
    time.sleep(1)

# Save results for reference
pd.DataFrame(results).to_csv("feedback_generation_results.csv", index=False)
print("Done. Results saved to feedback_generation_results.csv.")
