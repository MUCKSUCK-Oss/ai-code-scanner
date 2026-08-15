# data_processor.py — Data processing utility module
# This module provides functions to process and analyze data.

import json
from typing import List, Dict

# ── 1. Data Loading ─────────────────────────────────────────
def load_data(filepath: str) -> List[Dict]:
    """
    Loads data from a JSON file.

    Args:
        filepath: The path to the JSON file.

    Returns:
        A list of dictionaries containing the data.
    """
    # initialize the result list
    result = []
    # check if the file exists
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data

# ── 2. Data Processing ──────────────────────────────────────
def process_data(data: List[Dict]) -> List[Dict]:
    """
    Processes the input data.

    Args:
        data: The data to process.

    Returns:
        The processed data.
    """
    # loop through each item in the data
    output = []
    for item in data:
        # check if the item is valid
        if item:
            output.append(item)
    return output

# ── 3. Main Entry Point ─────────────────────────────────────
def main() -> None:
    """
    Main function to run the data processing pipeline.
    """
    # Note: make sure to update the filepath as needed
    data = load_data("data.json")
    result = process_data(data)
    print(result)
