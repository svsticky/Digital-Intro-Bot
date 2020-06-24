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
        
        if turn_context.activity.text == "UpdateCard":
            await self.update_card(turn_context)
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

    async def available_committees(self, turn_context: TurnContext):
        channel_id = turn_context.activity.channel_data['teamsChannelId']
        session = db.Session()
        if not db.getFirst(session, db.MentorGroup, 'channel_id', channel_id):
            await turn_context.send_activity("You can only perform this command from a Mentorgroep channel")
            session.close()
            return

        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        mentor_db_user = db.getUserOnType(session, 'mentor_user', helper.get_user_id(user))
        if not mentor_db_user:
            await turn_context.send_activity("Only a mentor can perform this action")
            session.close()
            return

        committees = db.getAll(session, db.Committee, 'occupied', False)
        print(committees)

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
                ] + [CardAction(
                        type=ActionTypes.message_back,
                        title="\u27F3",
                        text=f"UpdateCard"
                    )]
                )
            )
        session.close()
        choosing_activity = MessageFactory.attachment(card)
        await helper.create_channel_conversation(turn_context, channel_id, choosing_activity)
    
    async def update_card(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)

        session = db.Session()
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
                ] + [CardAction(
                        type=ActionTypes.message_back,
                        title="\u27F3",
                        text=f"UpdateCard"
                    )]
                )
            )
        session.close()
        updated_card = MessageFactory.attachment(card)
        updated_card.id = turn_context.activity.reply_to_id
        await turn_context.update_activity(updated_card)

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
