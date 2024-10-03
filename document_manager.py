import streamlit as st
import time
from streamlit_gsheets import GSheetsConnection

class DocumentManager:
    def __init__(self):
        if "conn" not in st.session_state:
            # Create a connection object.
            conn = st.connection("gsheets", type=GSheetsConnection)
            st.session_state.conn = conn
        self.conn = st.session_state.conn 

    def read(self, worksheet):
        try:
            df = self.conn.read(worksheet=worksheet)
            return df
        except:
            st.error(f"Failed to read worksheet: {worksheet}")
            return None

    def update(self, worksheet, data, retries=3, delay=5):
        """
        Update Google Sheets with retry logic in case of failures.

        Parameters:
        worksheet (str): Name of the worksheet to update.
        new_df (pandas.DataFrame): DataFrame to update in the Google Sheet.
        retries (int): Number of retry attempts (default is 3).
        delay (int): Delay between retries in seconds (default is 5 seconds).
        
        Returns:
        bool: True if successful, False if all retries failed.
        """
        attempt = 0
        while attempt < retries:
            try:
                self.conn.update(worksheet=worksheet, data=data)
                # st.success(f"Successfully updated Google Sheet on attempt {attempt + 1}.")
                return True
            except Exception as e:
                attempt += 1
                # st.warning(f"Attempt {attempt} failed with error: {e}")
                if attempt < retries:
                    # st.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)  # Wait before retrying
                else:
                    st.error(f"Failed to update Google Sheet after {retries} attempts.")
                    return False