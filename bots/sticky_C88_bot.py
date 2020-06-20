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
        if turn_context.activity.text.startswith("UnlockSet"):
            await self.unlock_set(turn_context)
            return

        # Answer a Crazy 88 question / exercise
        if turn_context.activity.text.startswith("Answer"):
            return

        # Get all questions which still have to be answered
        if turn_context.activity.text.startswith("GetQuestions"):
            await self.get_questions(turn_context)
            return

    async def unlock_set(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        channel_id = turn_context.activity.channel_data['teamsChannelId']
        session = db.Session()
        text = turn_context.activity.text.split()

        if db.getUserOnType(session, 'intro_user', helper.get_user_id(user)):
            try:
                question_set = int(text[1])
            except IndexError:
                await turn_context.send_activity(f"You need to specify the question set which you want to unlock for {turn_context.cha}")
                return

            progress = db.getFirst(session, db.Crazy88Progress, 'mg_id', channel_id)
            start_of_set = 8 * (question_set - 1)

            try:
                if question_set < 1 & question_set > 8:
                    await turn_context.send_activity("This is not a valid set")
                elif not progress: 
                    # Check if this mentor group exists by checking if they have any progress
                    await turn_context.send_activity("This mentor group does not exist")
                elif getattr(progress, f"opdr{start_of_set+1}") != 0:
                    # Check if question has already been unlocked or answered
                    await turn_context.send_activity("This set has already been unlocked for this group!")
                else:                    
                    # Unlock all questions for a given set
                    for x in range(1, 9):
                        setattr(progress, f"opdr{start_of_set+x}", 1)

                    db.dbMerge(session, progress)
                    response_text = f'Congratulations! You now have unlocked question set {question_set}.<br>'
                    
                    questions = db.getQuestionsFromSet(session, channel_id, question_set - 1)
                    for question in questions:
                        response_text += f'{question}<br>'

                    await turn_context.send_activity(response_text)
            except IndexError:
                await turn_context.send_activity("This question set does not exist")
        else:
            await turn_context.send_activity("You are not allowed to perform this task! You need to be an Intro Member.")
        session.close()

    async def get_questions(self, turn_context: TurnContext):
        channel_id = turn_context.activity.channel_data['teamsChannelId']
        session = db.Session()

        question_states = db.getFirst(session, db.Crazy88Progress, 'mg_id', channel_id)
        if not question_states:
            await turn_context.send_activity("This is not a mentor group")
        else:
            questions = session.query(db.Questions).all()
            response_text = ""
            for n in range(1, 89):
                if getattr(question_states, f"opdr{n}") == 1:
                    row = questions[n-1]
                    response_text += f'{row.opdr}. {row.question}\n'

            if not response_text:
                await turn_context.send_activity("This mentor group does not have any open questions")
            else:
                await turn_context.send_activity(response_text)

        session.close()
