#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
from dotenv import load_dotenv
load_dotenv('./.env')

class DefaultConfig:
    """ Bot Configuration """

    PORT = 3978
    ALFAS_APP_ID = os.getenv("ALFASAppId")
    ALFAS_APP_PASSWORD = os.getenv("ALFASAppPassword")

    C88_APP_ID = os.getenv("C88AppId")
    C88_APP_PASSWORD = os.getenv("C88AppPassword")

    UITHOF_APP_ID = os.getenv("UithofAppId")
    UITHOF_APP_PASSWORD = os.getenv("UithofAppPassword")

    ADMIN_APP_ID = os.getenv("AdminAppId")
    ADMIN_APP_PASSWORD = os.getenv("AdminAppPassword")
    
    MENTOR_PASSWORD = os.getenv("MentorPassword")
    INTRO_PASSWORD = os.getenv("IntroPassword")
    COMMITTEE_PASSWORD = os.getenv("CommitteePassword")

    ALFAS_INFOSHEET_ID = os.getenv("ALFASInfoSheetId")
    ALFAS_MEMBERS_RANGE = os.getenv("ALFASMemberRange")
    ALFAS_TIMESLOTS_RANGE = os.getenv("ALFASTimeslotsRange")

    MAIN_ADMIN = ["Niels Kwadijk", "Joris de Jong"]

    TIME_ZONE = os.getenv("TimeZone")
