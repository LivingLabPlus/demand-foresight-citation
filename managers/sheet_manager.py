import requests
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class SheetManager:
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
            # Construct API URL and payload
            api_url = f"{st.secrets.BACKEND_URL}/read-sheet"
            payload = {
                "sheetname": worksheet_name,
                "spreadsheet_id": st.secrets.connection.spreadsheet_id,
                "spreadsheet_credentials": dict(st.secrets.connection.credentials),
            }

            # Send POST request
            response = requests.post(api_url, json=payload)

            # Check if response status is OK
            if response.status_code == 200:
                try:
                    # Attempt to parse JSON response
                    data = response.json()

                    # Validate structure of JSON response
                    if "data" in data and "columns" in data:
                        df = pd.DataFrame(
                            data["data"], columns=data["columns"])
                        return df
                    else:
                        print("Error: Missing 'data' or 'columns' in response.")
                except ValueError as ve:
                    # Handle JSON decoding error
                    print("Error decoding JSON response:", ve)
            else:
                # Handle non-200 HTTP status codes
                print(
                    f"Error: Received status code {response.status_code}. Response text: {response.text}")

        except requests.exceptions.RequestException as req_err:
            # Handle request-related errors (e.g., connection issues)
            print("Request error:", req_err)

        except KeyError as key_err:
            # Handle missing or malformed secrets/configuration
            print("Configuration error:", key_err)

        except Exception as e:
            # Catch-all for any other unexpected exceptions
            print("An unexpected error occurred:", e)

        # Return None if any error occurs
        return None

    @staticmethod
    def append_rows(worksheet_name, rows_data):
        # Define the range to append data to
        range_name = f"{worksheet_name}"
        service = SheetManager.get_service()

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
            service = SheetManager.get_service()

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
    def update_summary(worksheet_name, document_id, summary):
        try:
            # Initialize the Sheets API service
            service = SheetManager.get_service()

            df = SheetManager.read(worksheet_name)

            # Find the row index where document_id matches
            row_index = df[df['document_id'] == str(document_id)].index
            if row_index.empty:
                print("Document ID not found in worksheet.")
                return

            # Update the specific cell range for summary
            cell_range = f"{worksheet_name}!D{row_index.item()+2}"

            result = (
                service.spreadsheets().values().update(
                    spreadsheetId=st.secrets["connection"]["spreadsheet_id"],
                    range=cell_range,
                    valueInputOption="RAW",
                    body={"values": [[summary]]},
                ).execute()
            )
            print(f"{result.get('updatedCells')} cells updated.")
            return result
        except HttpError as error:
            print(f"An error occurred: {error}")
            return error
        except Exception as error:
            print(f"An error occurred: {error}")
            return error

    @staticmethod
    def write_rows(worksheet_name, dataframe):
        service = SheetManager.get_service()

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
    def delete_documents(document_ids):
        """Update Google Sheets by removing deleted document entries."""
        vectors = SheetManager.read("vectors")
        vector_row_indices = vectors.index[vectors["document_id"].isin(
            document_ids)].tolist()
        SheetManager.delete_rows("vectors", vector_row_indices)

        documents = SheetManager.read("documents")
        document_row_indices = documents.index[documents["document_id"].isin(
            document_ids)].tolist()
        SheetManager.delete_rows("documents", document_row_indices)

        user_documents = SheetManager.read("userDocuments")
        user_row_indices = user_documents.index[user_documents["document_id"].isin(
            document_ids)].tolist()
        SheetManager.delete_rows("userDocuments", user_row_indices)

    @staticmethod
    def upload_document(
        new_document_row,
        new_user_document_row,
        new_vectors
    ):
        """Append new rows to the appropriate Google Sheets."""
        SheetManager.append_rows(
            "documents", [list(new_document_row[0].values())])
        SheetManager.append_rows(
            "userDocuments", [list(new_user_document_row[0].values())])
        SheetManager.append_rows("vectors", new_vectors)
