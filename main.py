import json
import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime, timedelta
import requests
import secrets
import time
import hashlib
import crypt 
import pathlib
import dotenv

from utils.logging_utils import logger

DEBUG = True
CURRENT_DIR = pathlib.Path(__file__).parent.absolute()
DOWNLOAD_FOLDER = "attachments"
PARSED_DOWNLOAD_FOLDER = CURRENT_DIR / DOWNLOAD_FOLDER

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)


if not os.path.exists(".env"):
    logger.error("No .env file found. Exiting.")
    exit()

dotenv.load_dotenv(".env")

EXPECTED_ENV_VARS = [
    "API_WUFOO",
    "API_TRELLO",
    "TOKEN_TRELLO",
    "LIST_ID_TRELLO",
    "BASE_URL_ORGANIZATION",
    "WUFOO_FORM_HASH",
    "WUFOO_BASE_URL",
    "TRELLO_BASE_URL",
    "ENTRY_ID_FILE"
]

for var in EXPECTED_ENV_VARS:
    if var not in os.environ:
        logger.error(f"Expected environment variable {var} not found. Exiting.")
        exit()
    
API_WUFOO = os.getenv("API_WUFOO")
API_TRELLO = os.getenv("API_TRELLO")
TOKEN_TRELLO = os.getenv("TOKEN_TRELLO")
LIST_ID_TRELLO = os.getenv("LIST_ID_TRELLO")
BASE_URL_ORGANIZATION = os.getenv("BASE_URL_ORGANIZATION")
WUFOO_FORM_HASH = os.getenv("WUFOO_FORM_HASH")

WUFOO_BASE_URL = f"https://{BASE_URL_ORGANIZATION}.wufoo.com/api/v3/"

TRELLO_BASE_URL = "https://api.trello.com/1/cards"

ENTRY_ID_FILE = CURRENT_DIR / "last_card_id.txt"

random_key = secrets.token_hex(16)
username = API_WUFOO
password_wufoo = random_key

WUFOO_AUTH_TUPLE=(username, password_wufoo)


def custom_url_open(full_url: str, auth: tuple = None) -> requests.models.Response:
    try:
        if auth:
            response = requests.get(full_url, auth=auth)
        else:
            response = requests.get(full_url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print("Request Exception:", e)
        sys.exit(1)


def download_entrie_files_to_folder(entrie: dict, description: str, fields_for_attachments: list) -> bool:
    """
    Downloads the files from the entries to the folder.

    Args:
        entrie (dict): The entrie from the Wufoo form.
        description (str): The description for the Trello card.
        fields_for_attachments (list): List of tuples containing the field names and the field ids for the attachments: e.g. ``[("Field31", "Resume"), ("Field32", "Cover letter")]``

    Returns:
        bool: True if the files were downloaded succesfully, False otherwise.
    """

    date_time_entrie_creation_date = datetime.strptime(entrie['DateCreated'], '%Y-%m-%d %H:%M:%S')
    entry_date_short = f"{date_time_entrie_creation_date.year}_{date_time_entrie_creation_date.month}"
    folder_name = f"{entry_date_short} {entrie['Field14']} {entrie['Field1']} ({entrie['EntryId']})"
    folder_name = os.path.join(DOWNLOAD_FOLDER, folder_name)

    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    
    for field in fields_for_attachments:    
        try:
            entrie_for_field = entrie[field[0]]
        except KeyError:
            logger.error(f"Field {field[0]} not found in entrie {entrie['EntryId']}. Making it empty.")
            raise Exception(f"Field {field[0]} not found in entrie {entrie['EntryId']} when downloading the files.")

        try:
            file_name = entrie_for_field.split(" ")[0]
            url = entrie_for_field.split(" ")[1][1:-1]
        except:
            logger.error(f"File url or name {file_name} from form {entrie['EntryId']} could not be parsed. Skipping.")
            try:
                file_path = os.path.join(folder_name, file_name)
                if os.path.exists(file_path):
                    logger.info(f"File {file_name} already exists in folder {folder_name}. Skipping.")
                    continue

                with requests.get(url, allow_redirects=True,) as r:
                    open(file_path, 'wb').write(r.content)
                logger.info(
                    f"Succesfully downloaded file {file_name}")
            
            except Exception as e:
                logger.error(f"File {file_name} from form {entrie['EntryId']} could not be downloaded. Url: {url}. Error: {e}")
                with open(file_path, 'w') as f:
                    f.write(f"File {file_name} could not be downloaded. Url: {url}. Error: {e}")
                    f.close()
                continue

    
    # Write the description to a text file
    backup_form = os.path.join(folder_name, "trello_card_description.txt")
    with open(backup_form, 'w') as f:
        f.write(description)
        f.close()

    return True
