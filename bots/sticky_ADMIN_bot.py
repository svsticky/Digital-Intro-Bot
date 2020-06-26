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

        # Manual user registration functions. To be used when users need to be added after initialization.
        # These functions are password protected and their existance should only be leaked to those that need it.
        # In the bot documentation, someone should be pointed to a bot admin if there are problems.
        
        # Register a user as an intro user
        if turn_context.activity.text.startswith("RegisterIntro"):
            await self.register_intro(turn_context)
            return

        # Register a user as a mentor
        if turn_context.activity.text.startswith("RegisterMentor"):
            await self.register_mentor(turn_context)
            return

        # Register a user as a committee member
        if turn_context.activity.text.startswith("RegisterCommitteeMember"):
            await self.register_committee_member(turn_context)
            return
        
        if turn_context.activity.text == "UserInfo":
            await self.user_info(turn_context)
            return

        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        user_full_name = user.given_name + " " + user.surname

        session = db.Session()
        if not db.getUserOnType(session, 'intro_user', user.id) and user_full_name not in self.CONFIG.MAIN_ADMIN:
            await turn_context.send_activity("You are no admin and thus not allowed to use this bot.")
            session.close()
            return
        session.close()

        # Fully initialize bot (we might want to add separate inits)
        if turn_context.activity.text == "Initialize":
            await self.initialize(turn_context)
            return
        
        # Add a committee
        if turn_context.activity.text.startswith("AddCommittee"):
            await self.add_committee(turn_context)
            return

        # Follow-up registering of a committee
        if turn_context.activity.text.startswith("RegCommittee"):
            await self.register_committee(turn_context)
            return

        # Follow-up registering of a mentor group
        if turn_context.activity.text.startswith("RegMentorGroup"):
            await self.register_mentor_group(turn_context)
            return

        # Add a mentor group
        if turn_context.activity.text.startswith("AddMentorGroup"):
            await self.add_mentor_group(turn_context)
            return

        await turn_context.send_activity("I don't know this command. Maybe you made a typo?")
    
    # Main initialize Method
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
    
    ### Initialization methods!!!!

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
                    # Create mentor group
                    mentor_group = db.MentorGroup(name=group_name, channel_id=channel.id)
                    db.dbInsert(session, mentor_group)
                    # Create crazy 88 progress for this group
                    crazy88_group = db.Crazy88Progress(mg_id=channel.id)
                    db.dbInsert(session, crazy88_group)
                else:
                    # Update Crazy88 progress
                    existing_c88_progress = db.getFirst(session, db.Crazy88Progress, 'mg_id', existing_mentor_group.channel_id)
                    existing_c88_progress.mg_id = channel.id
                    db.dbMerge(session, existing_c88_progress)
                    # Update mentor group data
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
    
    ### Methods to add users and groups separately to the bot!!!

    # Function to start adding a seperate committee. Expects argument: committee_name
    async def add_committee(self, turn_context: TurnContext):
        try:
            committee_name = turn_context.activity.text.split()[1]
        except IndexError:
            await turn_context.send_activity("You need to specify the name for the committee")
            return
        channels = await TeamsInfo.get_team_channels(turn_context)
        # A card is returned to the user that contains all channels as buttons.
        # A click on the button will send a new command to the bot.
        card = CardFactory.hero_card(
            HeroCard(
                title="Choose corresponding Committee channel",
                text="Choose the channel that the committee belongs to.",
                buttons=[
                    CardAction(
                        type=ActionTypes.message_back,
                        title=channel.name,
                        text=f"RegCommittee {channel.id} {committee_name}"
                    ) for channel in channels if channel.name is not None
                ],
            ),
        )
        await turn_context.send_activity(MessageFactory.attachment(card))

    # Reacts on the click of the button of the previous function. Saves the committee and links the channel.
    async def register_committee(self, turn_context: TurnContext):
        # Get the extra info around the command. This includes the channel id and the committee name.
        command_info = turn_context.activity.text.split()

        # Check if the information is there.
        try:
            committee_name = command_info[2]
            channel_id = command_info[1]
        except IndexError:
            await turn_context.send_activity("Something went wrong internally in the bot. Please contact an Intro Member")
            return

        #Save or update the new committee
        session = db.Session()
        existing_committee = db.getFirst(session, db.Committee, 'name', committee_name)        
        if existing_committee:
            existing_committee.channel_id = channel_id
            db.dbMerge(session, existing_committee)
        else:
            committee = db.Committee(name=committee_name, info="", channel_id=channel_id)
            db.dbInsert(session, committee)
        session.close()
        await turn_context.send_activity(f"Committee '{committee_name}' was successfully added!")

    # Function that starts adding a separate mentor group.
    async def add_mentor_group(self, turn_context: TurnContext):
        try:
            mentor_group_name = turn_context.activity.text.split()[1]
        except IndexError:
            await turn_context.send_activity("You need to specify the name for the mentorgroup")
            return
        channels = await TeamsInfo.get_team_channels(turn_context)
        # Again send a card with all channels to choose the corresponding one.
        card = CardFactory.hero_card(
            HeroCard(
                title="Choose corresponding Mentor Group channel",
                text="Choose the channel that the mentor group belongs to.",
                buttons=[
                    CardAction(
                        type=ActionTypes.message_back,
                        title=channel.name,
                        text=f'RegMentorGroup {channel.id} {mentor_group_name}'
                    ) for channel in channels if channel.name is not None
                ],
            ),
        )
        await turn_context.send_activity(MessageFactory.attachment(card))

    # This function handles the choice of a channel for a mentor group.
    async def register_mentor_group(self, turn_context: TurnContext):
        command_info = turn_context.activity.text.split()

        try:
            mentor_group_name = command_info[2]
            channel_id = command_info[1]
        except IndexError:
            await turn_context.send_activity("Something went wrong internally in the bot. Please contact an Intro Member")
            return

        session = db.Session()
        existing_mentor_group = db.getFirst(session, db.MentorGroup, 'name', mentor_group_name)
        if existing_mentor_group:
            existing_mentor_group.channel_id = channel_id
            db.dbMerge(session, existing_mentor_group)
        else:
            mentor_group = db.MentorGroup(name=mentor_group_name, channel_id=channel_id)
            db.dbInsert(session, mentor_group)
        await turn_context.send_activity(f"Mentor Group '{mentor_group_name}' was successfully added!")
        session.close()

    async def register_intro(self, turn_context: TurnContext):
        try:
            intro_password = turn_context.activity.text.split()[1]
        except IndexError:
            await turn_context.send_activity("Wrong password! You are not cool enough to be Intro...")
            return

        if intro_password == self.CONFIG.INTRO_PASSWORD:
            session = db.Session()
            sender = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            existing_user = db.getUserOnType(session, 'intro_user', sender.id)
            if not existing_user:
                new_user = db.IntroUser(user_teams_id=helper.get_user_id(sender), user_name=sender.name)
                db.dbInsert(session, new_user)
                await turn_context.send_activity("You have been successfully registered as an Intro Member")
            else:
                await turn_context.send_activity("You have already been registered as this type of user.")
            session.close()
        else:
            await turn_context.send_activity("Wrong password! You are not cool enough to be Intro...")

    async def register_mentor(self, turn_context: TurnContext):
        command_info = turn_context.activity.text.split()

        try:
            mentor_password = command_info[1]
            mentor_group_name = command_info[2]
        except IndexError:
            await turn_context.send_activity("Wrong command style. It needs to look like this: RegisterMentor <password> <mentor_group_name>.")
            return

        if mentor_password == self.CONFIG.MENTOR_PASSWORD:
            session = db.Session()
            sender = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            mentor_group = db.getFirst(session, db.MentorGroup, 'name', mentor_group_name)
            existing_user = db.getUserOnType(session, 'mentor_user', helper.get_user_id(sender))

            if not existing_user:
                if mentor_group:
                    new_user = db.MentorUser(user_teams_id=helper.get_user_id(sender),
                                            user_name=sender.name,
                                            mg_id=mentor_group.mg_id)
                    db.dbInsert(session, new_user)
                    await turn_context.send_activity(f"You have been successfully registered as a Mentor of group '{mentor_group_name}''")
                else:
                    await turn_context.send_activity('This committee does not exist yet. Please contact an Intro member if you think this is not right.')
            else:
                existing_user.mg_id = mentor_group.mg_id
                db.dbMerge(session, existing_user)
                await turn_context.send_activity(f"Mentor user '{sender.name}' has been successfully updated!")
            session.close()
        else:
            turn_context.send_activity('Wrong password!')

    async def register_committee_member(self, turn_context: TurnContext):
        command_info = turn_context.activity.text.split()

        try:
            committee_password = command_info[1]
            committee_name = command_info[2]
        except IndexError:
            await turn_context.send_activity("Wrong command style. It needs to look like this: RegisterCommitteeMember <password> <committee>.")
            return

        if committee_password == self.CONFIG.COMMITTEE_PASSWORD:
            session = db.Session()
            sender = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            committee = db.getFirst(session, db.Committee, 'name', committee_name)
            existing_user = db.getUserOnType(session, 'committee_user', helper.get_user_id(sender))

            if not existing_user:
                if committee:
                    new_user = db.CommitteeUser(user_teams_id=helper.get_user_id(sender),
                                                user_name=sender.name,
                                                committee_id=committee.committee_id)
                    db.dbInsert(session, new_user)
                    await turn_context.send_activity(f'You have been successfully registered as a Committee Member of {committee_name}')
                else:
                    await turn_context.send_activity('This committee does not exist yet. Please contact an Intro member if you think this is not right.')
            else:
                existing_user.committee_id = committee.committee_id
                db.dbMerge(session, existing_user)
                await turn_context.send_activity(f"Committee user '{sender.name}' has been successfully updated!")
            session.close()
        else:
            await turn_context.send_activity('Wrong password!')

    async def user_info(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)

        session = db.Session()
        users = db.getAll(session, db.User, 'user_teams_id', helper.get_user_id(user))

        if not users:
            await turn_context.send_activity("You are not registered as a special user to the bot")
            session.close()
            return
        
        return_string = "You are known to the bot as follows:   \n"
        for user in users:
            if user.user_type == "intro_user":
                return_string += f'- Introduction committee member   \n'
            elif user.user_type == "mentor_user":
                mentor_user = db.getUserOnType(session, 'mentor_user', user.user_teams_id)
                mentor_group = db.getFirst(session, db.MentorGroup, 'mg_id', mentor_user.mg_id)
                return_string += f'- Mentor for group {mentor_group.name}   \n'
            elif user.user_type == "committee_user":
                committee_user = db.getUserOnType(session, 'committee_user', user.user_teams_id)
                committee = db.getFirst(session, db.Committee, 'committee_id', committee_user.committee_id)
                return_string += f'- Committee member for {committee.name}   \n'
        session.close()
        await turn_context.send_activity(return_string)
    
    ### Local helper methods!!!

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