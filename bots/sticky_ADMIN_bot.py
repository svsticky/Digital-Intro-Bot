# The admin bot (for the cool kids)

import datetime
from botbuilder.core import CardFactory, TurnContext, MessageFactory
from botbuilder.core.teams import TeamsActivityHandler, TeamsInfo
from botbuilder.schema import CardAction, HeroCard, Mention, ConversationParameters
from botbuilder.schema._connector_client_enums import ActionTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import modules.database as db
import modules.helper_funtions as helper
from config import DefaultConfig
from google_api import GoogleSheet


class StickyADMINBot(TeamsActivityHandler):
    def __init__(self, app_id: str, app_password: str):
        self._app_id = app_id
        self._app_password = app_password
        self.CONFIG = DefaultConfig()
        self.scheduler = AsyncIOScheduler(timezone=self.CONFIG.TIME_ZONE)
        self.jobs = [] # Holds channel ids of mentor groups for which a job is already created.

    async def on_message_activity(self, turn_context: TurnContext):
        TurnContext.remove_recipient_mention(turn_context.activity)
        turn_context.activity.text = turn_context.activity.text.strip()

        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        user_full_name = user.given_name + " " + user.surname

        print(user.additional_properties['aadObjectId'])

        session = db.Session()
        if not db.getUserOnType(session, 'intro_user', user.id) and user_full_name not in self.CONFIG.MAIN_ADMIN:
            await turn_context.send_activity("You are no admin and thus not allowed to use this bot.")
            session.close()
            return
        session.close()

        if turn_context.activity.text == "Initialize":
            await self.initialize(turn_context)
            return

        await turn_context.send_activity("I don't know this command. Maybe you made a typo?")
    
    async def initialize(self, turn_context: TurnContext):
        session = db.Session()

        # Init channels
        await self.init_channels(turn_context, session)

        # Init members
        await self.init_members(turn_context, session)

        # Init timeslots
        await self.init_timeslots(turn_context, session)

        # Fetch questions for crazy 88
        await self.fetch_crazy88_questions(turn_context, session)

        session.close()
        #Feedback to user.
        await turn_context.send_activity("All members have been added to the bot with their respective rights")
        await turn_context.send_activity("Done initializing the bot.")
    
    async def init_channels(self, turn_context: TurnContext, session):
        await turn_context.send_activity("Starting initialization of committees and mentor groups...")
        added_groups = ""

        # Get all channels of the team
        channels = await TeamsInfo.get_team_channels(turn_context)

        # For every channel we...
        for channel in channels:
            if channel.name is None:
                continue

            #Check if it is a "Mentorgroep" channel
            if channel.name.startswith("Mentorgroep"):
                # If so, add it to the database as a MentorGroup or update it.
                group_name = channel.name.split()[1]
                existing_mentor_group = db.getFirst(session, db.MentorGroup, 'name', group_name)

                if not existing_mentor_group:
                    mentor_group = db.MentorGroup(name=group_name, channel_id=channel.id)
                    db.dbInsert(session, mentor_group)
                else:
                    existing_mentor_group.channel_id = channel.id
                    existing_mentor_group.name = group_name
                    db.dbMerge(session, existing_mentor_group)
                # Notify the channel that it is now an ALFAS channel
                init_message = MessageFactory.text(f"This channel is now the main ALFAS channel for Mentor group '{group_name}'")
                await helper.create_channel_conversation(turn_context, channel.id, init_message)
                added_groups += f'{group_name}, '

            #Check if it is a "Commissie" channel
            if channel.name.startswith("Commissie"):
                #If so, add it to the database as a Commissie or update it.
                committee_name = channel.name.split()[1]
                existing_committee = db.getFirst(session, db.Committee, 'name', committee_name)

                if not existing_committee:
                    committee = db.Committee(name=committee_name, info="", channel_id=channel.id)
                    db.dbInsert(session, committee)
                else:
                    existing_committee.channel_id = channel.id
                    existing_committee.name = committee_name
                    db.dbMerge(session, existing_committee)
                # Notify the channel that it is now an ALFAS channel
                init_message = MessageFactory.text(f"This channel is now the main ALFAS channel for Committee '{committee_name}'")
                await helper.create_channel_conversation(turn_context, channel.id, init_message)
                added_groups += f'{committee_name}, '
        # Done with the channels
        await turn_context.send_activity(f"The following groups have been added: {added_groups}")
        await turn_context.send_activity("All committees and mentor groups have been added.")

    async def init_members(self, turn_context: TurnContext, session):
        # Starting with adding members. Members are retrieved from a private google sheet.
        sheet_values = GoogleSheet().get_members()
        # Get members from teams
        members = await TeamsInfo.get_members(turn_context)

        # Double for loop which is sad... If you can come up with something better, let me know.
        # For all members in the sheet...
        for row in sheet_values[1:]:
            #get corresponding member
            matching_member = next(filter(lambda member: member.email == row[2], members), None)

            if matching_member is None:
                continue
            database_member = None
            print(matching_member)
            # Get from the database what member the member needs to become and save it as the right user.
            if row[3] == "Intro":
                user = db.getUserOnType(session, 'intro_user', helper.get_user_id(matching_member))
                if not user:
                    database_member = db.IntroUser(user_teams_id=helper.get_user_id(matching_member),
                                                   user_name=matching_member.name)
            elif row[3] == "Mentor":
                user = db.getUserOnType(session, 'mentor_user', matching_member.id)
                if not user:
                    mentor_group = db.getFirst(session, db.MentorGroup, 'name', row[4])
                    if mentor_group:
                        database_member = db.MentorUser(user_teams_id=helper.get_user_id(matching_member),
                                                        user_name=matching_member.name,
                                                        mg_id=mentor_group.mg_id)
                    else:
                        await turn_context.send_activity(f"Mentor group for '{matching_member.name} does not exist!")
            elif row[3] == "Commissie":
                user = db.getUserOnType(session, 'committee_user', helper.get_user_id(matching_member))
                if not user:
                    committee = db.getFirst(session, db.Committee, 'name', row[4])
                    if committee:
                        database_member = db.CommitteeUser(user_teams_id=helper.get_user_id(matching_member),
                                                           user_name=matching_member.name,
                                                           committee_id=committee.committee_id)
                    else:
                        await turn_context.send_activity(f"Committee for '{matching_member.name}' does not exist!")

            # Insert if a database_member is created (this is not the case if the user already exists in the database).
            if database_member is not None:
                db.dbInsert(session, database_member)

    async def init_timeslots(self, turn_context: TurnContext, session):
        # Obtain timeslots sheet
        await turn_context.send_activity("Starting obtaining timeslots for mentorgroups...")
        sheet_values = GoogleSheet().get_timeslots()

        for row in sheet_values[1:]:
            mentor_group = db.getFirst(session, db.MentorGroup, 'name', row[0])
            mentor_group.sticky_timeslot = row[1]
            mentor_group.aes_timeslot = row[2]
            db.dbMerge(session, mentor_group)
            if mentor_group.channel_id in self.jobs:
                continue
            else:
                self.create_job(turn_context, mentor_group.channel_id, row[1], "Sticky")
                self.create_job(turn_context, mentor_group.channel_id, row[2], "Aeskwadraat")
                self.jobs.append(mentor_group.channel_id)

        if not self.scheduler.running:
            self.scheduler.start()
        await turn_context.send_activity("All timeslots have been obtained.")

    async def fetch_crazy88_questions(self, turn_context: TurnContext, session):
        # Obtain questions from Google sheets 
        await turn_context.send_activity("Fetching all Crazy 88 questions...")
        sheet_values = GoogleSheet().get_questions()

        for i, q in enumerate(sheet_values):
            question = db.getFirst(session, db.Questions, 'opdr', i+1)
            q = q[0]
            if not question:
                new_question = db.Questions(opdr=i+1, question=q)
                db.dbInsert(session, new_question)
            else:
                question.question = q
                db.dbMerge(session, question)
                
        await turn_context.send_activity(f"Finished getting all Crazy 88 questions! Added / updated {len(sheet_values)} values")
    
    async def send_reminder(self, turn_context: TurnContext, minutes, channel_id, association):
        message = MessageFactory.text(f"Reminder! You are expected visit the registration booth of {association} in {minutes} minutes.")
        await helper.create_channel_conversation(turn_context, channel_id, message)

    def string_to_datetime(self, time: str):
        hour, minute = int(time[:2]), int(time[3:])
        time = datetime.datetime(2020, 1, 1, hour, minute, 0)
        return time
    
    def create_job(self, turn_context: TurnContext, channel_id, string_time: str, association):
        time = self.string_to_datetime(string_time)
        time_5 = time - datetime.timedelta(minutes=5)
        time_1 = time - datetime.timedelta(minutes=1)
        self.scheduler.add_job(self.send_reminder, args=[turn_context, 1, channel_id, association],
                                trigger='cron', hour=time_1.hour, minute=time_1.minute)
        self.scheduler.add_job(self.send_reminder, args=[turn_context, 5, channel_id, association],
                                trigger='cron', hour=time_5.hour, minute=time_5.minute)