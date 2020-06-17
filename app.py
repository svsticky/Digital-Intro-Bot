import sys
import traceback
import uuid
from datetime import datetime
from http import HTTPStatus

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    TurnContext,
    BotFrameworkAdapter,
)
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity, ActivityTypes

from bots import StickyALFASBot, StickyC88Bot, StickyUITHOFBot, StickyADMINBot
from config import DefaultConfig

CONFIG = DefaultConfig()

# Create adapter.
# See https://aka.ms/about-bot-adapter to learn more about how bots work.
ALFAS_SETTINGS = BotFrameworkAdapterSettings(CONFIG.ALFAS_APP_ID, CONFIG.ALFAS_APP_PASSWORD)
ALFAS_ADAPTER = BotFrameworkAdapter(ALFAS_SETTINGS)

C88_SETTINGS = BotFrameworkAdapterSettings(CONFIG.C88_APP_ID, CONFIG.C88_APP_PASSWORD)
C88_ADAPTER = BotFrameworkAdapter(C88_SETTINGS)

UITHOF_SETTINGS = BotFrameworkAdapterSettings(CONFIG.UITHOF_APP_ID, CONFIG.UITHOF_APP_PASSWORD)
UITHOF_ADAPTER = BotFrameworkAdapter(UITHOF_SETTINGS)

ADMIN_SETTINGS = BotFrameworkAdapterSettings(CONFIG.ADMIN_APP_ID, CONFIG.ADMIN_APP_PASSWORD)
ADMIN_ADAPTER = BotFrameworkAdapter(ADMIN_SETTINGS)


# Catch-all for errors.
async def on_error(context: TurnContext, error: Exception):
    # This check writes out errors to console log .vs. app insights.
    # NOTE: In production environment, you should consider logging this to Azure
    #       application insights.
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()

    # Send a message to the user
    await context.send_activity("The bot encountered an error or bug.")
    await context.send_activity(
        "To continue to run this bot, please fix the bot source code."
    )
    # Send a trace activity if we're talking to the Bot Framework Emulator
    if context.activity.channel_id == "emulator":
        # Create a trace activity that contains the error object
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.utcnow(),
            type=ActivityTypes.trace,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        )
        # Send a trace activity, which will be displayed in Bot Framework Emulator
        await context.send_activity(trace_activity)


ALFAS_ADAPTER.on_turn_error = on_error
C88_ADAPTER.on_turn_error = on_error
UITHOF_ADAPTER.on_turn_error = on_error
ADMIN_ADAPTER.on_turn_error = on_error

# If the channel is the Emulator, and authentication is not in use, the AppId will be null.
# We generate a random AppId for this case only. This is not required for production, since
# the AppId will have a value.
ALFAS_APP_ID = ALFAS_SETTINGS.app_id if ALFAS_SETTINGS.app_id else uuid.uuid4()
C88_APP_ID = C88_SETTINGS.app_id if C88_SETTINGS.app_id else uuid.uuid4()
UITHOF_APP_ID = UITHOF_SETTINGS.app_id if UITHOF_SETTINGS.app_id else uuid.uuid4()
ADMIN_APP_ID = ADMIN_SETTINGS.app_id if ADMIN_SETTINGS.app_id else uuid.uuid4()

# Create the Bot

ALFAS_BOT = StickyALFASBot(CONFIG.ALFAS_APP_ID, CONFIG.ALFAS_APP_PASSWORD)
C88_BOT = StickyC88Bot(CONFIG.C88_APP_ID, CONFIG.C88_APP_PASSWORD)
UITHOF_BOT = StickyUITHOFBot(CONFIG.UITHOF_APP_ID, CONFIG.UITHOF_APP_PASSWORD)
ADMIN_BOT = StickyADMINBot(CONFIG.ADMIN_APP_ID, CONFIG.ADMIN_APP_PASSWORD)


# Listen for incoming requests on /api/messages.
async def alfas_messages(req: Request) -> Response:
    # Main bot message handler.
    if "application/json" in req.headers["Content-Type"]:
        body = await req.json()
    else:
        return Response(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    activity = Activity().deserialize(body)
    auth_header = req.headers["Authorization"] if "Authorization" in req.headers else ""

    response = await ALFAS_ADAPTER.process_activity(activity, auth_header, ALFAS_BOT.on_turn)
    if response:
        return json_response(data=response.body, status=response.status)
    return Response(status=HTTPStatus.OK)

async def c88_messages(req: Request) -> Response:
    # Main bot message handler.
    if "application/json" in req.headers["Content-Type"]:
        body = await req.json()
    else:
        return Response(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    activity = Activity().deserialize(body)
    auth_header = req.headers["Authorization"] if "Authorization" in req.headers else ""

    response = await C88_ADAPTER.process_activity(activity, auth_header, C88_BOT.on_turn)
    if response:
        return json_response(data=response.body, status=response.status)
    return Response(status=HTTPStatus.OK)

async def uithof_messages(req: Request) -> Response:
    # Main bot message handler.
    if "application/json" in req.headers["Content-Type"]:
        body = await req.json()
    else:
        return Response(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    activity = Activity().deserialize(body)
    auth_header = req.headers["Authorization"] if "Authorization" in req.headers else ""

    response = await UITHOF_ADAPTER.process_activity(activity, auth_header, UITHOF_BOT.on_turn)
    if response:
        return json_response(data=response.body, status=response.status)
    return Response(status=HTTPStatus.OK)

async def admin_messages(req: Request) -> Response:
    # Main bot message handler.
    if "application/json" in req.headers["Content-Type"]:
        body = await req.json()
    else:
        return Response(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    activity = Activity().deserialize(body)
    auth_header = req.headers["Authorization"] if "Authorization" in req.headers else ""

    response = await ADMIN_ADAPTER.process_activity(activity, auth_header, ADMIN_BOT.on_turn)
    if response:
        return json_response(data=response.body, status=response.status)
    return Response(status=HTTPStatus.OK)



APP = web.Application(middlewares=[aiohttp_error_middleware])
APP.router.add_post("/api/alfas/messages", alfas_messages)
APP.router.add_post("/api/c88/messages", c88_messages)
APP.router.add_post("/api/uithof/messages", uithof_messages)
APP.router.add_post("/api/admin/messages", admin_messages)


if __name__ == "__main__":
    try:
        web.run_app(APP, host="localhost", port=CONFIG.PORT)
    except Exception as error:
        raise error