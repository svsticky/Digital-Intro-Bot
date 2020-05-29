# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from botbuilder.core import CardFactory, TurnContext, MessageFactory
from botbuilder.core.teams import TeamsActivityHandler, TeamsInfo
from botbuilder.schema import CardAction, HeroCard, Mention, ConversationParameters
from botbuilder.schema._connector_client_enums import ActionTypes
import modules.database as db
from config import DefaultConfig


class TeamsConversationBot(TeamsActivityHandler):
    def __init__(self, app_id: str, app_password: str):
        self._app_id = app_id
        self._app_password = app_password
        self.CONFIG = DefaultConfig()

    async def on_message_activity(self, turn_context: TurnContext):
        TurnContext.remove_recipient_mention(turn_context.activity)
        turn_context.activity.text = turn_context.activity.text.strip()

        if turn_context.activity.text == "InitializeBot":
            await self.initialize(turn_context)
            return

        if turn_context.activity.text.startswith("AddCommittee"):
            await self.add_committee(turn_context)
            return

        if turn_context.activity.text.startswith("RegCommittee"):
            await self.register_committee(turn_context)
            return
        
        if turn_context.activity.text.startswith("RegMentorGroup"):
            await self.register_mentor_group(turn_context)
            return
        
        if turn_context.activity.text.startswith("AddMentorGroup"):
            await self.add_mentor_group(turn_context)
            return

        if turn_context.activity.text.startswith("RegisterIntro"):
            await self.register_intro(turn_context)
            return
        
        if turn_context.activity.text.startswith("RegisterMentor"):
            await self.register_mentor(turn_context)
            return

        if turn_context.activity.text.startswith("RegisterCommitteeMember"):
            await self.register_committee_member(turn_context)
            return

        if turn_context.activity.text == "AvailableCommittees":
            await self.available_committees(turn_context)
            return

        if turn_context.activity.text.startswith("ChooseCommittee"):
            await self.choose_committee(turn_context)
            return

        if turn_context.activity.text == "GetIntro":
            await self.get_intro(turn_context)
            return

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
    
    async def initialize(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        if not db.getFirst(db.IntroUser, 'user_teams_id', user.id):
            await turn_context.send_activity("You are not allowed to perform this command!")
            return

        await turn_context.send_activity("Starting initialization of committees and mentor groups...")

        channels = await TeamsInfo.get_team_channels(turn_context)

        for channel in channels:
            if channel.name is None:
                continue

            if channel.name.startswith("Mentorgroep"):
                group_name = channel.name.split()[1]
                existing_mentor_group = db.getFirst(db.MentorGroup, 'name', group_name)

                if not existing_mentor_group:
                    mentor_group = db.MentorGroup(name=group_name, channel_id=channel.id)
                    db.dbInsert(mentor_group)
                else:
                    existing_mentor_group.channel_id = channel.id
                    existing_mentor_group.name = group_name
                    db.dbMerge(existing_mentor_group)
                init_message = MessageFactory.text(f"This channel is now the main ALFAS channel for Mentor group '{group_name}'")
                await self.create_channel_conversation(turn_context, channel.id, init_message)
                await turn_context.send_activity(f"Mentor Group '{group_name}' has been added!")
            
            if channel.name.startswith("Commissie"):
                committee_name = channel.name.split()[1]
                existing_committee = db.getFirst(db.Committee, 'name', committee_name)

                if not existing_committee:
                    committee = db.Committee(name=committee_name, info="", channel_id=channel.id)
                    db.dbInsert(committee)
                else:
                    existing_committee.channel_id = channel.id
                    existing_committee.name = committee_name
                    db.dbMerge(existing_committee)
                init_message = MessageFactory.text(f"This channel is now the main ALFAS channel for Committee '{committee_name}'")
                await self.create_channel_conversation(turn_context, channel.id, init_message)
                await turn_context.send_activity(f"Committee '{committee_name}' has been added!")
        
        await turn_context.send_activity("All committees and mentor groups have been added.")
                

    async def get_intro(self, turn_context: TurnContext):
        return_text = ''
        session = db.Session()

        for user in session.query(db.IntroUser).all():
            return_text = f'{user.user_name}   \n'
        
        await turn_context.send_activity(return_text)

    async def add_committee(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)

        if(db.getFirst(db.IntroUser, 'user_teams_id', user.id)):
            try:
                committee_name = turn_context.activity.text.split()[1]
            except IndexError:
                await turn_context.send_activity("You need to specify the name for the committee")
                return
            channels = await TeamsInfo.get_team_channels(turn_context)
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

    async def register_committee(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        if not db.getFirst(db.IntroUser, 'user_teams_id', user.id):
            await turn_context.send_activity("You do not have the rights to perform this action")

        command_info = turn_context.activity.text.split()

        try:
            committee_name = command_info[2]
            channel_id = command_info[1]
        except IndexError:
            await turn_context.send_activity("Something went wrong internally in the bot. Please contact an Intro Member")
        
        existing_committee = db.getFirst(db.Committee, 'name', committee_name)        
        if existing_committee:
            existing_committee.channel_id = channel_id
            db.dbMerge(existing_committee)
        else:
            committee = db.Committee(name=committee_name, info="", channel_id=channel_id)
            db.dbInsert(committee)

        await turn_context.send_activity(f"Committee '{committee_name}' was successfully added!")

    async def add_mentor_group(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)

        if(db.getFirst(db.IntroUser, 'user_teams_id', user.id)):
            try:
                mentor_group_name = turn_context.activity.text.split()[1]
            except IndexError:
                await turn_context.send_activity("You need to specify the name for the mentorgroup")
                return
            channels = await TeamsInfo.get_team_channels(turn_context)
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

    async def register_mentor_group(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        if not db.getFirst(db.IntroUser, 'user_teams_id', user.id):
            await turn_context.send_activity("You do not have the rights to perform this action")
            
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
            existing_user = db.getFirst(db.IntroUser, 'user_teams_id', sender.id)
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
            existing_user = db.getFirst(db.MentorUser, 'user_teams_id', sender.id)

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
            existing_user = db.getFirst(db.CommitteeUser, 'user_teams_id', sender.id)

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
