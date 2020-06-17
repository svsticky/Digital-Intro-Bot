from botbuilder.core import CardFactory, TurnContext, MessageFactory
from botbuilder.schema import CardAction, HeroCard, Mention, ConversationParameters

async def create_channel_conversation(turn_context: TurnContext, teams_channel_id: str, message):
        params = ConversationParameters(
            is_group=True,
            channel_data={"channel": {"id": teams_channel_id}},
            activity=message
        )
        connector_client = await turn_context.adapter.create_connector_client(turn_context.activity.service_url)
        await connector_client.conversations.create_conversation(params)

async def create_personal_conversation(turn_context: TurnContext, user, message, app_id):
    conversation_reference = TurnContext.get_conversation_reference(turn_context.activity)
    params = ConversationParameters(
        is_group=False,
        bot=turn_context.activity.recipient,
        members=[user],
        tenant_id=turn_context.activity.conversation.tenant_id,
    )

    async def get_ref(tc1):
        conversation_reference_inner = TurnContext.get_conversation_reference(
            tc1.activity
        )
        return await tc1.adapter.continue_conversation(
            conversation_reference_inner, send_message, app_id
        )

    async def send_message(tc2: TurnContext):
        return await tc2.send_activity(
            message
        )  # pylint: disable=cell-var-from-loop

    await turn_context.adapter.create_conversation(conversation_reference, get_ref, params)

def get_user_id(user):
    return user.aad_object_id if user.aad_object_id else user.additional_properties['aadObjectId']
