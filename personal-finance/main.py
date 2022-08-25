from datetime import datetime
import json
import os
from typing import Any, Dict, List
from uuid import uuid4
from nordigen import NordigenClient

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError



# API used is here https://nordigen.com/en/?gclid=CjwKCAjwu5yYBhAjEiwAKXk_eLXZ6ijT_EDClBJ2Jy2JzbmrqsGlHbPe8xkjvCrSOBLqHxgWTzPlJRoCpw4QAvD_BwE
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET =  os.environ.get("CLIENT_SECRET")
# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = os.environ.get("GOOGLE_SHEETS_ID")
SHEETNAME = 'DataImport'


def google_auth():
    """Shows basic usage of the Sheets API.
    Prints values from a sample spreadsheet.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def update_values(spreadsheet_id, range_name, value_input_option,
                  values):

    creds= google_auth()
    # pylint: disable=maybe-no-member
    try:

        service = build('sheets', 'v4', credentials=creds)
        body = {
            'values': values
        }
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption=value_input_option, body=body).execute()
        print(f"{result.get('updatedCells')} cells updated.")
        return result
    except HttpError as error:
        print(f"An error occurred: {error}")
        return error


def update_ob(client, insitution):
    institution_id = client.institution.get_institution_id_by_name(
        country="GB",
        institution=insitution
    )
    
    
    init = client.initialize_session(
        # institution id
        institution_id=institution_id,
        # redirect url after successful authentication
        redirect_uri="https://localhost",
        # additional layer of unique ID defined by you
        reference_id=str(uuid4())
    )
    
    print(init)
    
    input()
    
    link = init.link # bank authorization link
    requisition_id = init.requisition_id
    
    input()
    
    print(link)
    print(requisition_id)
    
    return requisition_id

def tidy_transactions(transactions, bank_name):
    write_to_sheet = []
    for transaction in transactions:
        write_to_sheet.append([
            bank_name,
            transaction.get("valueDate") if transaction.get("valueDate") is not None else transaction.get("bookingDate"),
            transaction.get("transactionAmount").get("amount"),
            transaction.get("creditorName"),
            transaction.get("remittanceInformationUnstructured")
        ])
    return write_to_sheet

def pull_transactions(client, requisition_id):
    accounts = client.requisition.get_requisition_by_id(
        requisition_id=requisition_id
    )

    # Get account id from the list.
    account_id = accounts["accounts"][0]

    # Create account instance and provide your account id from previous step
    account = client.account_api(id=account_id)
    # Filter transactions by specific date range
    transactions = account.get_transactions(date_from=str(datetime.date(datetime.today().replace(day=1))), date_to=str(datetime.date(datetime.today())))

    return transactions


def process_transactions_for_sheets(transactions: List[Any]):    
    update_values(SPREADSHEET_ID, f"{SHEETNAME}!A1:E","USER_ENTERED", transactions)
    
    

def main():
    client = NordigenClient(
        secret_id=CLIENT_ID,
        secret_key=CLIENT_SECRET,
        timeout=120
    )
    token_data = client.generate_token()
    print(token_data)
    with open("banks.json", "r") as f:
        data = json.load(f)
    transactions_header = [["Bank Name", "Date", "Amount", "Location Name", "Location Details"]]
    transactions = []
    for bank in data:
        if bank.get("requisition_id") is None:
            bank["requisition_id"] = update_ob(client, bank.get("institution"))
        transactions += tidy_transactions(
                pull_transactions(
                    client,
                    bank["requisition_id"]
                ).get("transactions").get("booked"),
                bank.get("institution"))
    with open("banks.json", "w") as f:
        json.dump(data, f)
    transactions.sort(key=lambda row: (row[1], row[2]), reverse=False)
    transactions_header += transactions
    process_transactions_for_sheets(transactions_header)
    

if __name__ == "__main__":
    main()