import uuid
from flask import Flask, request, jsonify
from rag import rag  # Import the RAG pipeline for serving live user queries
import db            # Import database utility functions

# Initialize Flask app
app = Flask(__name__)

# Flask URL endpoint decorator listens for HTTP POST requests sent to the /question path
@app.route("/question", methods=["POST"]) # Creates a virtual route 
def handle_question(): # Called by Flask when a client sends a POST to process the user's recipe question
    data = request.json
    question = data["question"]

    # Validate input
    if not question:
        return jsonify({"error": "No question provided"}), 400

    # Generate a unique conversation ID for tracking
    conversation_id = str(uuid.uuid4())

    # Call the RAG pipeline to get an answer for the question
    answer_data = rag(question)

    # Prepare the response
    result = {
        "conversation_id": conversation_id,
        "question": question,
        "answer": answer_data["answer"],
    }

    # Save the conversation to the database
    db.save_conversation(
        conversation_id=conversation_id,
        question=question,
        answer_data=answer_data,
    )

    return jsonify(result)

# Endpoint to handle user feedback on answers
@app.route("/feedback", methods=["POST"])
def handle_feedback():
    data = request.json
    conversation_id = data["conversation_id"]
    feedback = data["feedback"]

    # Validate input: feedback must be 1 (positive) or -1 (negative)
    if not conversation_id or feedback not in [1, -1]:
        return jsonify({"error": "Invalid input"}), 400

    # Save the feedback to the database
    db.save_feedback(
        conversation_id=conversation_id,
        feedback=feedback,
    )

    result = {
        "message": f"Feedback received for conversation {conversation_id}: {feedback}"
    }
    return jsonify(result)

# Run the Flask app in debug mode if executed directly
if __name__ == "__main__":
    app.run(debug=True)

# ----------------------------------------------------------------------
# This file implements a simple Flask API for a recipe assistant.
# - For production, relevant notebook logic is moved into this Python module.
# - The /question endpoint accepts a user question, generates an answer using a RAG pipeline,
#   saves the conversation, and returns the answer with a unique conversation ID.
# - The /feedback endpoint allows users to submit feedback (positive/negative) on a conversation,
#   which is saved for future analysis or improvement.
# - All data persistence is handled through the db module.