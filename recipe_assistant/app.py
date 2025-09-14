"""
Flask API for Recipe Assistant.
 Exposes endpoints for question answering and feedback collection.
 Uses advanced RAG pipeline (cover, hybrid, LLM rerank) via rag.py/retrieval.py.
 Logs conversations and feedback to PostgreSQL via db.py.
 Designed for containerization and cloud deployment (e.g., AWS EC2).
"""

import uuid
import os
import logging
from prometheus_client import start_http_server, Counter
from flask import Flask, request, jsonify
from recipe_assistant.rag import rag  # Advanced RAG pipeline (uses retrieval.py)
from recipe_assistant import db  # Database logging
# Distributed Tracing: OpenTelemetry/Tempo
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry import trace

os.makedirs('logs', exist_ok=True)  # Ensure the logs directory exists

# Monitoring: Logging for Grafana/Loki
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)

# Prometheus metrics
questions_total = Counter('api_questions_total', 'Total questions received by API')
errors_total = Counter('api_errors_total', 'Total API errors')
feedback_total = Counter('feedback_total', 'Total feedback received')
positive_feedback_total = Counter('positive_feedback_total', 'Total positive feedback received')
negative_feedback_total = Counter('negative_feedback_total', 'Total negative feedback received')
start_http_server(8000, "0.0.0.0")  # Exposes metrics at :8000/metrics

app = Flask(__name__)

trace.set_tracer_provider(TracerProvider())
# The endpoint should include /v1/traces for OTLP HTTP
span_processor = BatchSpanProcessor(
    OTLPSpanExporter(endpoint="http://tempo:4318/v1/traces")
)
trace.get_tracer_provider().add_span_processor(span_processor)
FlaskInstrumentor().instrument_app(app)

@app.route("/question", methods=["POST"])
def handle_question():
    """
    Accepts a POST request with a JSON payload: {"question": "..."}
    Runs the RAG pipeline and returns the answer and conversation_id.
    """
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("handle_question"):
        data = request.json
        question = data.get("question")
        approach = data.get("approach")
        if not question:
            logging.error("No question provided in /question endpoint")
            errors_total.inc()
            return jsonify({"error": "No question provided"}), 400

        conversation_id = str(uuid.uuid4())
        logging.info(f"Received question: {question} (conversation_id={conversation_id}, approach={approach})")
        questions_total.inc()

        # Run the RAG pipeline (default: best approach)
        answer_data = rag(
            question,
            approach=approach or os.getenv("RETRIEVAL_APPROACH", "best")
        )

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
        logging.info(f"Answered question for conversation_id={conversation_id}")
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
        logging.error("Invalid feedback input in /feedback endpoint")
        errors_total.inc()
        return jsonify({"error": "Invalid input"}), 400
    
    if feedback == 1:
        positive_feedback_total.inc()
    else:
        negative_feedback_total.inc()
        
    logging.info(f"Received feedback: {feedback} for conversation_id={conversation_id}")
    feedback_total.inc()
    db.save_feedback(
        conversation_id=conversation_id,
        feedback=feedback,
    )

    result = {
        "message": f"Feedback received for conversation {conversation_id}: {feedback}"
    }
    logging.info(f"Feedback processed for conversation_id={conversation_id}")
    return jsonify(result)

@app.route("/health", methods=["GET"])
def health_check():
    """Simple health check endpoint for monitoring and cloud deployment."""
    return jsonify({"status": "ok"})

# Force log output for testing
logging.info("Recipe Assistant app started.")

if __name__ == "__main__":
    # For local development only; use gunicorn or similar in production
    app.run(host="0.0.0.0", port=int(os.getenv("APP_PORT", 5000)), debug=True)