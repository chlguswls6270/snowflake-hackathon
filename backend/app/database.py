import os
from dotenv import load_dotenv
from snowflake.snowpark import Session

# Load environment variables from the .env file
load_dotenv()

def get_snowflake_session() -> Session:
    """
    Creates and returns a Snowflake Snowpark session using credentials from .env.
    """
    connection_parameters = {
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "role": os.getenv("SNOWFLAKE_ROLE"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
        # We don't bind to a single database because we will query multiple Marketplace databases.
        # But we do set the default schema.
        "schema": os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC")
    }
    
    # Create the Snowflake Session
    session = Session.builder.configs(connection_parameters).create()
    return session

def get_db_names():
    """
    Returns a dictionary of the Marketplace database names configured in the environment.
    """
    return {
        "richgo": os.getenv("SNOWFLAKE_DB_RICHGO"),
        "ajd": os.getenv("SNOWFLAKE_DB_AJD"),
        "sph": os.getenv("SNOWFLAKE_DB_SPH")
    }
