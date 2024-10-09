import os
import sys
import traceback
from datetime import datetime, timedelta
import requests
import secrets
import time

import pathlib
import dotenv

from utils.logging_utils import logger

DEBUG = True
GDPR_CAUTION = True

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


def post_custom_formatted_card_to_trello(data: dict, trello_key: str = API_TRELLO, trello_token: str = TOKEN_TRELLO, list_id_trello: str = LIST_ID_TRELLO) -> bool:
    """
    Posts a card to the Trello list with the data from the Wufoo form.

    ### Args:
        - data (dict): The data from the Wufoo form.
        - trello_key (str): The Trello API key.
        - trello_token (str): The Trello API token.
        - list_id_trello (str): The id of the list where the card should be posted.

    ### Returns:
        - bool: True if the card was posted succesfully, False otherwise.

    """
    
    # We'll get the current fields from the form to get the field names. 
    # Wufoo doesn't store the field names if the form has been edited, 
    # so we'll just use the field ids then.
    form_data = custom_url_open(WUFOO_BASE_URL + 'forms.json', WUFOO_AUTH_TUPLE)
    link_to_fields = form_data['Forms'][0]['LinkFields']
    
    field_data = custom_url_open(link_to_fields, WUFOO_AUTH_TUPLE)
    field_data = field_data['Fields']
    
    
    fields_grouped_by_id = {}
    for field in field_data:
        fields_grouped_by_id[field['ID']] = field['Title']
    
    entrie: dict
    for entrie in data['Entries']:
        # We'll parse the data from the Wufoo form to a long string that will be the description of the Trello card.
        # This is a custom format that works for us, but you can modify it to your needs.

        date_time_now_str = datetime.now().strftime("%d.%m.%Y klo %H:%M:%S")
        
        date_time_entrie_creation_date = datetime.strptime(entrie['DateCreated'], '%Y-%m-%d %H:%M:%S')  # Convert the date string from the form to a datetime object
        date_time_entrie_creation_date_str = date_time_entrie_creation_date.strftime("%d.%m.%Y klo %H:%M:%S")  # reformat datetime object to string
        deadline_in_half_a_year = date_time_entrie_creation_date + timedelta(weeks=26)  # Use the datetime object to calculate the due date after half a year
        
        base_description = (
            f"""Arrived: {date_time_entrie_creation_date_str}\n\n"""
            f"""_NB. This submission has automatically been created in Trello on {date_time_now_str}._\n\n\n\n"""
            )
        
        
        field_conditional_description = ""
        for field in entrie.keys():
            if field == "EntryId":
                field_conditional_description += f"Form entry id: {entrie[field]}\n\n"
                continue
            if entrie[field] == '' or entrie[field] == None:
                continue
            try:
                field_conditional_description += f"**{fields_grouped_by_id[field]}**\n{entrie[field]}\n\n"
            except:
                field_conditional_description += f"**{field}**\n{entrie[field]}\n\n"
                continue
            
        name_for_the_card = f"{entrie['Field14']} ({entrie['Field1']})" # In our case, we'll use the name of the submitted product and the name of the submitter as the name of the card.
    
        description = base_description + field_conditional_description

        if DEBUG:
            logger.info(f"Debug mode on. Normally would post the following card to Trello.")
        
        if not DEBUG:
            post_card_to_trello_list(
            name = name_for_the_card,
            pos = "top",
            desc = description,
            due = deadline_in_half_a_year,
            start = date_time_entrie_creation_date,
            idList = list_id_trello,
            key = trello_key,
            token = trello_token
            )
            
        try:
            if not DEBUG:
                download_entrie_files_to_folder(entrie, description)
                logger.info(f"Downloaded files for entrie {entrie['EntryId']}")
            if DEBUG:
                logger.info(f"Debug mode on. Normally would download the files for entrie {entrie['EntryId']}")
        except:
            logger.error('Something went wrong when downloading the files from Wufoo.')
            
    return True

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

