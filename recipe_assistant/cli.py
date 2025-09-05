"""
Command-line interface (CLI) for the Recipe Assistant.
Allows users to interactively ask for recipe recommendations and provide feedback (+1/-1).
Communicates with the Flask API backend via HTTP requests.
"""

import json
import uuid
import argparse
import requests
import questionary
import pandas as pd

def get_random_question(file_path):
    """Select a random question from a CSV file (for testing or demo)."""
    df = pd.read_csv(file_path)
    return df.sample(n=1).iloc[0]["question"]

def ask_question(url, question):
    """Send a question to the API and return the response."""
    data = {"question": question}
    response = requests.post(url, json=data)
    return response.json()

def send_feedback(url, conversation_id, feedback):
    """Send user feedback (+1/-1) to the API for a given conversation."""
    feedback_data = {"conversation_id": conversation_id, "feedback": feedback}
    response = requests.post(f"{url}/feedback", json=feedback_data)
    return response.status_code

def main():
    parser = argparse.ArgumentParser(
        description="Interactive CLI app for recipe recommendations"
    )
    parser.add_argument(
        "--random", action="store_true", help="Use random questions from the CSV file"
    )
    args = parser.parse_args()

    base_url = "http://localhost:5000"
    csv_file = "../data/ground-truth-retrieval.csv"

    print("Welcome to the Recipe Assistant!")
    print("You can exit the program at any time when prompted.")

    while True:
        # Get question from user or randomly from CSV
        if args.random:
            question = get_random_question(csv_file)
            print(f"\nRandom question: {question}")
        else:
            question = questionary.text("Ask your recipe question (e.g., 'What can I cook with chicken and rice?' or 'What can I bake with milk, flour, sugar, and eggs'):").ask()

        # Ask the API for recipe recommendations
        response = ask_question(f"{base_url}/question", question)
        print("\nRecipe recommendations:", response.get("answer", "No recommendations provided"))

        # Get conversation ID for feedback
        conversation_id = response.get("conversation_id", str(uuid.uuid4()))

        # Prompt user for feedback (+1, -1, or skip)
        feedback = questionary.select(
            "How would you rate this response?",
            choices=["+1 (Positive)", "-1 (Negative)", "Pass (Skip feedback)"],
        ).ask()

        if feedback != "Pass (Skip feedback)":
            feedback_value = 1 if feedback == "+1 (Positive)" else -1
            status = send_feedback(base_url, conversation_id, feedback_value)
            print(f"Feedback sent. Status code: {status}")
        else:
            print("Feedback skipped.")

        # Ask if user wants to continue
        continue_prompt = questionary.confirm("Do you want another recommendation?").ask()
        if not continue_prompt:
            print("Thank you for using Recipe Assistant. Goodbye!")
            break

if __name__ == "__main__":
    main()