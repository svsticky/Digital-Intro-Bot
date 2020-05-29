#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
from dotenv import load_dotenv
load_dotenv('./.env')

class DefaultConfig:
    """ Bot Configuration """

    PORT = 3978
    APP_ID = os.getenv("MicrosoftAppId")
    APP_PASSWORD = os.getenv("MicrosoftAppPassword")
    
    MENTOR_PASSWORD = os.getenv("MentorPassword")
    INTRO_PASSWORD = os.getenv("IntroPassword")
    COMMITTEE_PASSWORD = os.getenv("CommitteePassword")

    SPREADSHEET_ID = os.getenv("SpreadSheetId")
    SPREADSHEET_RANGE = os.getenv("SpreadSheetRange")
