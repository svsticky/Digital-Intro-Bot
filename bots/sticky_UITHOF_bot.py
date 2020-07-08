from botbuilder.core import CardFactory, TurnContext, MessageFactory
from botbuilder.core.teams import TeamsActivityHandler, TeamsInfo
from botbuilder.schema import CardAction, HeroCard, Mention, ConversationParameters
from botbuilder.schema._connector_client_enums import ActionTypes
#import modules.database as db
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