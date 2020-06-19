# svsticky-intro-bot

This repository contains all the Teams bots that are used during the digital svsticky introduction period. It is fully written in python using the BotFramework of Microsoft.

## Server Installation
- Run `pip install -r requirements.txt` to install all dependencies
- Copy `sample.env` to `.env` with `cp sample.env .env`
- Fill in all details in the environment file. To be able to fill in all the details, you need to register the bots you need with Microsoft (see below on how to do that).
- Run `python app.py`

## Register your bot with microsoft
This way of registering your bot assumes that you do not have an active Azure subscription.

- Go to the [Bot Framework Website](dev.botframework.com/bots/new).
- Login with the microsoft account that you want to connect the bot to.
- Fill in all the required information. The messaging endpoint will be the server on which the bot is running. Note that this MUST BE HTTPS (that is: secure).
- Next, click the `Create Microsoft App ID and password` button. This will lead you to the Azure portal. Here click `New registration`.
- Provide a name for the application and specify its access (recommended is to choose 'Accounts in any organizational directory). Click `Register`.
- You will land on a page that shows the App-ID of your bot. This you will need so save it somewhere.
- The bot needs a password. For this, go the `Certificates & secrets` and create a new secret. Copy it for later use.
- Next, return to the initial bot registering page, scroll down and click `Register`.
- You will now land on the Channels page. To use the registered bot in Teams, we need to add it as a channel.
- Once this is done, your bot is registered and ready to go on Microsoft's side.

## Tunneling
As noted earlier, the bot framework of microsoft only accepts https endpoints for safety. This can be a bummer if you do not have any certificates at the ready during testing or just when running it locally. This, we can fix.
- Install ngrok: `sudo snap install ngrok`
- Once installed, run: `ngrok http -host-header=rewrite 3978`
- This will open a window inside your terminal that shows a https link. This link tunnels towards where your bot will be running on your computer.
- Copy this link and go to your bot's settings on [this website](dev.botframework.com/bots).
- Paste the link in your endpoint and add the specific endpoint (something like `api/alfas/messages`).
- Now, when you open a new terminal and run your bot, It should listen to commands from teams.

## Teams Installation.
To install the bot as an app in Teams, we need the manifest files in `./appmanifest`.
- Zip the needed manifest file (.json) together with the two png files in this directory.
- In the zip-file, rename the manifest file to `manifest.json`.
- In teams, click on the three dots on the menu on the left.
- Click `More apps`.
- Click `Upload a custom app`.
- Navigate to the zip-file you just created.
- Choose how you want to add the app (bot) to teams and click `Add`.
- You are all done!