"""
Database module for Recipe Assistant.
Handles all interactions with the PostgreSQL database, including:
- Creating tables for conversations and feedback
- Saving and retrieving conversations and user feedback
- Timezone management for consistent timestamps

This module enables persistent storage of user queries, LLM answers, evaluation results, and feedback,
allowing for analytics, monitoring, and improvement of the RAG pipeline.
"""

import os
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime
from zoneinfo import ZoneInfo

# Environment/configuration for timezone handling
RUN_TIMEZONE_CHECK = os.getenv('RUN_TIMEZONE_CHECK', '1') == '1'
TZ_INFO = os.getenv("TZ", "Europe/Berlin")
tz = ZoneInfo(TZ_INFO)

def get_db_connection():
    """
    Establish a connection to the PostgreSQL database using environment variables.
    """
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        database=os.getenv("POSTGRES_DB", "recipe_assistant"),
        user=os.getenv("POSTGRES_USER", "your_username"),
        password=os.getenv("POSTGRES_PASSWORD", "your_password"),
    )

def init_db():
    """
    Initialize the database schema.
    Drops and recreates the 'conversations' and 'feedback' tables.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Drop tables if they exist (for a clean start)
            cur.execute("DROP TABLE IF EXISTS feedback")
            cur.execute("DROP TABLE IF EXISTS conversations")
            # Create conversations table to store each user interaction and LLM answer
            cur.execute("""
                CREATE TABLE conversations (
                    id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    model_used TEXT NOT NULL,
                    response_time FLOAT NOT NULL,
                    relevance TEXT NOT NULL,
                    relevance_explanation TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    eval_prompt_tokens INTEGER NOT NULL,
                    eval_completion_tokens INTEGER NOT NULL,
                    eval_total_tokens INTEGER NOT NULL,
                    openai_cost FLOAT NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
                )
            """)
            # Create feedback table to store user feedback on answers
            cur.execute("""
                CREATE TABLE feedback (
                    id SERIAL PRIMARY KEY,
                    conversation_id TEXT REFERENCES conversations(id),
                    feedback INTEGER NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
                )
            """)
        conn.commit()
    finally:
        conn.close()

def save_conversation(conversation_id, question, answer_data, timestamp=None):
    """
    Save a conversation (user query, LLM answer, evaluation, and metadata) to the database.
    """
    if timestamp is None:
        timestamp = datetime.now(tz)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations
                (id, question, answer, model_used, response_time, relevance,
                relevance_explanation, prompt_tokens, completion_tokens, total_tokens,
                eval_prompt_tokens, eval_completion_tokens, eval_total_tokens, openai_cost, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    conversation_id,
                    question,
                    answer_data["answer"],
                    answer_data["model_used"],
                    answer_data["response_time"],
                    answer_data["relevance"],
                    answer_data["relevance_explanation"],
                    answer_data["prompt_tokens"],
                    answer_data["completion_tokens"],
                    answer_data["total_tokens"],
                    answer_data["eval_prompt_tokens"],
                    answer_data["eval_completion_tokens"],
                    answer_data["eval_total_tokens"],
                    answer_data["openai_cost"],
                    timestamp
                ),
            )
        conn.commit()
    finally:
        conn.close()

def save_feedback(conversation_id, feedback, timestamp=None):
    """
    Save user feedback (e.g., thumbs up/down) for a conversation.
    """
    if timestamp is None:
        timestamp = datetime.now(tz)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feedback (conversation_id, feedback, timestamp) VALUES (%s, %s, COALESCE(%s, CURRENT_TIMESTAMP))",
                (conversation_id, feedback, timestamp),
            )
        conn.commit()
    finally:
        conn.close()

def get_recent_conversations(limit=5, relevance=None):
    """
    Retrieve the most recent conversations, optionally filtered by relevance.
    Returns a list of conversation records (with feedback if available).
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            query = """
                SELECT c.*, f.feedback
                FROM conversations c
                LEFT JOIN feedback f ON c.id = f.conversation_id
            """
            if relevance:
                query += f" WHERE c.relevance = '{relevance}'"
            query += " ORDER BY c.timestamp DESC LIMIT %s"
            cur.execute(query, (limit,))
            return cur.fetchall()
    finally:
        conn.close()

def get_feedback_stats():
    """
    Get aggregate feedback statistics (number of thumbs up/down).
    Returns a dictionary with counts.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT
                    SUM(CASE WHEN feedback > 0 THEN 1 ELSE 0 END) as thumbs_up,
                    SUM(CASE WHEN feedback < 0 THEN 1 ELSE 0 END) as thumbs_down
                FROM feedback
            """)
            return cur.fetchone()
    finally:
        conn.close()

def check_timezone():
    """
    Utility for debugging timezone handling between Python and PostgreSQL.
    Prints current time in various formats and tests round-trip insertion.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW timezone;")
            db_timezone = cur.fetchone()[0]
            print(f"Database timezone: {db_timezone}")

            cur.execute("SELECT current_timestamp;")
            db_time_utc = cur.fetchone()[0]
            print(f"Database current time (UTC): {db_time_utc}")

            db_time_local = db_time_utc.astimezone(tz)
            print(f"Database current time ({TZ_INFO}): {db_time_local}")

            py_time = datetime.now(tz)
            print(f"Python current time: {py_time}")

            # Insert a test conversation to check timestamp handling
            cur.execute("""
                INSERT INTO conversations
                (id, question, answer, model_used, response_time, relevance,
                relevance_explanation, prompt_tokens, completion_tokens, total_tokens,
                eval_prompt_tokens, eval_completion_tokens, eval_total_tokens, openai_cost, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING timestamp;
            """,
            ('test', 'test question', 'test answer', 'test model', 0.0, 0.0,
             'test explanation', 0, 0, 0, 0, 0, 0, 0.0, py_time))

            inserted_time = cur.fetchone()[0]
            print(f"Inserted time (UTC): {inserted_time}")
            print(f"Inserted time ({TZ_INFO}): {inserted_time.astimezone(tz)}")

            cur.execute("SELECT timestamp FROM conversations WHERE id = 'test';")
            selected_time = cur.fetchone()[0]
            print(f"Selected time (UTC): {selected_time}")
            print(f"Selected time ({TZ_INFO}): {selected_time.astimezone(tz)}")

            cur.execute("DELETE FROM conversations WHERE id = 'test';")
            conn.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

# Optionally run timezone check at import (for debugging)
if RUN_TIMEZONE_CHECK:
    check_timezone()