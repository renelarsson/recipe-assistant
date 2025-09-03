"""
Database preparation script for Recipe Assistant.
This script initializes the PostgreSQL database schema by creating (or recreating) the required tables.
It is intended to be run manually during setup or when resetting the database.
"""

import os
from dotenv import load_dotenv

# Disable timezone check when initializing the database (for clean output)
os.environ['RUN_TIMEZONE_CHECK'] = '0'

from .db import init_db  # Import the database initialization function

# Load environment variables from .env file (e.g., DB credentials)
load_dotenv()

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Database initialized successfully.")