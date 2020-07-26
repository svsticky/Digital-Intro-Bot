# The admin bot (for the cool kids)

import datetime
from botbuilder.core import CardFactory, TurnContext, MessageFactory
from botbuilder.core.teams import TeamsActivityHandler, TeamsInfo
from botbuilder.schema import CardAction, HeroCard, Mention, ConversationParameters
from botbuilder.schema.teams import TeamsChannelAccount
from botbuilder.schema._connector_client_enums import ActionTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import modules.database as db
import modules.helper_funtions as helper
from config import DefaultConfig
from google_api import GoogleSheet


class StickyADMINBot(TeamsActivityHandler):
    def __init__(self, app_id: str, app_password: str, alfas, uithof):
        self._app_id = app_id
        self._app_password = app_password
        self.CONFIG = DefaultConfig()
        self.alfas_bot = alfas # alfas bot object
        self.uithof_bot = uithof # uithof bot object
        self.just_booted = True

    async def on_teams_members_added(self, teams_members_added: [TeamsChannelAccount],
        team_info: TeamsInfo, turn_context: TurnContext
    ):
        message = "Welcome message here..."
        for member in teams_members_added:
            await helper.create_personal_conversation(turn_context, member, message, self._app_id)
        return

    async def on_message_activity(self, turn_context: TurnContext):
        TurnContext.remove_recipient_mention(turn_context.activity)
        turn_context.activity.text = turn_context.activity.text.strip()

        # Manual user registration functions. To be used when users need to be added after initialization.
        # These functions are password protected and their existance should only be leaked to those that need it.
        # In the bot documentation, someone should be pointed to a bot admin if there are problems.

        # Register a user as an intro user
        if turn_context.activity.text.startswith("IkBenIntro"):
            await self.register_intro(turn_context)
            return

        # Register a user as a mentor
        if turn_context.activity.text.startswith("IkBenMentor"):
            await self.register_mentor(turn_context)
            return

        # Register a user as a committee member
        if turn_context.activity.text.startswith("IkBenCommissielid"):
            if self.alfas_bot:
                await self.register_committee_member(turn_context)
            else:
                await turn_context.send_activity("Dit commando is niet actief omdat de bijbehorende bot niet draait.")
            return
        
        if turn_context.activity.text == "GebruikersInfo":
            await self.user_info(turn_context)
            return

        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        user_full_name = user.given_name + " " + user.surname

        session = db.Session()
        if not db.getUserOnType(session, 'intro_user', user.id) and user_full_name not in self.CONFIG.MAIN_ADMIN:
            await turn_context.send_activity("Je bent geen administrator en kan dit command dus niet uitvoeren!")
            session.close()
            return
        session.close()

        # Fully initialize bot (we might want to add separate inits)
        if turn_context.activity.text == "Initialiseren":
            await self.initialize(turn_context)
            return
        
        if turn_context.activity.text == "HerstartScheduler":
            session = db.Session()
            await self.restart_scheduler(turn_context, session)
            session.close()
            return
        
        # Add a committee        
        if turn_context.activity.text.startswith("CommissieToevoegen"):
            if self.alfas_bot:
                await self.add_committee(turn_context)
            else:
                await turn_context.send_activity("Dit commando is niet actief omdat de bijbehorende bot niet draait.")
            return

        # Follow-up registering of a committee
        if turn_context.activity.text.startswith("RegCommittee"):
            if self.alfas_bot:
                await self.register_committee(turn_context)
            else:
                await turn_context.send_activity("Dit commando is niet actief omdat de bijbehorende bot niet draait.")
            return

        # Add a mentor group
        if turn_context.activity.text.startswith("MentorgroepToevoegen"):
            await self.add_mentor_group(turn_context)
            return

        # Follow-up registering of a mentor group
        if turn_context.activity.text.startswith("RegMentorGroup"):
            await self.register_mentor_group(turn_context)
            return
        
        if turn_context.activity.text.startswith("USPlocatieToevoegen"):
            if self.uithof_bot:
                await self.add_USP_location(turn_context)
            else:
                await turn_context.send_activity("Dit commando is niet actief omdat de bijbehorende bot niet draait.")
            return

        # Follow-up registering of a committee
        if turn_context.activity.text.startswith("RegUSPLocation"):
            if self.uithof_bot:
                await self.register_USP_location(turn_context)
            else:
                await turn_context.send_activity("Dit commando is niet actief omdat de bijbehorende bot niet draait.")
            return
        
        if turn_context.activity.text.startswith("Activeer"): #followed by one of ['alfas', 'c88', 'uithof']
            await self.unlock_bot(turn_context)
            return

        if turn_context.activity.text.startswith("Deactiveer"): #followed by one of ['alfas', 'c88', 'uithof']
            await self.lock_bot(turn_context)
            return

        await turn_context.send_activity("Ik ken dit commando niet. Misschien heb je een typfout gemaakt?")
    
    # Main initialize Method
    async def initialize(self, turn_context: TurnContext):
        session = db.Session()

        # Init channels
        await self.init_channels(turn_context, session)

        # Init members
        await self.init_members(turn_context, session)

        # Init timeslots
        if self.alfas_bot: # only needs to be done when the alfas bot is launched.
            await self.init_timeslots(turn_context, session)

        session.close()
        #Feedback to user.
        await turn_context.send_activity("De bot is geïnitialiseerd!")
    
    ### Initialization methods!!!!

    async def init_channels(self, turn_context: TurnContext, session):
        await turn_context.send_activity("Gestart met het initialiseren van groepen gebasseerd op Teamskanalen...")

        # Get all channels of the team
        channels = await TeamsInfo.get_team_channels(turn_context)

        # For every channel we...
        for channel in channels:
            if channel.name is None:
                continue

            #Check if it is a "Mentorgroep" channel
            if channel.name.startswith("Mentorgroep"):
                # If so, add it to the database as a MentorGroup or update it.
                group_name = channel.name.split()[1]
                existing_mentor_group = db.getFirst(session, db.MentorGroup, 'name', group_name)

                if not existing_mentor_group:
                    # Create mentor group
                    mentor_group = db.MentorGroup(name=group_name, channel_id=channel.id)
                    db.dbInsert(session, mentor_group)
                else:
                    # Update mentor group data
                    existing_mentor_group.channel_id = channel.id
                    existing_mentor_group.name = group_name
                    db.dbMerge(session, existing_mentor_group)
                # Notify the channel that it is now an ALFAS channel
                init_message = MessageFactory.text(f"Dit kanaal is nu het botkanaal voor Mentorgroep: '{group_name}'")
                await helper.create_channel_conversation(turn_context, channel.id, init_message)

            #Check if it is a "Commissie" channel
            if self.alfas_bot: # If the alfas bot is launched
                if channel.name.startswith("Commissie"):
                    #If so, add it to the database as a Commissie or update it.
                    committee_name = channel.name.split()[1]
                    existing_committee = db.getFirst(session, db.Committee, 'name', committee_name)

                    if not existing_committee:
                        committee = db.Committee(name=committee_name, info="", channel_id=channel.id)
                        db.dbInsert(session, committee)
                    else:
                        existing_committee.channel_id = channel.id
                        existing_committee.name = committee_name
                        db.dbMerge(session, existing_committee)
                    # Notify the channel that it is now an ALFAS channel
                    init_message = MessageFactory.text(f"Dit kanaal is nu het ALFASkanaal voor Commissie: '{committee_name}'")
                    await helper.create_channel_conversation(turn_context, channel.id, init_message)

            #Check if it is a "usp location" channel
            if self.uithof_bot: # If the uithof bot is launched
                if channel.name.startswith("USP"):
                    #If so, add it to the database as a Commissie or update it.
                    location_name = channel.name.split()[1]
                    existing_location = db.getFirst(session, db.USPLocation, 'name', location_name)

                    if not existing_location:
                        location = db.USPLocation(name=location_name, info="", channel_id=channel.id)
                        db.dbInsert(session, location)
                    else:
                        existing_location.channel_id = channel.id
                        existing_location.name = location_name
                        db.dbMerge(session, existing_location)
                    # Notify the channel that it is now an USP channel
                    init_message = MessageFactory.text(f"Dit kanaal is nu het USPkanaal voor locatie: '{location_name}'")
                    await helper.create_channel_conversation(turn_context, channel.id, init_message)

        # Done with the channels
        await turn_context.send_activity("Alle groepen zijn geïnitialiseerd!")

    async def init_members(self, turn_context: TurnContext, session):
        # Starting with adding members. Members are retrieved from a private google sheet.
        await turn_context.send_activity("Gestart met het initialiseren van gebruikers via de google sheets...")
        sheet_values = GoogleSheet().get_members()
        # Get members from teams
        members = await TeamsInfo.get_members(turn_context)

        # Double for loop which is sad... If you can come up with something better, let me know.
        # For all members in the sheet...
        for row in sheet_values[1:]:
            #get corresponding member
            matching_member = next(filter(lambda member: member.email == row[2], members), None)

            if matching_member is None:
                continue
            database_member = None

            # Get from the database what member the member needs to become and save it as the right user.
            if row[3] == "Intro":
                user = db.getUserOnType(session, 'intro_user', helper.get_user_id(matching_member))
                if not user:
                    database_member = db.IntroUser(user_teams_id=helper.get_user_id(matching_member),
                                                   user_name=matching_member.name)
            elif row[3] == "Mentor":
                user = db.getUserOnType(session, 'mentor_user', helper.get_user_id(matching_member))
                if not user:
                    mentor_group = db.getFirst(session, db.MentorGroup, 'name', row[4])
                    if mentor_group:
                        database_member = db.MentorUser(user_teams_id=helper.get_user_id(matching_member),
                                                        user_name=matching_member.name,
                                                        mg_id=mentor_group.mg_id)
                    else:
                        await turn_context.send_activity(f"De mentorgroep voor '{matching_member.name} bestaat niet!")
            elif self.alfas_bot and row[3] == "Commissie": # These are only added when the alfas bot is launched.
                user = db.getUserOnType(session, 'committee_user', helper.get_user_id(matching_member))
                if not user:
                    committee = db.getFirst(session, db.Committee, 'name', row[4])
                    if committee:
                        database_member = db.CommitteeUser(user_teams_id=helper.get_user_id(matching_member),
                                                        user_name=matching_member.name,
                                                        committee_id=committee.committee_id)
                    else:
                        await turn_context.send_activity(f"De commissie voor '{matching_member.name}' bestaat niet!")
            elif self.uithof_bot and row[3] == "USP": # These are only added when the uithof bot is launched.
                user = db.getUserOnType(session, 'usp_user', helper.get_user_id(matching_member))
                if not user:
                    location = db.getFirst(session, db.USPLocation, 'name', row[4])
                    if location:
                        database_member = db.USPUser(user_teams_id=helper.get_user_id(matching_member),
                                                    user_name=matching_member.name,
                                                    location_id=location.location_id)
                    else:
                        await turn_context.send_activity(f"De locatie voor '{matching_member.name}' bestaat niet!")
            # Insert if a database_member is created (this is not the case if the user already exists in the database).
            if database_member is not None:
                db.dbInsert(session, database_member)

        await turn_context.send_activity("Alle gebruikers zijn toegevoegd met bijbehorende rechten.")

    async def init_timeslots(self, turn_context: TurnContext, session):
        # Obtain timeslots sheet
        await turn_context.send_activity("Gestart met het ophalen van verenigingstijdsloten voor de mentorgroepen...")
        sheet_values = GoogleSheet().get_timeslots()

        for row in sheet_values[1:]:
            mentor_group = db.getFirst(session, db.MentorGroup, 'name', row[0])
            for idx, association in enumerate(self.CONFIG.ASSOCIATIONS):
                try:
                    time_hours = int(row[idx+1].split(':')[0])
                    time_minutes = int(row[idx+1].split(':')[1])
                except ValueError:
                    await turn_context.send_activity("De tijdsloten in de google sheet zijn niet goed geformateerd.")
                    return
                setattr(mentor_group, f'{association}_timeslot', datetime.time(time_hours, time_minutes, 0, 0))
            db.dbMerge(session, mentor_group)
           
            for idx, association in enumerate(self.CONFIG.ASSOCIATIONS):
                result_jobs = self.create_job(turn_context, mentor_group.channel_id, row[idx+1], association)
                if association in self.alfas_bot.jobs.keys():
                    self.alfas_bot.jobs[association].extend(result_jobs)
                else:
                    self.alfas_bot.jobs.update({association: result_jobs})

        if not self.alfas_bot.scheduler.running:
            self.alfas_bot.scheduler.start()
        await turn_context.send_activity("Alle tijdsloten zijn toegevoegd!")
    
    async def restart_scheduler(self, turn_context, session):
        mentor_groups = db.getTable(session, db.MentorGroup)

        for mentor_group in mentor_groups:
            for _, association in enumerate(self.CONFIG.ASSOCIATIONS):
                time = getattr(mentor_group, f'{association}_timeslot')
                result_jobs = self.create_job(turn_context, mentor_group.channel_id, f'{time.hour}:{time.minute}', association)
                if association in self.alfas_bot.jobs.keys():
                    self.alfas_bot.jobs[association].extend(result_jobs)
                else:
                    self.alfas_bot.jobs.update({association: result_jobs})
        
        if not self.alfas_bot.scheduler.running:
            self.alfas_bot.scheduler.start()
        
        await turn_context.send_activity("Scheduler has restarted")

    # Function to start adding a seperate committee. Expects argument: committee_name
    async def add_committee(self, turn_context: TurnContext):
        try:
            committee_name = turn_context.activity.text.split()[1]
        except IndexError:
            await turn_context.send_activity("Je moet de naam van de commissie aan de bot meegeven: CommissieToevoegen <naam>")
            return
        channels = await TeamsInfo.get_team_channels(turn_context)
        # A card is returned to the user that contains all channels as buttons.
        # A click on the button will send a new command to the bot.
        card = CardFactory.hero_card(
            HeroCard(
                title="Commissiekanaal.",
                text="Kies het kanaal waar deze commissie aan gelinkt zal worden.",
                buttons=[
                    CardAction(
                        type=ActionTypes.message_back,
                        title=channel.name,
                        text=f"RegCommittee {channel.id} {committee_name}"
                    ) for channel in channels if channel.name is not None and channel.name.startswith('Commissie')
                ],
            ),
        )
        await turn_context.send_activity(MessageFactory.attachment(card))

    # Reacts on the click of the button of the previous function. Saves the committee and links the channel.
    async def register_committee(self, turn_context: TurnContext):
        # Get the extra info around the command. This includes the channel id and the committee name.
        command_info = turn_context.activity.text.split()

        # Check if the information is there.
        try:
            committee_name = command_info[2]
            channel_id = command_info[1]
        except IndexError:
            await turn_context.send_activity("Iets ging intern mis bij de bot. Contacteer iemand van de introductiecommissie.")
            return

        #Save or update the new committee
        session = db.Session()
        existing_committee = db.getFirst(session, db.Committee, 'name', committee_name)        
        if existing_committee:
            existing_committee.channel_id = channel_id
            db.dbMerge(session, existing_committee)
        else:
            committee = db.Committee(name=committee_name, info="", channel_id=channel_id)
            db.dbInsert(session, committee)
        session.close()
        await turn_context.send_activity(f"De commissie '{committee_name}' is succesvol toegevoegd!")

    # Function that starts adding a separate mentor group.
    async def add_mentor_group(self, turn_context: TurnContext):
        try:
            mentor_group_name = turn_context.activity.text.split()[1]
        except IndexError:
            await turn_context.send_activity("Je moet de naam van de commissie aan de bot meegeven: MentorgroepToevoegen <naam>")
            return
        channels = await TeamsInfo.get_team_channels(turn_context)
        # Again send a card with all channels to choose the corresponding one.
        card = CardFactory.hero_card(
            HeroCard(
                title="Mentorgroepkanaal",
                text="Kies het kanaal waar deze mentorgroep aan gelinkt moet worden.",
                buttons=[
                    CardAction(
                        type=ActionTypes.message_back,
                        title=channel.name,
                        text=f'RegMentorGroup {channel.id} {mentor_group_name}'
                    ) for channel in channels if channel.name is not None and channel.name.startswith('Mentorgroep')
                ],
            ),
        )
        await turn_context.send_activity(MessageFactory.attachment(card))

    # This function handles the choice of a channel for a mentor group.
    async def register_mentor_group(self, turn_context: TurnContext):
        command_info = turn_context.activity.text.split()

        try:
            mentor_group_name = command_info[2]
            channel_id = command_info[1]
        except IndexError:
            await turn_context.send_activity("Iets ging intern mis bij de bot. Contacteer iemand van de introductiecommissie.")
            return

        session = db.Session()
        existing_mentor_group = db.getFirst(session, db.MentorGroup, 'name', mentor_group_name)
        if existing_mentor_group:
            existing_mentor_group.channel_id = channel_id
            db.dbMerge(session, existing_mentor_group)
        else:
            mentor_group = db.MentorGroup(name=mentor_group_name, channel_id=channel_id)
            db.dbInsert(session, mentor_group)
        await turn_context.send_activity(f"Mentorgroep '{mentor_group_name}' is succesvol toegevoegd!")
        session.close()
    
    # Function that starts adding a separate USP location.
    async def add_USP_location(self, turn_context: TurnContext):
        try:
            USP_location_name = turn_context.activity.text.split()[1]
        except IndexError:
            await turn_context.send_activity("Je moet de naam van de commissie aan de bot meegeven: USPlocatieToevoegen <naam>")
            return
        channels = await TeamsInfo.get_team_channels(turn_context)
        # Again send a card with all channels to choose the corresponding one.
        card = CardFactory.hero_card(
            HeroCard(
                title="USPkanaal",
                text="Kies het kanaal waar deze USP locatie aan gelinkt moet worden.",
                buttons=[
                    CardAction(
                        type=ActionTypes.message_back,
                        title=channel.name,
                        text=f'RegUSPLocation {channel.id} {USP_location_name}'
                    ) for channel in channels if channel.name is not None and channel.name.startswith('USP')
                ],
            ),
        )
        await turn_context.send_activity(MessageFactory.attachment(card))

    # This function handles the choice of a channel for a USP location.
    async def register_USP_location(self, turn_context: TurnContext):
        command_info = turn_context.activity.text.split()

        try:
            USP_location_name = command_info[2]
            channel_id = command_info[1]
        except IndexError:
            await turn_context.send_activity("Iets ging intern mis bij de bot. Contacteer iemand van de introductiecommissie.")
            return

        session = db.Session()
        existing_USP_location = db.getFirst(session, db.USPLocation, 'name', USP_location_name)
        if existing_USP_location:
            existing_USP_location.channel_id = channel_id
            db.dbMerge(session, existing_USP_location)
        else:
            USP_location = db.USPLocation(name=USP_location_name, channel_id=channel_id)
            db.dbInsert(session, USP_location)
        await turn_context.send_activity(f"USP locatie '{USP_location_name}' is succesvol toegevoegd!")
        session.close()

    async def register_intro(self, turn_context: TurnContext):
        try:
            intro_password = turn_context.activity.text.split()[1]
        except IndexError:
            await turn_context.send_activity("Authenticatiefout! Je bent niet koel genoeg om intro te zijn...")
            return

        if intro_password == self.CONFIG.INTRO_PASSWORD:
            session = db.Session()
            sender = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            existing_user = db.getUserOnType(session, 'intro_user', sender.id)
            if not existing_user:
                new_user = db.IntroUser(user_teams_id=helper.get_user_id(sender), user_name=sender.name)
                db.dbInsert(session, new_user)
                await turn_context.send_activity("Je bent succesvol geregistreerd als Intro")
            else:
                await turn_context.send_activity("Je bent al geregistreerd als Intro!")
            session.close()
        else:
            await turn_context.send_activity("Authenticatiefout! Je bent niet koel genoeg om intro te zijn...")

    async def register_mentor(self, turn_context: TurnContext):
        command_info = turn_context.activity.text.split()

        try:
            mentor_password = command_info[1]
            mentor_group_name = command_info[2]
        except IndexError:
            await turn_context.send_activity("Dit commando heeft meer informatie nodig: IkBenMentor <wachtwoord> <mentorgroep_naam>.")
            return

        if mentor_password == self.CONFIG.MENTOR_PASSWORD:
            session = db.Session()
            sender = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            mentor_group = db.getFirst(session, db.MentorGroup, 'name', mentor_group_name)
            existing_user = db.getUserOnType(session, 'mentor_user', helper.get_user_id(sender))

            if not existing_user:
                if mentor_group:
                    new_user = db.MentorUser(user_teams_id=helper.get_user_id(sender),
                                            user_name=sender.name,
                                            mg_id=mentor_group.mg_id)
                    db.dbInsert(session, new_user)
                    await turn_context.send_activity(f"Je bent succesvol geregistreerd als een Mentor voor groep: '{mentor_group_name}''")
                else:
                    await turn_context.send_activity('Deze mentorgroep bestaat nog niet! Contacteer een Introlid als je vindt dat dit niet klopt.')
            else:
                existing_user.mg_id = mentor_group.mg_id
                db.dbMerge(session, existing_user)
                await turn_context.send_activity(f"Mentor '{sender.name}' is succesvol bijgewerkt!")
            session.close()
        else:
            turn_context.send_activity('Verkeerd wachtwoord!')

    async def register_committee_member(self, turn_context: TurnContext):
        command_info = turn_context.activity.text.split()

        try:
            committee_password = command_info[1]
            committee_name = command_info[2]
        except IndexError:
            await turn_context.send_activity("Dit commando heeft meer informatie nodig: IkBenCommissielid <wachtwoord> <commissie_naam>.")
            return

        if committee_password == self.CONFIG.COMMITTEE_PASSWORD:
            session = db.Session()
            sender = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            committee = db.getFirst(session, db.Committee, 'name', committee_name)
            existing_user = db.getUserOnType(session, 'committee_user', helper.get_user_id(sender))

            if not existing_user:
                if committee:
                    new_user = db.CommitteeUser(user_teams_id=helper.get_user_id(sender),
                                                user_name=sender.name,
                                                committee_id=committee.committee_id)
                    db.dbInsert(session, new_user)
                    await turn_context.send_activity(f"Je bent succesvol geregistreerd als een Commissielid van '{committee_name}'")
                else:
                    await turn_context.send_activity('Deze commissie bestaat nog niet! Contacteer een Introlid als je vindt dat dit niet klopt.')
            else:
                existing_user.committee_id = committee.committee_id
                db.dbMerge(session, existing_user)
                await turn_context.send_activity(f"Commissielid '{sender.name}' is succesvol bijgewerkt")
            session.close()
        else:
            await turn_context.send_activity('Verkeerd wachtwoord!')

    async def user_info(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)

        session = db.Session()
        users = db.getAll(session, db.User, 'user_teams_id', helper.get_user_id(user))

        if not users:
            await turn_context.send_activity("Je bent niet als een speciale gebruiker bij de bot geregistreerd!")
            session.close()
            return
        
        return_string = "Je bent als volgt bij de bot bekend:   \n"
        for user in users:
            if user.user_type == "intro_user":
                return_string += f'- Introlid   \n'
            elif user.user_type == "mentor_user":
                mentor_user = db.getUserOnType(session, 'mentor_user', user.user_teams_id)
                mentor_group = db.getFirst(session, db.MentorGroup, 'mg_id', mentor_user.mg_id)
                return_string += f'- Mentor voor groep {mentor_group.name}   \n'
            elif user.user_type == "committee_user":
                committee_user = db.getUserOnType(session, 'committee_user', user.user_teams_id)
                committee = db.getFirst(session, db.Committee, 'committee_id', committee_user.committee_id)
                return_string += f'- Commissielid voor {committee.name}   \n'
            elif user.user_type == "usp_user":
                location_user = db.getUserOnType(session, 'usp_user', user.user_teams_id)
                location = db.getFirst(session, db.USPLocation, 'location_id', location_user.location_id)
                return_string += f'- USP helper voor {location.name}    \n'
        session.close()
        await turn_context.send_activity(return_string)

    async def unlock_bot(self, turn_context: TurnContext):

        try:
            bot = turn_context.activity.text.split()[1]
        except IndexError:
            await turn_context.send_activity("Je moet specificeren welke bot je wilt activeren: Activeer <'alfas', 'c88' of 'uithof'>")
        
        if bot == 'alfas' and self.alfas_bot:
            self.alfas_bot.unlocked = True
        elif bot == 'uithof' and self.uithof_bot:
            self.uithof_bot.unlocked = True
        else:
            await turn_context.send_activity("Deze bot is niet bekend bij de ADMINbot of is niet gestart.")
            return
        
        await turn_context.send_activity("De bot is succesvol geactiveerd!")

    async def lock_bot(self, turn_context: TurnContext):

        try:
            bot = turn_context.activity.text.split()[1]
        except IndexError:
            await turn_context.send_activity("Je moet specificeren welke bot je wilt deactiveren: Activeer <'alfas', 'c88' of 'uithof'>")
        
        if bot == 'alfas' and self.alfas_bot:
            self.alfas_bot.unlocked = False
        elif bot == 'uithof' and self.uithof_bot:
            self.uithof_bot.unlocked = False
        else:
            await turn_context.send_activity("Deze bot is niet bekend bij de ADMINbot of is niet gestart.")
            return
        
        await turn_context.send_activity("De bot is succesvol geactiveerd!")
    
    ### Local helper methods!!!

    async def send_reminder(self, turn_context: TurnContext, minutes, channel_id, association):
        message = MessageFactory.text(f"Herinnering! De inschrijfbalie van {association} zal jullie groep bezoeken over {minutes} minuten.")
        await helper.create_channel_conversation(turn_context, channel_id, message)

    def string_to_datetime(self, time: str):
        hour, minute = int(time[:2]), int(time[3:])
        time = datetime.datetime(2020, 1, 1, hour, minute, 0, 0)
        return time
    
    def create_job(self, turn_context: TurnContext, channel_id, string_time: str, association):
        time = self.string_to_datetime(string_time)
        time_5 = time - datetime.timedelta(minutes=5)
        time_1 = time - datetime.timedelta(minutes=1)
        one_job = self.alfas_bot.scheduler.add_job(self.send_reminder, args=[turn_context, 1, channel_id, association],
                                        trigger='cron', year=self.CONFIG.ALFAS_DATE.year,
                                        month=self.CONFIG.ALFAS_DATE.month, day=self.CONFIG.ALFAS_DATE.day,
                                        hour=time_1.hour, minute=time_1.minute)
        five_job = self.alfas_bot.scheduler.add_job(self.send_reminder, args=[turn_context, 5, channel_id, association],
                                        trigger='cron', year=self.CONFIG.ALFAS_DATE.year,
                                        month=self.CONFIG.ALFAS_DATE.month, day=self.CONFIG.ALFAS_DATE.day,
                                        hour=time_5.hour, minute=time_5.minute)
        return [one_job, five_job]