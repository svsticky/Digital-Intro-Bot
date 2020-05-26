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

        if turn_context.activity.text.startswith("AddCommittee"):
            await self.add_committee(turn_context)
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

        if turn_context.activity.text == "GetIntro":
            await self.get_intro(turn_context)
            return

        if turn_context.activity.text == "MentionMe":
            await self._mention_activity(turn_context)
            return

        if turn_context.activity.text == "UpdateCardAction":
            await self._update_card_activity(turn_context)
            return

        if turn_context.activity.text == "MessageAllMembers":
            await self._message_all_members(turn_context)
            return

        if turn_context.activity.text == "Delete":
            await self._delete_card_activity(turn_context)
            return
        
        if turn_context.activity.text == "ShowMembers":
            await self.return_members(turn_context)
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
            committee = db.Committee(name=committee_name, info="")
            db.dbMerge(committee)
            await turn_context.send_activity(f"Committee '{committee_name}' was successfully added!")
        else:
            await turn_context.send_activity("You are not allowed to perform this task! You need to be an Intro Member.")

    async def add_mentor_group(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)

        if(db.getFirst(db.IntroUser, 'user_teams_id', user.id)):
            try:
                mentor_group_name = turn_context.activity.text.split()[1]
            except IndexError:
                await turn_context.send_activity("You need to specify the name for the mentorgroup")
                return
            mentor_group = db.MentorGroup(name=mentor_group_name)
            db.dbMerge(mentor_group)
            await turn_context.send_activity(f"Mentor Group '{mentor_group_name}' was successfully added!")
        else:
            await turn_context.send_activity("You are not allowed to perform this task! You need to be an Intro Member.")

    async def register_intro(self, turn_context: TurnContext):        
        try:
            intro_password = turn_context.activity.text.split()[1]
        except IndexError:
            await turn_context.send_activity("Wrong password! You are not cool enough to be Intro...")
            return

        if intro_password == self.CONFIG.INTRO_PASSWORD:
            sender = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            new_user = db.IntroUser(user_teams_id=sender.id,
                                    user_name=sender.name)
            db.dbMerge(new_user)
            await turn_context.send_activity("You have been successfully registered as an Intro Member")
        else:
            await turn_context.send_activity("Wrong password! You are not cool enough to be Intro...")

    async def register_mentor(self, turn_context: TurnContext):
        command_info = turn_context.activity.text.split()

        try:
            mentor_password = command_info[1]
            mentor_group_name = command_info[2]
        except IndexError:
            await turn_context.send_activity("Wrong command style. It needs to look like this: RegisterMentor <password> <mentor_group_name>.")
        
        if mentor_password == self.CONFIG.MENTOR_PASSWORD:
            sender = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            mentor_group = db.getFirst(db.MentorGroup, 'name', mentor_group_name)

            if mentor_group:
                new_user = db.MentorUser(user_teams_id=sender.id,
                                        user_name=sender.name,
                                        mg_id=mentor_group.mg_id)
                db.dbMerge(new_user)
                await turn_context.send_activity(f"You have been successfully registered as a Mentor of group '{mentor_group_name}''")
            else:
                await turn_context.send_activity('This committee does not exist yet. Please contact an Intro member if you think this is not right.')
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

            if committee:
                new_user = db.CommitteeUser(user_teams_id=sender.id,
                                            user_name=sender.name,
                                            committee_id=committee.committee_id)
                db.dbMerge(new_user)
                await turn_context.send_activity(f'You have been successfully registered as a Committee Member of {committee_name}')
            else:
                await turn_context.send_activity('This committee does not exist yet. Please contact an Intro member if you think this is not right.')
        else:
            await turn_context.send_activity('Wrong password!')
        

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
