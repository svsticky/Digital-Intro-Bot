from botbuilder.core import CardFactory, TurnContext, MessageFactory
from botbuilder.core.teams import TeamsActivityHandler, TeamsInfo
from botbuilder.schema import CardAction, HeroCard, Mention, ConversationParameters
from botbuilder.schema._connector_client_enums import ActionTypes
import modules.database as db
import modules.helper_funtions as helper
from config import DefaultConfig
from google_api import GoogleSheet


class StickyC88Bot(TeamsActivityHandler):
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

        # Send a certain set of activities to the given group
        if turn_context.activity.text.startswith("FetchQuestions"):
            await self.fetch_questions(turn_context)
            return

    async def fetch_questions(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        session = db.Session()
        
        if db.getUserOnType(session, 'intro_user', helper.get_user_id(user)):
            await turn_context.send_activity("Fetching all Crazy 88 questions...")
            session = db.Session()
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
        else:
            await turn_context.send_activity("You are not allowed to perform this task! You need to be an Intro Member.")
        session.close()