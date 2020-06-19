from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from config import DefaultConfig


class GoogleSheet:
    def __init__(self):
        self.config = DefaultConfig()
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        self.service = build('sheets', 'v4', credentials=creds)

    def get_members(self):
        sheet = self.service.spreadsheets()
        result = sheet.values().get(spreadsheetId=self.config.ALFAS_INFOSHEET_ID,
                                    range=self.config.ALFAS_MEMBERS_RANGE).execute()
        values = result.get('values', [])
        return values
    
    def get_timeslots(self):
        sheet = self.service.spreadsheets()
        result = sheet.values().get(spreadsheetId=self.config.ALFAS_INFOSHEET_ID,
                                    range=self.config.ALFAS_TIMESLOTS_RANGE).execute()
        values = result.get('values', [])
        return values

    def get_questions(self):
        sheet = self.service.spreadsheets()
        result = sheet.values().get(spreadsheetId=self.config.ALFAS_INFOSHEET_ID,
                                    range=self.config.CRAZY88_QUESTION_RANGE).execute()
        values = result.get('values', [])
        return values