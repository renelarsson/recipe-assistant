
import os
import dlt
import pandas as pd
from dotenv import load_dotenv


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
        df = pd.read_csv(csv_path)
        yield df.to_dict(orient="records")

    return recipes

if __name__ == "__main__":
    pipeline = dlt.pipeline(
        pipeline_name="recipe_ingestion",
        destination="postgres",
        dataset_name="recipe_data"
    )
    # DLT will pick up credentials from environment variables loaded above
    load_info = pipeline.run(recipe_data_source())
    print(load_info)
