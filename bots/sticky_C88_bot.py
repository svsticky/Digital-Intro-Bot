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
        if turn_context.activity.text.startswith("SendQuestions"):
            await self.send_questions(turn_context)
            return

        if turn_context.activity.text.startswith("Answer"):
            pass

        if turn_context.activity.text.startswith("GetQuestions"):
            pass

    async def send_questions(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        session = db.Session()
        text = turn_context.activity.text.split()

        if db.getUserOnType(session, 'intro_user', helper.get_user_id(user)):
            try:
                group = text[1]
                question_set = text[2]
            except IndexError:
                await turn_context.send_activity("You need to specify the name for the group and the question set")
                return

            channels = await TeamsInfo.get_team_channels(turn_context)
            if (group in channels):
                # Sample question set to test with
                questions = [
                    [   
                        "1. What is love?",
                        "2. Baby don't hurt me",
                        "3. Don't hurt me",
                        "4. No more"
                    ],
                    [
                        "5. Is this the real life?",
                        "6. Or is this just fantasy?",
                        "7. Caught in a landslide",
                        "8. No escape from reality"
                    ]
                ]

                # TODO: Save progress of questions in database

                response_text = f'Congratulations {group}! You now have unlocked question set {question_set}\n'
                for question in questions[question_set]:
                    response_text += f'{question}\n'
                await turn_context.send_activity(response_text)
            else:
                await turn_context.send_activity("This group does not exist")
                return
        else:
            await turn_context.send_activity("You are not allowed to perform this task! You need to be an Intro Member.")
        session.close()
