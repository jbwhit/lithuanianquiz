import os
import time
from datetime import datetime

import pandas as pd
import requests

# Google Sheet IDs for different tabs
NUMBERS_SHEET_ID = "1132830952"
PRONOUNS_SHEET_ID = "0"
SPREADSHEET_ID = "1chGs5Aj4rS38_R6Fl7B5a5sfH8MWvvuYCI1peioGW64"

def download_sheet(sheet_id=NUMBERS_SHEET_ID, name='numbers', output_dir='data'):
    """
    Downloads a specific sheet from a Google Spreadsheet as a CSV file.

    Args:
        sheet_id (str): The gid parameter of the specific sheet
        name (str): Base name for the output file
        output_dir (str): Directory to save the CSV files

    Returns:
        str: Path to the saved CSV file
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")

    # Get today's date in YYYY-MM-DD format
    today = datetime.now().strftime("%Y-%m-%d")

    # Create the URL to download as CSV
    url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={sheet_id}"

    # Create the output filename
    filename = os.path.join(output_dir, f"{name}_{today}.csv")

    try:
        # Use requests to handle potential connection issues
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for HTTP errors

        # Save the raw CSV content
        with open(filename, 'wb') as f:
            f.write(response.content)

        # Read back to validate and process if needed
        df = pd.read_csv(filename)

        # If needed, you can perform data cleaning here
        # For example: df = df.dropna() or other cleaning operations

        # Save the processed dataframe
        df.to_csv(filename, index=False)

        print(f"CSV file '{filename}' has been created successfully with {len(df)} rows.")
        return filename

    except requests.exceptions.RequestException as e:
        print(f"Error downloading the sheet: {e}")
        return None
    except pd.errors.ParserError as e:
        print(f"Error parsing the CSV data: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

def download_all_sheets():
    """Download all configured sheets with retry logic"""
    sheets_to_download = [
        {"sheet_id": NUMBERS_SHEET_ID, "name": "numbers"},
        {"sheet_id": PRONOUNS_SHEET_ID, "name": "pronouns"}
    ]

    results = []

    for sheet in sheets_to_download:
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                result = download_sheet(sheet_id=sheet["sheet_id"], name=sheet["name"])
                if result:
                    results.append(result)
                    break
                else:
                    retry_count += 1
                    print(f"Retrying {sheet['name']} ({retry_count}/{max_retries})...")
                    time.sleep(2)  # Wait before retrying
            except Exception as e:
                retry_count += 1
                print(f"Error on {sheet['name']}: {e}. Retry {retry_count}/{max_retries}")
                time.sleep(2)

    print(f"Downloaded {len(results)} of {len(sheets_to_download)} sheets successfully.")
    return results

if __name__ == "__main__":
    # Download all configured sheets
    download_all_sheets()
