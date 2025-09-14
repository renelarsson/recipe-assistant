
"""
Command-line interface (CLI) for the Recipe Assistant.
Allows users to interactively ask for recipe recommendations and provide feedback (+1/-1).
Communicates with the Flask API backend via HTTP requests.
"""

import logging
# Prometheus metrics for monitoring
from prometheus_client import start_http_server, Counter
import uuid
import argparse
import requests
import questionary
import pandas as pd

print("cli.py loaded")
# Monitoring: Logging for Grafana/Loki
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

# Prometheus metrics
cli_runs_total = Counter('cli_runs_total', 'Total CLI runs')
cli_errors_total = Counter('cli_errors_total', 'Total CLI errors')

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
    print("main() called")
    # Start Prometheus metrics server on port 8002
    start_http_server(8002, "0.0.0.0")
    parser = argparse.ArgumentParser(
        description="Interactive CLI app for recipe recommendations"
    )
    parser.add_argument(
        "--random",
        action="store_true",
        help="Use random questions from the CSV file"
    )
    args = parser.parse_args()

    base_url = "http://localhost:5000"
    csv_file = "data/ground-truth-retrieval.csv"

    logging.info("CLI started.")
    cli_runs_total.inc()
    print("Welcome to the Recipe Assistant!")
    print("You can exit the program at any time when prompted.")

    while True:
        # Get question from user or randomly from CSV
        if args.random:
            question = get_random_question(csv_file)
            print(f"\nRandom question: {question}")
        else:
            question = questionary.text(
                "Ask your recipe question (e.g., 'What can I cook with chicken and rice?' "
                "or 'What can I bake with milk, flour, sugar, and eggs'):"
            ).ask()
        logging.info(f"CLI question asked: {question}")
        try:
            # Ask the API for recipe recommendations
            response = ask_question(f"{base_url}/question", question)
            logging.info(f"CLI received response: {response}")
            print(
                "\nRecipe recommendations:",
                response.get("answer", "No recommendations provided")
            )
        except Exception as e:
            cli_errors_total.inc()
            logging.error(f"CLI error: {e}")
            print(f"Error: {e}")
            continue

        # Get conversation ID for feedback
        conversation_id = response.get("conversation_id", str(uuid.uuid4()))

        # Prompt user for feedback (+1, -1, or skip)
        feedback = questionary.select(
            "How would you rate this response?",
            choices=[
                "+1 (Positive)",
                "-1 (Negative)",
                "Pass (Skip feedback)"
            ]
        ).ask()

        if feedback != "Pass (Skip feedback)":
            feedback_value = 1 if feedback == "+1 (Positive)" else -1
            status = send_feedback(base_url, conversation_id, feedback_value)
            logging.info(f"CLI feedback sent: {feedback_value} for conversation_id={conversation_id}, status={status}")
            print(f"Feedback sent. Status code: {status}")
        else:
            logging.info("CLI feedback skipped.")
            print("Feedback skipped.")

        # Ask if user wants to continue
        continue_prompt = questionary.confirm(
            "Do you want another recommendation?"
        ).ask()

        if not continue_prompt:
            logging.info("CLI session ended by user.")
            print("Thank you for using Recipe Assistant. Goodbye!")
            break

if __name__ == "__main__":
    main()
        