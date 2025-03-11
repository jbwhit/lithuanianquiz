#!/usr/bin/env python

import argparse
import glob
import logging
import os
import re
import sys
from dataclasses import dataclass, fields, make_dataclass
from datetime import datetime
from typing import TypeVar

import pandas as pd

from fastlite import database

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('lithuanian-db')

T = TypeVar('T')

# Base dataclass for numbers table - this represents our "expected" schema
@dataclass
class Numbers:
    number: int
    neoficialiai: str = ""
    compound: str = ""
    years: str = ""
    kokia_kaina: str = ""
    kokia_kaina_compound: str = ""
    euro_nom: str = ""
    cent_nom: str = ""
    kiek_kainuoja: str = ""
    kiek_kainuoja_compound: str = ""
    euro_acc: str = ""
    cent_acc: str = ""
    # Default values for all fields to handle missing columns

@dataclass
class Attempt:
    user_id: int
    number: int
    correct: bool
    timestamp: str
    grammar_tested: str = ""
    exercise_id: int = 0

def read_latest_dated_csv(directory="data", prefix="numbers_"):
    """
    Reads the most recent dated CSV file with format prefix_YYYY-MM-DD.csv

    Args:
        directory (str): Directory to search in
        prefix (str): Prefix of the filename before the date

    Returns:
        pandas.DataFrame: The data from the latest dated CSV file
        str: The filename that was read
    """
    # Create directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)

    # Pattern to match files like "numbers_2025-03-10.csv"
    pattern = os.path.join(directory, f"{prefix}*.csv")
    dated_files = glob.glob(pattern)

    if not dated_files:
        raise FileNotFoundError(f"No CSV files matching {pattern} found in {directory}")

    # Function to extract date from filename and convert to datetime object
    def extract_date(filename):
        # Extract date using regex - looking for YYYY-MM-DD pattern
        match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        if match:
            date_str = match.group(1)
            return datetime.strptime(date_str, "%Y-%m-%d")
        return datetime.min  # Return minimum date if no match

    # Find the most recent file based on the date in the filename
    latest_file = max(dated_files, key=extract_date)

    logger.info(f"Reading the latest dated file: {latest_file}")

    # Read and return the data
    return pd.read_csv(latest_file), latest_file

def get_dataclass_field_names(cls: type[T]) -> set[str]:
    """Get the field names of a dataclass."""
    return {f.name for f in fields(cls)}

def get_dataclass_field_types(cls: type[T]) -> dict[str, type]:
    """Get the field names and types of a dataclass."""
    return {f.name: f.type for f in fields(cls)}

def detect_column_type(series: pd.Series) -> type:
    """Detect the appropriate Python type for a pandas Series."""
    if series.dtype == 'int64':
        return int
    elif series.dtype == 'float64':
        return float
    elif series.dtype == 'bool':
        return bool
    else:
        return str

def generate_dynamic_dataclass(df: pd.DataFrame, base_class: type[T] | None = None,
                               name: str = "DynamicTable") -> type:
    """
    Generate a dataclass dynamically based on DataFrame columns and an optional base class.

    Args:
        df: DataFrame to base the dataclass on
        base_class: Optional base dataclass to incorporate fields from
        name: Name for the generated dataclass

    Returns:
        A new dataclass type
    """
    # Start with fields from base class if provided
    fields_dict = {}
    if base_class:
        fields_dict = get_dataclass_field_types(base_class)

    # Add or update fields from DataFrame
    for column in df.columns:
        if column not in fields_dict:
            # New field - detect type from data
            fields_dict[column] = detect_column_type(df[column])

    # Convert to list of (name, type) tuples for make_dataclass
    fields_list = [(name, type_) for name, type_ in fields_dict.items()]

    # Create and return the dynamic dataclass
    return make_dataclass(name, fields_list)

def backup_database(db_path: str) -> str:
    """Create a backup of the database before making changes."""
    if not os.path.exists(db_path):
        logger.info(f"No existing database to backup at {db_path}")
        return ""

    backup_path = f"{db_path}.{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
    import shutil
    shutil.copy2(db_path, backup_path)
    logger.info(f"Created database backup at {backup_path}")
    return backup_path

def compare_schemas(existing_fields: set, new_fields: set, dynamic_schema: bool, logger) -> None:
    """Log schema differences between existing table and new data."""
    if not existing_fields:
        return

    only_in_existing = existing_fields - new_fields
    only_in_new = new_fields - existing_fields

    if only_in_existing:
        logger.warning(f"Fields in existing table but not in new data: {only_in_existing}")
        logger.warning("These fields will be preserved but may contain NULL values for new records")

    if only_in_new:
        logger.warning(f"Fields in new data but not in existing table: {only_in_new}")
        if dynamic_schema:
            logger.info("Will attempt to add these fields to the table")
        else:
            logger.warning("These fields will be ignored (dynamic_schema=False)")

def process_records(table, records: list, pk_field: str, existing_pks: set, backup_path: str, logger) -> None:
    """Process records, separating into new and updates."""
    # Separate records into new and updates
    new_records = [r for r in records if r[pk_field] not in existing_pks]
    update_records = [r for r in records if r[pk_field] in existing_pks]

    if new_records:
        logger.info(f"Inserting {len(new_records)} new records")
        try:
            table.insert_all(new_records)
        except Exception as e:
            logger.error(f"Error inserting new records: {e}")
            if backup_path:
                logger.info(f"You can restore from backup: {backup_path}")
            raise

    if update_records:
        logger.info(f"Updating {len(update_records)} existing records")
        try:
            for record in update_records:
                pk_value = record[pk_field]
                table.update(record, pk_value)
        except Exception as e:
            logger.error(f"Error updating records: {e}")
            if backup_path:
                logger.info(f"You can restore from backup: {backup_path}")
            raise

