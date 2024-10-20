import streamlit as st
import pandas as pd
import time
import uuid
from streamlit_gsheets import GSheetsConnection

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class DocumentManager:
    @staticmethod
    def get_service():
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

        # Create credentials from the dictionary
        creds = service_account.Credentials.from_service_account_info(
            st.secrets['connection']['credentials'], scopes=SCOPES
        )

        # Initialize the Sheets API client
        service = build('sheets', 'v4', credentials=creds)

        return service

    @staticmethod
    def read(worksheet_name):
        try:
            service = DocumentManager.get_service()

            # Define the range to fetch data from
            range_name = f"{worksheet_name}"

            # Get the data from the Google Sheet
            result = service.spreadsheets().values().get(
                spreadsheetId=st.secrets['connection']['spreadsheet_id'],
                range=range_name
            ).execute()

            # Extract the rows and convert to a DataFrame
            rows = result.get('values', [])
            if not rows:
                return pd.DataFrame()  # Return an empty DataFrame if no data

            # Convert rows to DataFrame, assuming the first row contains headers
            df = pd.DataFrame(rows[1:], columns=rows[0])
            return df
        except Exception as e:
            print("Exception:", e)
            return None

    @staticmethod
    def append_rows(worksheet_name, rows_data):
        # Define the range to append data to
        range_name = f"{worksheet_name}"
        service = DocumentManager.get_service()

        # Append the row to the Google Sheet
        request = service.spreadsheets().values().append(
            spreadsheetId=st.secrets['connection']['spreadsheet_id'],
            range=range_name,
            # Use "USER_ENTERED" if you want Google Sheets to evaluate formulas
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows_data}
        )
        response = request.execute()
        return response

    @staticmethod
    def delete_rows(worksheet_name, row_indices):
        try:
            service = DocumentManager.get_service()

            # Retrieve the sheet ID based on the worksheet name
            spreadsheet = service.spreadsheets().get(
                spreadsheetId=st.secrets['connection']['spreadsheet_id']
            ).execute()
            sheet_id = None
            for sheet in spreadsheet['sheets']:
                if sheet['properties']['title'] == worksheet_name:
                    sheet_id = sheet['properties']['sheetId']
                    break

            if sheet_id is None:
                print(
                    f"Worksheet name '{worksheet_name}' not found in the spreadsheet.")
                return None

            # Sort row indices in descending order
            row_indices = sorted(row_indices, reverse=True)

            # Create a request to delete the specified row in the Google Sheet
            batch_update_request = {
                "requests": [
                    {
                        "deleteDimension": {
                            "range": {
                                "sheetId": sheet_id,
                                "dimension": "ROWS",
                                # Start index of the row to delete (0-based)
                                "startIndex": row_index + 1,
                                "endIndex": row_index + 2  # End index, exclusive
                            }
                        }
                    } for row_index in row_indices
                ]
            }

            # Send the batch update request to delete the row
            response = service.spreadsheets().batchUpdate(
                spreadsheetId=st.secrets["connection"]["spreadsheet_id"],
                body=batch_update_request
            ).execute()

            return response
        except HttpError as error:
            st.error(f"錯誤: {error}")
            return error

    @staticmethod
    def write_rows(worksheet_name, dataframe):
        service = DocumentManager.get_service()

        # Convert the DataFrame to a list of lists (including the header)
        data = [dataframe.columns.tolist()] + dataframe.values.tolist()

        # Define the range to write to (starting from A1)
        range_name = f"{worksheet_name}!A1"

        # Create the body for the update request
        body = {
            'values': data
        }

        # Use the Sheets API to update the values
        result = service.spreadsheets().values().update(
            spreadsheetId=st.secrets["connection"]["spreadsheet_id"],
            range=range_name,
            valueInputOption="RAW",  # Options: "RAW" or "USER_ENTERED"
            body=body
        ).execute()

    @staticmethod
    def get_documents_by_user(documents, user_documents, username):
        # return None when cannot retrieve documents from database
        if documents is None or user_documents is None:
            return None

        document_ids = user_documents[
            user_documents["username"] == username
        ]["document_id"].tolist()

        documents_for_user = documents[
            documents["document_id"].isin(document_ids)
        ]
        return documents_for_user.reset_index(drop=True)
