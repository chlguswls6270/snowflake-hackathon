from __future__ import annotations
from typing import TYPE_CHECKING
import os
import re
from dotenv import load_dotenv
if TYPE_CHECKING:
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
    
    required = ("account", "user", "password", "warehouse")
    if any(not connection_parameters[key] for key in required):
        raise RuntimeError("Snowflake connection settings are incomplete.")
    get_db_names()  # Validate configured identifiers before opening a session.

    from snowflake.snowpark import Session

    # Create the Snowflake Session
    session = Session.builder.configs(connection_parameters).create()
    return session

def get_db_names():
    """Validate and quote configured database identifiers, never request input."""
    names = {}
    for key in ("richgo", "ajd", "sph"):
        value = os.getenv(f"SNOWFLAKE_DB_{key.upper()}", "")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", value):
            raise RuntimeError(f"Invalid SNOWFLAKE_DB_{key.upper()} configuration.")
        names[key] = f'"{value}"'
    return names

