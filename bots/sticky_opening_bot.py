# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from botbuilder.core import CardFactory, TurnContext, MessageFactory
from botbuilder.core.teams import TeamsActivityHandler, TeamsInfo
from botbuilder.schema import CardAction, HeroCard, Mention, ConversationParameters
from botbuilder.schema._connector_client_enums import ActionTypes
import modules.database as db
from config import DefaultConfig
from google_api import GoogleSheet


class StickyOpeningBot(TeamsActivityHandler):
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