def update_database(db_path: str, df: pd.DataFrame, table_name: str,
                    base_class: type[T], pk_field: str,
                    dynamic_schema: bool = True) -> None:
    """
    Update a database table with data from a DataFrame, handling schema changes.

    Args:
        db_path: Path to the database file
        df: DataFrame with new data
        table_name: Name of the table to update
        base_class: Base dataclass defining the expected schema
        pk_field: Primary key field name
        dynamic_schema: Whether to allow dynamic schema adjustment
    """
    # Create backup before changes
    backup_path = backup_database(db_path)

    # Open database connection
    db = database(db_path)

    # Check if table exists
    table_exists = table_name in db.t

    # Generate dynamic dataclass if needed
    data_class = base_class
    if dynamic_schema:
        data_class = generate_dynamic_dataclass(df, base_class, name=table_name.capitalize())
        logger.info(f"Generated dynamic dataclass with fields: {get_dataclass_field_names(data_class)}")

    # Create table if it doesn't exist
    if not table_exists:
        logger.info(f"Creating new table '{table_name}' in database")
        db.create(data_class, name=table_name, pk=pk_field)
    else:
        logger.info(f"Table '{table_name}' already exists in database")

        # Compare schema
        existing_fields = set()
        try:
            # Try to get one row to examine schema
            first_row = next(db.t[table_name].rows)
            existing_fields = set(first_row.keys())
        except (StopIteration, Exception) as e:
            logger.warning(f"Could not examine existing schema: {e}")

        compare_schemas(existing_fields, set(df.columns), dynamic_schema, logger)

    # Convert DataFrame to list of dictionaries
    records = df.to_dict(orient='records')

    # Process records
    table = db.t[table_name]
    if table_exists:
        # Get existing primary keys
        try:
            existing_pks = set(row[pk_field] for row in table.rows)
        except Exception as e:
            logger.error(f"Error getting existing primary keys: {e}")
            existing_pks = set()

        process_records(table, records, pk_field, existing_pks, backup_path, logger)
    else:
        # Insert all records for a new table
        logger.info(f"Inserting {len(records)} records into new table")
        try:
            table.insert_all(records)
        except Exception as e:
            logger.error(f"Error inserting records: {e}")
            if backup_path:
                logger.info(f"You can restore from backup: {backup_path}")
            raise

    # Log a summary
    try:
        row_count = len(list(table.rows))
        logger.info(f"Database update complete. Table '{table_name}' now has {row_count} records.")
    except Exception as e:
        logger.error(f"Error counting rows: {e}")

def create_attempts_table(db_path: str) -> None:
    """Create the attempts table if it doesn't exist."""
    db = database(db_path)
    table_name = "attempts"

    if table_name not in db.t:
        logger.info(f"Creating '{table_name}' table")
        db.create(Attempt, name=table_name)
    else:
        logger.info(f"Table '{table_name}' already exists")

def show_database_info(db_path: str) -> None:
    """Display information about the database."""
    if not os.path.exists(db_path):
        logger.info(f"Database file does not exist: {db_path}")
        return

    db = database(db_path)

    # Get table list
    table_names = list(db.t.keys())

    logger.info(f"Database at '{db_path}' contains {len(table_names)} tables:")
    for table_name in table_names:
        try:
            row_count = len(list(db.t[table_name].rows))
            logger.info(f"  - {table_name}: {row_count} rows")
        except Exception as e:
            logger.error(f"Error counting rows in {table_name}: {e}")

    # Show schema
    schema_query = "SELECT name, sql FROM sqlite_master WHERE type='table';"
    logger.info("\nDatabase Schema:")
    for row in db.query(schema_query):
        logger.info(f"\n{row}")

def main():
    """Main function to handle database creation and updates."""
    parser = argparse.ArgumentParser(description="Lithuanian Database Manager")
    parser.add_argument('--db', default="lithuanian_data.db", help="Database file path")
    parser.add_argument('--data-dir', default="data", help="Directory containing CSV files")
    parser.add_argument('--prefix', default="numbers_", help="Prefix for CSV filenames")
    parser.add_argument('--info', action='store_true', help="Show database information only")
    parser.add_argument('--static-schema', action='store_true',
                        help="Use static schema (don't adapt to new columns)")
    parser.add_argument('--debug', action='store_true', help="Enable debug logging")

    args = parser.parse_args()

    # Set debug level if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)

    # Show info if requested
    if args.info:
        show_database_info(args.db)
        return 0

    try:
        # Get latest data
        df, filename = read_latest_dated_csv(args.data_dir, args.prefix)

        logger.info(f"Loaded {len(df)} rows from {filename}")
        logger.debug(f"DataFrame columns: {list(df.columns)}")
        logger.debug(f"First few rows:\n{df.head()}")

        # Update the numbers table
        update_database(
            db_path=args.db,
            df=df,
            table_name="numbers",
            base_class=Numbers,
            pk_field="number",
            dynamic_schema=not args.static_schema
        )

        # Ensure the attempts table exists
        create_attempts_table(args.db)

        # Show database info
        show_database_info(args.db)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
