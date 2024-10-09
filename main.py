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
