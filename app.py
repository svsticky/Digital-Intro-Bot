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

CONFIG = DefaultConfig()
BOTS = BOTS_CHECK = ['ALFAS', 'C88', 'UITHOF']

if sys.argv[1:]:
    BOTS = sys.argv[1:]
    # Sanitation for args
    for i, _ in enumerate(BOTS):
        BOTS[i] = BOTS[i].upper()
        if BOTS[i] not in BOTS_CHECK:
            print("Wrong arguments. Arguments must only be the name of the bots you want to start. \n\n" \
                "Example: app.py ALFAS C88.\n\nWhen you use all the bots, no bots have to be specified.\n"
                f'The current bots you can choose are: {BOTS_CHECK}')
            sys.exit(1)

ALFAS_BOT = C88_BOT = UITHOF_BOT = None
for bot in BOTS:
    locals()[bot + "_SETTINGS"] = BotFrameworkAdapterSettings(eval(f'CONFIG.{bot}_APP_ID'), eval(f'CONFIG.{bot}_APP_PASSWORD'))
    locals()[bot + "_ADAPTER"] = BotFrameworkAdapter(eval(f'{bot}_SETTINGS'))
    locals()[bot + "_ADAPTER"].on_turn_error = on_error
    locals()[bot + "_APP_ID"] = locals()[bot + "_SETTINGS"].app_id if locals()[bot + "_SETTINGS"].app_id else uuid.uuid4()
    locals()[bot + "_BOT"] = eval(f'Sticky{bot}Bot(CONFIG.{bot}_APP_ID, CONFIG.{bot}_APP_PASSWORD)')

# Create Admin bot
ADMIN_SETTINGS = BotFrameworkAdapterSettings(CONFIG.ADMIN_APP_ID, CONFIG.ADMIN_APP_PASSWORD)
ADMIN_ADAPTER = BotFrameworkAdapter(ADMIN_SETTINGS)
ADMIN_ADAPTER.on_turn_error = on_error
ADMIN_APP_ID = ADMIN_SETTINGS.app_id if ADMIN_SETTINGS.app_id else uuid.uuid4()
ADMIN_BOT = StickyADMINBot(CONFIG.ADMIN_APP_ID, CONFIG.ADMIN_APP_PASSWORD,
                           ALFAS_BOT if ALFAS_BOT else None,
                           C88_BOT if C88_BOT else None,
                           UITHOF_BOT if UITHOF_BOT else None)

APP = web.Application(middlewares=[aiohttp_error_middleware])

# Listen for incoming requests on /api/messages.
async def messages(req: Request) -> Response:
    # Main bot message handler.
    if "application/json" in req.headers["Content-Type"]:
        body = await req.json()
    else:
        return Response(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    bot_id = body['recipient']['id'].split(':')[1]

    activity = Activity().deserialize(body)
    auth_header = req.headers["Authorization"] if "Authorization" in req.headers else ""

    if bot_id == CONFIG.ALFAS_APP_ID:
        response = await ALFAS_ADAPTER.process_activity(activity, auth_header, ALFAS_BOT.on_turn)
    elif bot_id == CONFIG.C88_APP_ID:
        response = await C88_ADAPTER.process_activity(activity, auth_header, C88_BOT.on_turn)
    elif bot_id == CONFIG.UITHOF_APP_ID:
        response = await UITHOF_ADAPTER.process_activity(activity, auth_header, UITHOF_BOT.on_turn)
    elif bot_id == CONFIG.ADMIN_APP_ID:
        response = await ADMIN_ADAPTER.process_activity(activity, auth_header, ADMIN_BOT.on_turn)

    if response:
        return json_response(data=response.body, status=response.status)
    return Response(status=HTTPStatus.OK)

if ALFAS_BOT:
    APP.router.add_post("/api/alfas/messages", messages)
if C88_BOT:
    APP.router.add_post("/api/c88/messages", messages)
if UITHOF_BOT:
    APP.router.add_post("/api/uithof/messages", messages)
APP.router.add_post("/api/admin/messages", messages)


if __name__ == "__main__":
    try:
        web.run_app(APP, host="localhost", port=CONFIG.PORT)
    except Exception as error:
        raise error