def post_card_to_trello_list(
        name: str,
        desc: str,
        due: datetime,
        start: datetime,
        idList: str = LIST_ID_TRELLO,
        key: str = API_TRELLO,
        token: str = TOKEN_TRELLO,
        pos: str = "top") -> bool:
    
    """
    Posts a card to the Trello list. Check the Trello API documentation for more information on the parameters.
    ### Args
        - name (str): The name of the card.
        - desc (str): The description of the card.
        - due (datetime): The due date of the card.
        - start (datetime): The start date of the card.
        - idList (str): The id of the list where the card should be posted.
        - key (str): The Trello API key.
        - token (str): The Trello API token.
        - pos (str): The position of the card in the list.

    ### Returns
        - bool: True if the card was posted succesfully, False / Exception otherwise.
    """
    
    try:
        query = {
            "name": name,
            "pos": pos,
            "desc": desc,
            "due": due,
            "start": start,
            "idList": idList,
            "key": key,
            "token": token
            }
        
        reponse = requests.request("POST", TRELLO_BASE_URL, params=query)
        reponse.raise_for_status() # Raise an exception for HTTP errors
        
        logger.info("Posted a card to Trello.")
        return True
    except Exception as e:
        if GDPR_CAUTION:
            logger.error(f"Something went wrong when making a POST to trello.")
        else:
            logger.error(f"Something went wrong when making a POST to trello: {e}")


def main():
    if os.path.exists(ENTRY_ID_FILE):
        with open(ENTRY_ID_FILE, 'r') as f:
            latest_entry_id = int(f.read())
            f.close()
    else:
        latest_entry_id = input(f"Couldn't find the latest entry id from {ENTRY_ID_FILE}.\nPlease enter the latest entry id form wufoo after which the forms should be fetched (excluding the entry id).\nEntry id after which to fetch: ", end="")

    try:
        fetched_data = {"Entries": []}
        logger.info("Fetching data from Wufoo.")
        
        lowest_entry_id_from_data = None
        
        additional_max_clause = ""
        while True:
            url = f"forms/{WUFOO_FORM_HASH}/entries.json?Filter1=EntryId+Is_greater_than+{latest_entry_id}{additional_max_clause}&sort=EntryId&sortDirection=DESC"
            response_data = custom_url_open(WUFOO_BASE_URL + url, WUFOO_AUTH_TUPLE)
            
            for entry in response_data['Entries']:
                fetched_data['Entries'].append(entry)
            try:
                lowest_entry_id_from_data = int(response_data['Entries'][-1]['EntryId'])
            except:
                logger.info("No more entries to fetch.")
            
            if lowest_entry_id_from_data <= latest_entry_id + 1:
                logger.debug(f"No more entries to fetch, lowest entry id from data: {lowest_entry_id_from_data}")
                break
            else:
                additional_max_clause = f"&Filter2=EntryId+Is_less_than+{lowest_entry_id_from_data}"
            
        logger.info("Fetched data from Wufoo.")

    except Exception as e:
        logger.error(f"There was a problem getting entrie data from Wufoo. Error: {e}")
        exit(1)

    try:
        fetched_data['Entries'][0]['EntryId']
    except IndexError:
        logger.warning("There were no new entries in the Wufoo form. Exiting.")
        exit()

    try:
        post_custom_formatted_card_to_trello(fetched_data, API_TRELLO, TOKEN_TRELLO, LIST_ID_TRELLO)
    except Exception as e:
        if GDPR_CAUTION:
            logger.error(f"Something went wrong when posting the card to Trello. Not printing the error message due to GDPR_CAUTION.")
        else
        logger.warning(f"Something went wrong when posting the card to Trello. {e}")
        exit()

    with open(ENTRY_ID_FILE, 'w') as f:
        if not DEBUG:
            f.write(fetched_data['Entries'][0]['EntryId']) # Write the latest entry id to the file
            f.close()
        else:
            logger.info(f"Debug mode on. Normally would write the latest entry id {fetched_data['Entries'][0]['EntryId']} to the file.")
            f.close()

if __name__ == "__main__":
    main()
