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

    async def on_message_activity(self, turn_context: TurnContext):
        TurnContext.remove_recipient_mention(turn_context.activity)
        turn_context.activity.text = turn_context.activity.text.strip()

        #accept the group
        if turn_context.activity.text.startswith("Accept"):
            await self.accept(turn_context)
            return

        # Return all locations that are available at this moment
        if turn_context.activity.text == "AvailableLocations":
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
            return

        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        print(user)
        mentor_db_user = db.getUserOnType(session, 'mentor_user', helper.get_user_id(user))
        if not mentor_db_user:
            await turn_context.send_activity("Only a mentor can perform this action")
            session.close()
            return

        locations = db.getAll(session, db.USPLocation, 'occupied', False)

        card = CardFactory.hero_card(
            HeroCard(
                title="Available Locations",
                text='Choose the location you want to meet next!',
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
                await turn_context.send_activity("Something went wrong obtaining the chosen location, please contact the bot owner")

            location = db.getFirst(session, db.USPLocation, 'name', location_name)

            # If location is not occupied
            if not location.occupied:
                # Immediately set it as occupied, then do the rest (to make it atomic)
                location.occupied = True
                db.dbMerge(session, location)
                # Get mentor group and create a visit.
                mentor_group = db.getFirst(session, db.MentorGroup, 'mg_id', db_user.mg_id)
                visit = db.USPVisit(mg_id=mentor_group.mg_id, location_id=location.location_id)
                db.dbInsert(session, visit)
                await turn_context.send_activity(f"The location '{location.name}' will be notified of your arrival!")
                location_message = MessageFactory.text(f"The mentor group '{mentor_group.name}' wants to talk to you")
                await helper.create_channel_conversation(turn_context, location.channel_id, location_message)
                accept_button = await self.create_accept_button(mentor_group)
                await helper.create_channel_conversation(turn_context, location.channel_id, accept_button)
            else:
                #TODO: Update the card to the new available committees
                await turn_context.send_activity("This committee is now occupied, please choose another committee to visit.")
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
                        text=f"Accept {mentor_group.mg_id}",
                    ),
                ],
            )
        )
        return MessageFactory.attachment(card)

    async def accept(self, turn_context: TurnContext):
        pass

    async def release_location(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        session = db.Session()
        db_user = db.getUserOnType(session, 'usp_helper_user', helper.get_user_id(user))

        if db_user:
            location = db.getFirst(session, db.USPLocation, 'location_id', db_user.usp_id)
            location.occupied = False
            db.dbMerge(session, location)
            release_message = MessageFactory.text("This location has now been freed from occupation. Expect a new request soon!")
            await helper.create_channel_conversation(turn_context, location.channel_id, release_message)
        else:
            await turn_context.send_activity("You are not allowed to perform this command.")
        session.close()