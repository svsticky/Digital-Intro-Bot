# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from botbuilder.core import CardFactory, TurnContext, MessageFactory
from botbuilder.core.teams import TeamsActivityHandler, TeamsInfo
from botbuilder.schema import CardAction, HeroCard, Mention, ConversationParameters
from botbuilder.schema._connector_client_enums import ActionTypes
import modules.database as db
from config import DefaultConfig
from google_api import GoogleSheet


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

        # Initialize the bot
        if turn_context.activity.text == "InitializeBot":
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

        # Get all intro members
        if turn_context.activity.text == "GetIntro":
            await self.get_intro(turn_context)
            return

        #TODO: what to send if it is not a command?
        card = HeroCard(
            title="Welcome Card",
            text="Click the buttons to update this card",
            buttons=[
                CardAction(
                    type=ActionTypes.message_back,
                    title="Update Card",
                    text="UpdateCardAction",
                    value={"count": 0},
                ),
                CardAction(
                    type=ActionTypes.message_back,
                    title="Message all memebers",
                    text="MessageAllMembers",
                ),
            ],
        )
        await turn_context.send_activity(
            MessageFactory.attachment(CardFactory.hero_card(card))
        )
        return
    
    # Function that initializes the bot
    async def initialize(self, turn_context: TurnContext):
        # Get the user that sent the command
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        user_full_name = user.given_name + " " + user.surname
        print(user_full_name)
        print(self.CONFIG.MAIN_ADMIN[1])

        # Check if he or she has intro rights, if not abort the function
        if not db.getUserOnType('intro_user', user.id) and user_full_name not in self.CONFIG.MAIN_ADMIN:
            await turn_context.send_activity("You are not allowed to perform this command!")
            return

        # Feedback to the user
        await turn_context.send_activity("Starting initialization of committees and mentor groups...")

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
                existing_mentor_group = db.getFirst(db.MentorGroup, 'name', group_name)

                if not existing_mentor_group:
                    mentor_group = db.MentorGroup(name=group_name, channel_id=channel.id)
                    db.dbInsert(mentor_group)
                else:
                    existing_mentor_group.channel_id = channel.id
                    existing_mentor_group.name = group_name
                    db.dbMerge(existing_mentor_group)
                # Notify the channel that it are now an ALFAS channel
                init_message = MessageFactory.text(f"This channel is now the main ALFAS channel for Mentor group '{group_name}'")
                await self.create_channel_conversation(turn_context, channel.id, init_message)
                await turn_context.send_activity(f"Mentor Group '{group_name}' has been added!")
            
            #Check if it is a "Commissie" channel
            if channel.name.startswith("Commissie"):
                #If so, add it to the database as a Commissie or update it.
                committee_name = channel.name.split()[1]
                existing_committee = db.getFirst(db.Committee, 'name', committee_name)

                if not existing_committee:
                    committee = db.Committee(name=committee_name, info="", channel_id=channel.id)
                    db.dbInsert(committee)
                else:
                    existing_committee.channel_id = channel.id
                    existing_committee.name = committee_name
                    db.dbMerge(existing_committee)
                # Notify the channel that it are now an ALFAS channel
                init_message = MessageFactory.text(f"This channel is now the main ALFAS channel for Committee '{committee_name}'")
                await self.create_channel_conversation(turn_context, channel.id, init_message)
                await turn_context.send_activity(f"Committee '{committee_name}' has been added!")
        # Done with the channels
        await turn_context.send_activity("All committees and mentor groups have been added.")

        # Starting with adding members. Members are retrieved from a private google sheet.
        sheet_values = GoogleSheet().get_members()
        # Get members from teams
        members = await TeamsInfo.get_members(turn_context)
        
        # Double for loop which is sad... If you can come up with something better, let me know.
        # For all members in the sheet...
        for row in sheet_values[1:]:
            matching_member = None

            # Search for a corresponding member in the team members.
            for member in members:
                if member.given_name == row[0] and member.surname == row[1]:
                    matching_member = member
                    break
            
            if matching_member is None:
                continue
            database_member = None
            # Get from the database what member the member needs to become and save it as the right user.
            if row[2] == "Intro":
                user = db.getUserOnType('intro_user', matching_member.id)
                if not user:
                    database_member = db.IntroUser(user_teams_id=matching_member.id,
                                                   user_name=matching_member.name)
            elif row[2] == "Mentor":
                user = db.getUserOnType('mentor_user', matching_member.id)
                if not user:
                    mentor_group = db.getFirst(db.MentorGroup, 'name', row[3])
                    if mentor_group:
                        database_member = db.MentorUser(user_teams_id=matching_member.id,
                                                        user_name=matching_member.name,
                                                        mg_id=mentor_group.mg_id)
                    else:
                        await turn_context.send_activity(f"Mentor group for '{matching_member.name} does not exist!")
            elif row[2] == "Commissie":
                user = db.getUserOnType('committee_user', matching_member.id)
                if not user:
                    committee = db.getFirst(db.Committee, 'name', row[3])
                    if committee:
                        database_member = db.CommitteeUser(user_teams_id=matching_member.id,
                                                           user_name=matching_member.name,
                                                           committee_id=committee.committee_id)
                    else:
                        await turn_context.send_activity(f"Committee for '{matching_member.name}' does not exist!")
            
            # Insert if a database_member is created (this is not the case if the user already exists in the database).
            if database_member is not None:
                db.dbInsert(database_member)
                await turn_context.send_activity(f"Member {matching_member.name} has been added as a(n) {row[2]} user")
            else:
                await turn_context.send_activity(f"Member {matching_member.name} already existed. Left untouched")

        #Feedback to user.
        await turn_context.send_activity("All members have been added to the bot with their respective rights")
        await turn_context.send_activity("Done initializing the bot.")   

    # Obtains all intro members
    async def get_intro(self, turn_context: TurnContext):
        return_text = ''
        session = db.Session()
        users = db.getAllUsersOnType('intro_user')
        session.close()

        for user in users:
            return_text += f'{user.user_name}   \n'
        
        await turn_context.send_activity(return_text)

    #Function to start adding a seperate committee. Expects argument: committee_name
    async def add_committee(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)

        #Command can only be done by an intro_user
        if db.getUserOnType('intro_user', user.id):
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

    # Reacts on the click of the button of the previous function. Saves the committee and links the channel.
    async def register_committee(self, turn_context: TurnContext):
        # Again, check if the user is an intro user.
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        if not db.getUserOnType('intro_user', user.id):
            await turn_context.send_activity("You do not have the rights to perform this action")
            return

        # Get the extra info around the command. This includes the channel id and the committee name.
        command_info = turn_context.activity.text.split()

        # Check if the information is there.
        try:
            committee_name = command_info[2]
            channel_id = command_info[1]
        except IndexError:
            await turn_context.send_activity("Something went wrong internally in the bot. Please contact an Intro Member")
        
        #Save or update the new committee
        existing_committee = db.getFirst(db.Committee, 'name', committee_name)        
        if existing_committee:
            existing_committee.channel_id = channel_id
            db.dbMerge(existing_committee)
        else:
            committee = db.Committee(name=committee_name, info="", channel_id=channel_id)
            db.dbInsert(committee)

        await turn_context.send_activity(f"Committee '{committee_name}' was successfully added!")

    # Function that starts adding a separate mentor group.
    async def add_mentor_group(self, turn_context: TurnContext):
        # Check if the user if a intro user.
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)

        if db.getUserOnType('intro_user', user.id):
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
        else:
            await turn_context.send_activity("You are not allowed to perform this task! You need to be an Intro Member.")

    # This function handles the choice of a channel for a mentor group.
    async def register_mentor_group(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        if not db.getUserOnType('intro_user', user.id):
            await turn_context.send_activity("You do not have the rights to perform this action")
            return
            
        command_info = turn_context.activity.text.split()

        try:
            mentor_group_name = command_info[2]
            channel_id = command_info[1]
        except IndexError:
            await turn_context.send_activity("Something went wrong internally in the bot. Please contact an Intro Member")

        existing_mentor_group = db.getFirst(db.MentorGroup, 'name', mentor_group_name)
        if existing_mentor_group:
            existing_mentor_group.channel_id = channel_id
            db.dbMerge(existing_mentor_group)
        else:
            mentor_group = db.MentorGroup(name=mentor_group_name, channel_id=channel_id)
            db.dbInsert(mentor_group)
        await turn_context.send_activity(f"Mentor Group '{mentor_group_name}' was successfully added!")

    async def register_intro(self, turn_context: TurnContext):        
        try:
            intro_password = turn_context.activity.text.split()[1]
        except IndexError:
            await turn_context.send_activity("Wrong password! You are not cool enough to be Intro...")
            return

        if intro_password == self.CONFIG.INTRO_PASSWORD:
            sender = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            existing_user = db.getUserOnType('intro_user', sender.id)
            if not existing_user:
                new_user = db.IntroUser(user_teams_id=sender.id, user_name=sender.name)
                db.dbInsert(new_user)
                await turn_context.send_activity("You have been successfully registered as an Intro Member")
            else:
                await turn_context.send_activity("You have already been registered as this type of user.")
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
            sender = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            mentor_group = db.getFirst(db.MentorGroup, 'name', mentor_group_name)
            existing_user = db.getUserOnType('mentor_user', sender.id)

            if not existing_user:
                if mentor_group:
                    new_user = db.MentorUser(user_teams_id=sender.id,
                                            user_name=sender.name,
                                            mg_id=mentor_group.mg_id)
                    db.dbInsert(new_user)
                    await turn_context.send_activity(f"You have been successfully registered as a Mentor of group '{mentor_group_name}''")
                else:
                    await turn_context.send_activity('This committee does not exist yet. Please contact an Intro member if you think this is not right.')
            else:
                existing_user.mg_id = mentor_group.mg_id
                db.dbMerge(existing_user)
                await turn_context.send_activity(f"Mentor user '{sender.name}' has been successfully updated!")
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
            sender = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            committee = db.getFirst(db.Committee, 'name', committee_name)
            existing_user = db.getUserOnType('committee_user', sender.id)

            if not existing_user:
                if committee:
                    new_user = db.CommitteeUser(user_teams_id=sender.id,
                                                user_name=sender.name,
                                                committee_id=committee.committee_id)
                    db.dbInsert(new_user)
                    await turn_context.send_activity(f'You have been successfully registered as a Committee Member of {committee_name}')
                else:
                    await turn_context.send_activity('This committee does not exist yet. Please contact an Intro member if you think this is not right.')
            else:
                existing_user.committee_id = committee.committee_id
                db.dbMerge(existing_user)
                await turn_context.send_activity(f"Committee user '{sender.name}' has been successfully updated!")
        else:
            await turn_context.send_activity('Wrong password!')
        
    async def available_committees(self, turn_context: TurnContext):
        committees = db.getAll(db.Committee, 'occupied', False)

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

        choosing_activity = MessageFactory.attachment(card)
        await turn_context.send_activity(choosing_activity)
    
    async def choose_committee(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        db_user = db.getFirst(db.MentorUser, 'user_teams_id', user.id)
        
        if db_user:
            try:
                committee_name = turn_context.activity.text.split()[1]
            except IndexError:
                await turn_context.send_activity("Something went wrong obtaining the chosen committee, please contact the bot owner")
        
            committee = db.getFirst(db.Committee, 'name', committee_name)

            if not committee.occupied:
                committee.occupied = True
                db.dbMerge(committee)
                mentor_group = db.getFirst(db.MentorGroup, 'mg_id', db_user.mg_id)
                visit = db.Visit(mg_id=mentor_group.mg_id, committee_id=committee.committee_id)
                db.dbInsert(visit)
                await turn_context.send_activity(f"The members of committee '{committee.name}' will be joining your channel soon!")
                committee_message = MessageFactory.text(f"You are asked to join the channel of mentor group '{mentor_group.name}'")
                await self.create_channel_conversation(turn_context, committee.channel_id, committee_message)
            else:
                await turn_context.send_activity("This committee is now occupied, please choose another committee to visit.")

        else:
            await turn_context.send_activity(f"You are not a Mentor and thus not allowed to perform this command.")


    async def return_members(self, turn_context: TurnContext):
        members = await TeamsInfo.get_team_members(turn_context)
        return_text = ''
        for member in members:
            return_text += f'{member.id} {member.name}   \n'
        await turn_context.send_activity(return_text)

    async def _mention_activity(self, turn_context: TurnContext):
        mention = Mention(
            mentioned=turn_context.activity.from_property,
            text=f"<at>{turn_context.activity.from_property.name}</at>",
            type="mention",
        )

        reply_activity = MessageFactory.text(f"Hello {mention.text}")
        reply_activity.entities = [Mention().deserialize(mention.serialize())]
        await turn_context.send_activity(reply_activity)

    async def _update_card_activity(self, turn_context: TurnContext):
        data = turn_context.activity.value
        data["count"] += 1

        card = CardFactory.hero_card(
            HeroCard(
                title="Welcome Card",
                text=f"Updated count - {data['count']}",
                buttons=[
                    CardAction(
                        type=ActionTypes.message_back,
                        title="Update Card",
                        value=data,
                        text="UpdateCardAction",
                    ),
                    CardAction(
                        type=ActionTypes.message_back,
                        title="Message all members",
                        text="MessageAllMembers",
                    ),
                    CardAction(
                        type=ActionTypes.message_back,
                        title="Delete card",
                        text="Delete",
                    ),
                ],
            )
        )

        updated_activity = MessageFactory.attachment(card)
        updated_activity.id = turn_context.activity.reply_to_id
        await turn_context.update_activity(updated_activity)

    async def _message_all_members(self, turn_context: TurnContext):
        
        team_members = await TeamsInfo.get_members(turn_context)

        for member in team_members:
            conversation_reference = TurnContext.get_conversation_reference(
                turn_context.activity
            )

            conversation_parameters = ConversationParameters(
                is_group=False,
                bot=turn_context.activity.recipient,
                members=[member],
                tenant_id=turn_context.activity.conversation.tenant_id,
            )

            async def get_ref(tc1):
                conversation_reference_inner = TurnContext.get_conversation_reference(
                    tc1.activity
                )
                return await tc1.adapter.continue_conversation(
                    conversation_reference_inner, send_message, self._app_id
                )

            async def send_message(tc2: TurnContext):
                return await tc2.send_activity(
                    f"Hello {member.name}. I'm a Teams conversation bot."
                )  # pylint: disable=cell-var-from-loop

            await turn_context.adapter.create_conversation(
                conversation_reference, get_ref, conversation_parameters
            )

        await turn_context.send_activity(
            MessageFactory.text("All messages have been sent")
        )

    async def _delete_card_activity(self, turn_context: TurnContext):
        await turn_context.delete_activity(turn_context.activity.reply_to_id)
    
    async def create_channel_conversation(self, turn_context: TurnContext, teams_channel_id: str, message):
        params = ConversationParameters(
            is_group=True,
            channel_data={"channel": {"id": teams_channel_id}},
            activity=message
        )
        connector_client = await turn_context.adapter.create_connector_client(turn_context.activity.service_url)
        await connector_client.conversations.create_conversation(params)
