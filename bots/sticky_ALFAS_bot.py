# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from botbuilder.core import CardFactory, TurnContext, MessageFactory
from botbuilder.core.teams import TeamsActivityHandler, TeamsInfo
from botbuilder.schema import CardAction, HeroCard, Mention, ConversationParameters
from botbuilder.schema._connector_client_enums import ActionTypes
import modules.database as db
import modules.helper_funtions as helper
from config import DefaultConfig


class StickyALFASBot(TeamsActivityHandler):
    def __init__(self, app_id: str, app_password: str):
        self._app_id = app_id
        self._app_password = app_password
        self.CONFIG = DefaultConfig()

    async def on_message_activity(self, turn_context: TurnContext):
        """
            All message activities towards the bot enter this function.
            var turn_context: contains most of the message information.
        """
        TurnContext.remove_recipient_mention(turn_context.activity)
        turn_context.activity.text = turn_context.activity.text.strip()

        # Based on a given command, the bot performs a function.

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

        # Return all committees that are available at this moment
        if turn_context.activity.text == "AvailableCommittees":
            await self.available_committees(turn_context)
            return

        # Choose a committee for a mentor group to visit.
        if turn_context.activity.text.startswith("ChooseCommittee"):
            await self.choose_committee(turn_context)
            return

        # When someone enrolls for a certain committee
        if turn_context.activity.text.startswith("Enroll"):
            await self.enroll(turn_context)
            return

        if turn_context.activity.text == "Release":
            await self.release_committee(turn_context)
            return
        
        if turn_context.activity.text == "Associations":
            await self.association_planning(turn_context)
            return

        # Get all intro members
        if turn_context.activity.text == "GetIntro":
            await self.get_intro(turn_context)
            return

        #TODO: what to send if it is not a command?
        await turn_context.send_activity("You provided a non valid command, maybe you made a typo?")
        return

    # Obtains all intro members
    async def get_intro(self, turn_context: TurnContext):
        return_text = ''
        session = db.Session()
        users = db.getAllUsersOnType(session, 'intro_user')
        session.close()

        for user in users:
            return_text += f'{user.user_name}   \n'

        await turn_context.send_activity(return_text)

    #Function to start adding a seperate committee. Expects argument: committee_name
    async def add_committee(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        session = db.Session()
        #Command can only be done by an intro_user
        if db.getUserOnType(session, 'intro_user', helper.get_user_id(user)):
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
        else:
            await turn_context.send_activity("You are not allowed to perform this task! You need to be an Intro Member.")
        session.close()

    # Reacts on the click of the button of the previous function. Saves the committee and links the channel.
    async def register_committee(self, turn_context: TurnContext):
        # Again, check if the user is an intro user.
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        session = db.Session()
        if not db.getUserOnType(session, 'intro_user', helper.get_user_id(user)):
            await turn_context.send_activity("You do not have the rights to perform this action")
            session.close()
            return

        # Get the extra info around the command. This includes the channel id and the committee name.
        command_info = turn_context.activity.text.split()

        # Check if the information is there.
        try:
            committee_name = command_info[2]
            channel_id = command_info[1]
        except IndexError:
            await turn_context.send_activity("Something went wrong internally in the bot. Please contact an Intro Member")
            session.close()
            return

        #Save or update the new committee
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
        # Check if the user if a intro user.
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        session = db.Session()
        if db.getUserOnType(session, 'intro_user', helper.get_user_id(user)):
            try:
                mentor_group_name = turn_context.activity.text.split()[1]
            except IndexError:
                await turn_context.send_activity("You need to specify the name for the mentorgroup")
                session.close()
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
        else:
            await turn_context.send_activity("You are not allowed to perform this task! You need to be an Intro Member.")
        session.close()

    # This function handles the choice of a channel for a mentor group.
    async def register_mentor_group(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        session = db.Session()
        if not db.getUserOnType(session, 'intro_user', helper.get_user_id(user)):
            await turn_context.send_activity("You do not have the rights to perform this action")
            session.close()
            return

        command_info = turn_context.activity.text.split()

        try:
            mentor_group_name = command_info[2]
            channel_id = command_info[1]
        except IndexError:
            await turn_context.send_activity("Something went wrong internally in the bot. Please contact an Intro Member")

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

    async def available_committees(self, turn_context: TurnContext):
        channel_id = turn_context.activity.channel_data['teamsChannelId']
        session = db.Session()
        if not db.getFirst(session, db.MentorGroup, 'channel_id', channel_id):
            await turn_context.send_activity("You can only perform this command from a Mentorgroep channel")
            session.close()
            return

        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        print(user)
        mentor_db_user = db.getUserOnType(session, 'mentor_user', helper.get_user_id(user))
        if not mentor_db_user:
            await turn_context.send_activity("Only a mentor can perform this action")
            session.close()
            return

        committees = db.getAll(session, db.Committee, 'occupied', False)

        card = CardFactory.hero_card(
            HeroCard(
                title="Available Committees",
                text='Choose the committee that you want to meet next!',
                buttons=[
                    CardAction(
                        type=ActionTypes.message_back,
                        title=committee.name,
                        text=f"ChooseCommittee {committee.name}"
                    ) for committee in committees
                ],
            )
        )
        session.close()
        choosing_activity = MessageFactory.attachment(card)
        await turn_context.send_activity(choosing_activity)

    async def choose_committee(self, turn_context: TurnContext):
        #Get user from teams and database
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        session = db.Session()
        db_user = db.getUserOnType(session, 'mentor_user', helper.get_user_id(user))

        #If exists in database...
        if db_user:
            # Check if command is correct
            try:
                committee_name = turn_context.activity.text.split()[1]
            except IndexError:
                await turn_context.send_activity("Something went wrong obtaining the chosen committee, please contact the bot owner")

            committee = db.getFirst(session, db.Committee, 'name', committee_name)

            # If committee is not occupied
            if not committee.occupied:
                # Immediately set it as occupied, then do the rest (to make it atomic)
                committee.occupied = True
                db.dbMerge(session, committee)
                # Get mentor group and create a visit.
                mentor_group = db.getFirst(session, db.MentorGroup, 'mg_id', db_user.mg_id)
                visit = db.Visit(mg_id=mentor_group.mg_id, committee_id=committee.committee_id)
                db.dbInsert(session, visit)
                await turn_context.send_activity(f"The members of committee '{committee.name}' will be joining your channel soon!")
                committee_message = MessageFactory.text(f"You are asked to join the channel of mentor group '{mentor_group.name}'")
                await helper.create_channel_conversation(turn_context, committee.channel_id, committee_message)
                enroll_button = await self.create_enrollment_button(committee)
                await turn_context.send_activity(enroll_button)
            else:
                await turn_context.send_activity("This committee is now occupied, please choose another committee to visit.")
        else:
            await turn_context.send_activity(f"You are not a Mentor and thus not allowed to perform this command.")
        session.close()

    async def enroll(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)

        try:
            committee_id = turn_context.activity.text.split()[1]
        except IndexError:
            await turn_context.send_activity("Something went wrong when clicking the button, please contact an intro member")
            return

        session = db.Session()
        ex_enrollment = db.getEnrollment(session, committee_id, user.email)
        committee = db.getFirst(session, db.Committee, 'committee_id', committee_id)
        print(ex_enrollment)

        if not ex_enrollment:
            enrollment = db.Enrollment(committee_id=committee_id, first_name=user.given_name,
                                       last_name=user.surname, email_address=user.email)
            db.dbInsert(session, enrollment)
            await helper.create_personal_conversation(turn_context, user, f"You have been added to the interest list of '{committee.name}'", self._app_id)
        session.close()

    async def release_committee(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        session = db.Session()
        db_user = db.getUserOnType(session, 'committee_user', helper.get_user_id(user))

        if db_user:
            committee = db.getFirst(session, db.Committee, 'committee_id', db_user.committee_id)
            committee.occupied = False
            db.dbMerge(session, committee)
            release_message = MessageFactory.text("This committee has now been freed from occupation. Expect a new request soon!")
            await helper.create_channel_conversation(turn_context, committee.channel_id, release_message)
        else:
            await turn_context.send_activity("You are not allowed to perform this command.")
        session.close()

    async def association_planning(self, turn_context: TurnContext):
        channel_id = turn_context.activity.channel_data['teamsChannelId']
        session = db.Session()
        mentor_group = db.getFirst(session, db.MentorGroup, 'channel_id', channel_id)
        if not mentor_group:
            await turn_context.send_activity("You can only perform this command from a Mentorgroep channel")
            session.close()
            return

        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        mentor_db_user = db.getUserOnType(session, 'mentor_user', helper.get_user_id(user))
        if not mentor_db_user:
            await turn_context.send_activity("Only a mentor can perform this action")
            session.close()
            return

        aes_time, sticky_time = db.getAssociationPlanning(session, mentor_group.mg_id)

        await turn_context.send_activity("You are expected to arrive at the registration booths at the following times:\n\n"\
                                         f"Sticky: {sticky_time} hours\n\n"\
                                         f"Aes-kwadraat: {aes_time} hours")      

    #Example functions!
    async def return_members(self, turn_context: TurnContext):
        members = await TeamsInfo.get_team_members(turn_context)
        return_text = ''
        for member in members:
            return_text += f'{member.id} {member.name}   \n'
        await turn_context.send_activity(return_text)

    async def _delete_card_activity(self, turn_context: TurnContext):
        await turn_context.delete_activity(turn_context.activity.reply_to_id)

    async def create_enrollment_button(self, committee):
        card = CardFactory.hero_card(
            HeroCard(
                title='Enrollment',
                text='A new committee will enlighten you with their activities. '\
                     'If you are interested in the committee, push the enrollment button',
                buttons=[
                    CardAction(
                        type=ActionTypes.message_back,
                        title=f"Enroll for '{committee.name}'",
                        text=f"Enroll {committee.committee_id}",
                    ),
                ],
            )
        )
        return MessageFactory.attachment(card)
