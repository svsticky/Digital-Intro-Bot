from botbuilder.core import CardFactory, TurnContext, MessageFactory
from botbuilder.core.teams import TeamsActivityHandler, TeamsInfo
from botbuilder.schema import CardAction, HeroCard, Mention, ConversationParameters
from botbuilder.schema._connector_client_enums import ActionTypes
import modules.database as db
import modules.helper_funtions as helper
from config import DefaultConfig
    
class StickyUITHOFBot(TeamsActivityHandler):
    def __init__(self, app_id: str, app_password: str):
        self._app_id = app_id
        self._app_password = app_password
        self.CONFIG = DefaultConfig()
        self.unlocked = True

    async def on_message_activity(self, turn_context: TurnContext):
        if not self.unlocked:
            await turn_context.send_activity("The bot is locked and can thus not be used. Try again later or ask the bot admin to unlock the bot.")
            return
            
        TurnContext.remove_recipient_mention(turn_context.activity)
        turn_context.activity.text = turn_context.activity.text.strip()

        #accept the group
        if turn_context.activity.text.startswith("Accept"):
            await self.accept(turn_context)
            return

        # Return all locations that are available at this moment
        if turn_context.activity.text == "BeschikbareLocaties":
            await self.available_locations(turn_context)
            return

        # Choose a locations for a mentor group to visit.
        if turn_context.activity.text.startswith("ChooseLocation"):
            await self.choose_location(turn_context)
            return

        await turn_context.send_activity("You provided a non valid command, maybe you made a typo?")
        return

    async def available_locations(self, turn_context: TurnContext):
        channel_id = turn_context.activity.channel_data['teamsChannelId']
        session = db.Session()
        if not db.getFirst(session, db.MentorGroup, 'channel_id', channel_id):
            await turn_context.send_activity("You can only perform this command from a Mentorgroep channel")
            session.close()
            return

        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        mentor_db_user = db.getUserOnType(session, 'mentor_user', helper.get_user_id(user))
        intro_db_user = db.getUserOnType(session, 'intro_user', helper.get_user_id(user))
        if (not mentor_db_user and not intro_db_user):
            await turn_context.send_activity("Alleen een Mentor kan dit doen")
            session.close()
            return

        locations = session.query(db.USPLocation).all()

        card = CardFactory.hero_card(
            HeroCard(
                title="Beschikbare locaties",
                text='Kies de locatie waar je naartoe wilt gaan!',
                buttons=[
                    CardAction(
                        type=ActionTypes.message_back,
                        title=location.name,
                        text=f"ChooseLocation {location.name}"
                    ) for location in locations
                ],
            )
        )
        session.close()
        choosing_activity = MessageFactory.attachment(card)
        await turn_context.send_activity(choosing_activity)

    async def choose_location(self, turn_context: TurnContext):
        #Get user from teams and database
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        session = db.Session()
        db_user = db.getUserOnType(session, 'mentor_user', helper.get_user_id(user))
    
        #If exists in database...
        if db_user:
            # Check if command is correct
            try:
                location_name = turn_context.activity.text.split()[1]
            except IndexError:
                await turn_context.send_activity("Iets ging fout met het krijgen van de locatie. Neem a.u.b contact op met de intro-commissie")

            mentor_group = db.getFirst(session, db.MentorGroup, 'mg_id', db_user.mg_id)
            if mentor_group.occupied:
                await turn_context.send_activity("Je staat al in een queue!")
                session.close()
                return

            location = db.getFirst(session, db.USPLocation, 'name', location_name)

            # If location is not occupied
            if not location.occupied:
                # Immediately set it as occupied, then do the rest (to make it atomic)
                location.occupied = True
                mentor_group.occupied = True
                db.dbMerge(session, location)
                db.dbMerge(session, mentor_group)
                # Get mentor group and create a visit.
                visit = db.USPVisit(mg_id=mentor_group.mg_id, location_id=location.location_id)
                db.dbInsert(session, visit)
                await turn_context.send_activity(f"Je staat in de wachtlijst van: '{location.name}'")
                accept_button = await self.create_accept_button(mentor_group)
                await helper.create_channel_conversation(turn_context, location.channel_id, accept_button)
            else:
                mentor_group.occupation = True
                db.dbMerge(session, mentor_group)
                visit = db.USPVisit(mg_id=mentor_group.mg_id, location_id=location.location_id)
                db.dbInsert(session, visit)
                await turn_context.send_activity(f"Je staat in de wachtlijst van: '{location.name}'")
        else:
            await turn_context.send_activity(f"You are not a Mentor and thus not allowed to perform this command.")
        session.close()

    async def create_accept_button(self, mentor_group):
        card = CardFactory.hero_card(
            HeroCard(
                title='Accept Mentor Group',
                text='A new group wants to join talk to you. '\
                     'Push the accept button to notify that you are comming',
                buttons=[
                    CardAction(
                        type=ActionTypes.message_back,
                        title=f"Accept '{mentor_group.name}'",
                        text=f"Accept {mentor_group.name}",
                    ),
                ],
            )
        )
        return MessageFactory.attachment(card)

    async def accept(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        session = db.Session()
        db_user = db.getUserOnType(session, 'usp_user', helper.get_user_id(user))

        # Check if command is correct
        if db_user:
            try:
                mentor_group_name = turn_context.activity.text.split()[1]
            except IndexError:
                await turn_context.send_activity("Iets ging fout met het krijgen van de locatie. Neem a.u.b contact op met de intro-commissie")

            mentor_group = db.getFirst(session, db.MentorGroup, 'name', mentor_group_name)
            old_visit = db.getFirst(session, db.USPVisit, 'mg_id', mentor_group.mg_id)
            if(old_visit):
                accept_message = MessageFactory.text(f"De locatie komt nu naar je toe")
                await helper.create_channel_conversation(turn_context, mentor_group.channel_id, accept_message)
                await turn_context.send_activity(f"Je kan nu naar mentorgroep: {mentor_group_name} gaan")

                old_mentor_group = db.getFirst(session, db.MentorGroup, 'mg_id', old_visit.mg_id)
                location = old_visit.location_id
                old_mentor_group.occupied = False
                db.dbMerge(session, old_mentor_group)
                session.delete(old_visit)
                session.commit()
                await self.update_accept_card(turn_context, location)
            else:
                await turn_context.send_activity("Ging iets fout met het verwijderen van de laatste visit")
        else:
            await turn_context.send_activity("Aleen usp helpers kunnen dit doen")
        session.close()

    async def update_accept_card(self, turn_context: TurnContext, location):
        session = db.Session()
        
        mentor_groups = db.getAll(session, db.USPVisit, 'location_id', location)

        if mentor_groups:
            card = CardFactory.hero_card(
                HeroCard(
                    title='Accept Mentor Group',
                    text='A new group wants to join talk to you. '\
                        'Push the accept button to notify that you are comming',
                    buttons=[
                        CardAction(
                            type=ActionTypes.message_back,
                            title=f"Accept '{mentor_groups[0].name}'",
                            text=f"Accept {mentor_groups[0].name}",
                        ),
                    ],
                )
            )
            session.close()
            updated_card = MessageFactory.attachment(card)
            updated_card.id = turn_context.activity.reply_to_id
            await turn_context.update_activity(updated_card)
        else:
            current_location = db.getFirst(session, db.USPLocation, 'location_id', location)
            if(current_location):
                current_location.occupied = False
                db.dbMerge(session, current_location)
                session.close()
                updated_message = MessageFactory.text('Je hebt iedereen gehad')
                updated_message.id = turn_context.activity.reply_to_id
                await turn_context.update_activity(updated_message)
            else:
                await turn_context.send_activity("Er is iets misgegaan met het updaten van de laatste entry")