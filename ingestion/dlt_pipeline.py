
import os
import logging
import dlt
import pandas as pd
from dotenv import load_dotenv
# Prometheus metrics for monitoring
from prometheus_client import start_http_server, Counter

# Monitoring: Logging for Grafana/Loki
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

# Prometheus metrics
ingested_recipes = Counter('ingested_recipes_total', 'Total recipes ingested')
ingestion_errors = Counter('ingestion_errors_total', 'Total ingestion errors')

# Load environment variables from .env in the project root
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(base_dir, ".env")
load_dotenv(dotenv_path)

# Map .env variables to DLT's expected names
os.environ["RECIPE_INGESTION__CREDENTIALS__DATABASE"] = os.getenv(
    "POSTGRES_DB"
)
os.environ["RECIPE_INGESTION__CREDENTIALS__USERNAME"] = os.getenv(
    "POSTGRES_USER"
)
os.environ["RECIPE_INGESTION__CREDENTIALS__PASSWORD"] = os.getenv(
    "POSTGRES_PASSWORD"
)
os.environ["RECIPE_INGESTION__CREDENTIALS__PORT"] = os.getenv(
    "POSTGRES_PORT"
)

# If running locally, override host to localhost, else use .env value
if os.getenv("POSTGRES_HOST") == "postgres":
    os.environ["RECIPE_INGESTION__CREDENTIALS__HOST"] = "localhost"
else:
    os.environ["RECIPE_INGESTION__CREDENTIALS__HOST"] = os.getenv(
        "POSTGRES_HOST"
    )

@dlt.source
def recipe_data_source():
    @dlt.resource(write_disposition="replace")
    def recipes():
        csv_path = os.path.join(base_dir, "data", "recipes_clean.csv")
        logging.info("DLT pipeline: loading data from %s", csv_path)
        df = pd.read_csv(csv_path)
        logging.info("DLT pipeline: loaded %d recipes", len(df))
        yield df.to_dict(orient="records")

    return recipes

if __name__ == "__main__":
    logging.info("DLT pipeline started (main entry point)")
    # Start Prometheus metrics server on port 8001
    start_http_server(8001, "0.0.0.0")
    pipeline = dlt.pipeline(
        pipeline_name="recipe_ingestion",
        destination="postgres",
        dataset_name="recipe_data"
    )
    # DLT will pick up credentials from environment variables loaded above
    try:
        load_info = pipeline.run(recipe_data_source())
        # Count number of recipes ingested
        if load_info and 'loads' in load_info and load_info['loads']:
            total = 0
            for load in load_info['loads']:
                total += load.get('inserted_row_count', 0)
            ingested_recipes.inc(total)
            logging.info(f"Prometheus: Incremented ingested_recipes_total by {total}")
        logging.info("DLT pipeline completed. Load info: %s", load_info)
        print(load_info)
    except Exception as e:
        ingestion_errors.inc()
        logging.error(f"DLT pipeline failed: {e}")
        raise
