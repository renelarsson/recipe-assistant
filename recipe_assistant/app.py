"""
Flask API for Recipe Assistant.
- Exposes endpoints for question answering and feedback collection.
- Uses advanced RAG pipeline (cover, hybrid, LLM rerank) via rag.py/retrieval.py.
- Logs conversations and feedback to PostgreSQL via db.py.
- Designed for containerization and cloud deployment (e.g., AWS EC2).
"""

import uuid
import os
from flask import Flask, request, jsonify
from rag import rag  # Advanced RAG pipeline (uses retrieval.py)
import db  # Database logging

app = Flask(__name__)

@app.route("/question", methods=["POST"])
def handle_question():
    """
    Accepts a POST request with a JSON payload: {"question": "..."}
    Runs the RAG pipeline and returns the answer and conversation_id.
    """
    data = request.json
    question = data.get("question")
    approach = data.get("approach")  # Optional: allow user to select retrieval approach

    if not question:
        return jsonify({"error": "No question provided"}), 400

    conversation_id = str(uuid.uuid4())

    # Run the RAG pipeline (default: best approach)
    answer_data = rag(question, approach=approach or os.getenv("RETRIEVAL_APPROACH", "best"))

    # Log the conversation to the database
    db.save_conversation(
        conversation_id=conversation_id,
        question=question,
        answer_data=answer_data,
    )

    result = {
        "conversation_id": conversation_id,
        "question": question,
        "answer": answer_data["answer"],
        "relevance": answer_data.get("relevance"),
        "relevance_explanation": answer_data.get("relevance_explanation"),
        "model_used": answer_data.get("model_used"),
        "response_time": answer_data.get("response_time"),
        "openai_cost": answer_data.get("openai_cost"),
    }
    return jsonify(result)

@app.route("/feedback", methods=["POST"])
def handle_feedback():
    """
    Accepts a POST request with a JSON payload: {"conversation_id": "...", "feedback": 1 or -1}
    Logs user feedback to the database.
    """
    data = request.json
    conversation_id = data.get("conversation_id")
    feedback = data.get("feedback")

    if not conversation_id or feedback not in [1, -1]:
        return jsonify({"error": "Invalid input"}), 400

    db.save_feedback(
        conversation_id=conversation_id,
        feedback=feedback,
    )

    result = {
        "message": f"Feedback received for conversation {conversation_id}: {feedback}"
    }
    return jsonify(result)

@app.route("/health", methods=["GET"])
def health_check():
    """Simple health check endpoint for monitoring and cloud deployment."""
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    # For local development only; use gunicorn or similar in production
    app.run(host="0.0.0.0", port=int(os.getenv("APP_PORT", 5000)), debug=True)