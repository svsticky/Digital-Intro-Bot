# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import threading
from random import seed
from random import choice
from botbuilder.core import CardFactory, TurnContext, MessageFactory
from botbuilder.core.teams import TeamsActivityHandler, TeamsInfo
from botbuilder.schema import CardAction, HeroCard, Mention, ConversationParameters
from botbuilder.schema._connector_client_enums import ActionTypes
import modules.database as db
import modules.helper_funtions as helper
from config import DefaultConfig
from google_api import GoogleSheet


class StickyALFASBot(TeamsActivityHandler):
    def __init__(self, app_id: str, app_password: str):
        self._app_id = app_id
        self._app_password = app_password
        self.CONFIG = DefaultConfig()
        self.unlocked = True
        self.lock = threading.Lock()
        seed(1230948385) # Does it really matter :P?

    async def on_message_activity(self, turn_context: TurnContext):
        """
            All message activities towards the bot enter this function.
            var turn_context: contains most of the message information.
        """
        TurnContext.remove_recipient_mention(turn_context.activity)
        turn_context.activity.text = turn_context.activity.text.strip()

        if not self.unlocked:
            await turn_context.send_activity("De bot is gedeactiveerd en kan dus niet gebruikt worden.")
            return

        # Based on a given command, the bot performs a function.

        # Return all committees that are available at this moment
        if turn_context.activity.text == "BeschikbareCommissies":
            await self.available_committees(turn_context)
            return

        # Choose a committee for a mentor group to visit.
        if turn_context.activity.text.startswith("ChooseCommittee"):
            await self.choose_committee(turn_context)
            return
        
        if turn_context.activity.text == "RandomCommittee":
            await self.random_committee(turn_context)
            return

        # When someone enrolls for a certain committee
        if turn_context.activity.text.startswith("Enroll"):
            await self.enroll(turn_context)
            return

        if turn_context.activity.text == "Vrijgeven":
            await self.release_committee(turn_context)
            return
        
        if turn_context.activity.text == "VerenigingsPlanning":
            await self.association_planning(turn_context)
            return
        
        if turn_context.activity.text == "UpdateCard":
            await self.update_card(turn_context)
            return

        # Get all intro members
        if turn_context.activity.text == "Introleden":
            await self.get_intro(turn_context)
            return
        
        # Save enrollments to google sheet
        if turn_context.activity.text == "InschrijvingenOpslaan":
            await self.save_enrollments(turn_context)
            return

        #TODO: what to send if it is not a command?
        await turn_context.send_activity("Ik ken dit commando niet. Misschien heb je een typfout gemaakt?")
        return

    # Obtains all intro members
    async def get_intro(self, turn_context: TurnContext):
        return_text = ''
        session = db.Session()
        users = db.getAllUsersOnType(session, 'intro_user')
        session.close()

        for user in users:
            return_text += f'{user.user_name}   \n'

        await turn_context.send_activity(return_text)

    async def available_committees(self, turn_context: TurnContext):
        channel_id = turn_context.activity.channel_data['teamsChannelId']
        session = db.Session()
        if not db.getFirst(session, db.MentorGroup, 'channel_id', channel_id):
            await turn_context.send_activity("Je kunt dit commando alleen uitvoeren in een kanaal van een mentorgroep")
            session.close()
            return

        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        mentor_db_user = db.getUserOnType(session, 'mentor_user', helper.get_user_id(user))
        if not mentor_db_user:
            await turn_context.send_activity("Alleen een mentor kan dit commando uitvoeren.")
            session.close()
            return

        committees = db.getAll(session, db.Committee, 'occupied', False)

        card = CardFactory.hero_card(
            HeroCard(
                title="Beschikbare Commissies",
                text="Kies de commissie die je wil ontmoeten! Je kunt een commissie kiezen of de bot dit werkt laten doen. \
                      Klik op 'Refresh' om de lijst te vernieuwen.",
                buttons=[
                    CardAction(
                        type=ActionTypes.message_back,
                        title="\u27F3 Refresh",
                        text=f"UpdateCard"
                    ),
                    CardAction(
                        type=ActionTypes.message_back,
                        title="\u2753 Random",
                        text=f"RandomCommittee"
                    )] +
                    [CardAction(
                        type=ActionTypes.message_back,
                        title=committee.name,
                        text=f"ChooseCommittee {committee.name}"
                    ) for committee in committees]
                )
            )
        session.close()
        choosing_activity = MessageFactory.attachment(card)
        await helper.create_channel_conversation(turn_context, channel_id, choosing_activity)
    
    async def update_card(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)

        session = db.Session()
        mentor_db_user = db.getUserOnType(session, 'mentor_user', helper.get_user_id(user))
        if not mentor_db_user:
            await turn_context.send_activity("Alleen een mentor kan deze actie uitvoeren!")
            session.close()
            return

        committees = db.getAll(session, db.Committee, 'occupied', False)

        card = CardFactory.hero_card(
            HeroCard(
                title="Beschikbare Commissies",
                text="Kies de commissie die je wil ontmoeten! Je kunt een commissie kiezen of de bot dit werkt laten doen. \
                      Klik op 'Refresh' om de lijst te vernieuwen.",
                buttons=[
                    CardAction(
                        type=ActionTypes.message_back,
                        title="\u27F3 Refresh",
                        text=f"UpdateCard"
                    ),
                    CardAction(
                        type=ActionTypes.message_back,
                        title="\u2753 Random",
                        text=f"RandomCommittee"
                    )] +
                    [CardAction(
                        type=ActionTypes.message_back,
                        title=committee.name,
                        text=f"ChooseCommittee {committee.name}"
                    ) for committee in committees]
                )
            )
        session.close()
        updated_card = MessageFactory.attachment(card)
        updated_card.id = turn_context.activity.reply_to_id
        await turn_context.update_activity(updated_card)

    #Should only be reached from clicking on the card button.
    async def random_committee(self, turn_context: TurnContext):
        #Gets random committee from the database.
        channel_id = helper.get_channel_id(turn_context.activity)
        session = db.Session()
        mentor_group = db.getFirst(session, db.MentorGroup, 'channel_id', channel_id)

        if not mentor_group:
            await turn_context.send_activity("Deze mentorgroep bestaat niet voor de bot. Registreer de groep eerst of vraag een introlid dit te doen.")
            session.close()
            return
        
        if mentor_group.occupied:
            await turn_context.send_activity("Je hebt al een match met een andere commissie, deze moet eerst door de commissie weer worden vrijgegeven.")
            session.close()
            return
            
        try:
            self.lock.acquire()
            committees = db.getNonVisitedCommittees(session, mentor_group.mg_id)

            if not committees:
                await turn_context.send_activity("Alle commissies zijn op dit moment bezet. Probeer het later nog eens.")
                session.close()
                return

            chosen_committee = choice(committees)
            await self.match_group_with_committee(turn_context, session, chosen_committee, mentor_group)
        finally:
            self.lock.release()

    async def choose_committee(self, turn_context: TurnContext):
        #Get user from teams and database
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        session = db.Session()
        db_user = db.getUserOnType(session, 'mentor_user', helper.get_user_id(user))

        #If exists in database...
        if db_user:
            # Check if command is correct
            try:
                committee_name = turn_context.activity.text.split()[1]
            except IndexError:
                await turn_context.send_activity("Er ging iets intern mis bij de bot. Contacteer een introlid om het op te lossen.")

            mentor_group = db.getFirst(session, db.MentorGroup, 'mg_id', db_user.mg_id)

            if mentor_group.occupied:
                await turn_context.send_activity("Je hebt al een match met een andere commissie, deze moet eerst door de commissie weer worden vrijgegeven.")
                session.close()
                return            

            # If committee is not occupied
            try:
                self.lock.acquire()
                committee = db.getFirst(session, db.Committee, 'name', committee_name)
                await self.match_group_with_committee(turn_context, session, committee, mentor_group)
            finally:
                self.lock.release()          
        else:
            await turn_context.send_activity(f"Je bent geen mentor wat betekent dat je geen rechten hebt om dit commando uit te voeren.")
        session.close()

    async def enroll(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)

        try:
            committee_id = turn_context.activity.text.split()[1]
        except IndexError:
            await turn_context.send_activity("Er ging iets intern mis bij de bot. Contacteer een introlid om het op te lossen.")
            return

        session = db.Session()
        ex_enrollment = db.getEnrollment(session, committee_id, user.email)
        committee = db.getFirst(session, db.Committee, 'committee_id', committee_id)

        if not ex_enrollment:
            enrollment = db.Enrollment(committee_id=committee_id, first_name=user.given_name,
                                       last_name=user.surname, email_address=user.email)
            db.dbInsert(session, enrollment)
            await helper.create_personal_conversation(turn_context, user, f"Je bent toegevoegd aan de interesselijst voor '{committee.name}'", self._app_id)
        session.close()

    async def release_committee(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        session = db.Session()
        db_user = db.getUserOnType(session, 'committee_user', helper.get_user_id(user))

        if db_user:
            # Set committee occupied to False
            committee = db.getFirst(session, db.Committee, 'committee_id', db_user.committee_id)
            if not committee.occupied:
                message = MessageFactory.text("De commissie was al vrij. Dit commando is overbodig.")
                await helper.create_channel_conversation(turn_context, committee.channel_id, message)
                return
            committee.occupied = False
            db.dbMerge(session, committee)
            # Get the visit and set it to finished.
            visit = db.getFirst(session, db.Visit, 'committee_id', committee.committee_id)
            visit.finished = True
            db.dbMerge(session, visit)
            # Set mentor_group occupation to False
            mentor_group = db.getFirst(session, db.MentorGroup, 'mg_id', visit.mg_id)
            mentor_group.occupied = False
            db.dbMerge(session, mentor_group)
            release_message = MessageFactory.text("De commissie is weer vrijgegeven. Verwacht een nieuwe ronde spoedig!")
            await helper.create_channel_conversation(turn_context, committee.channel_id, release_message)
            release_message = MessageFactory.text("Jullie kunnen weer een nieuwe commissie kiezen!")
            await helper.create_channel_conversation(turn_context, mentor_group.channel_id, release_message)
        else:
            await turn_context.send_activity("Je bent niet gemachtigd om dit command uit te voeren.")
        session.close()

    async def association_planning(self, turn_context: TurnContext):
        channel_id = turn_context.activity.channel_data['teamsChannelId']
        session = db.Session()
        mentor_group = db.getFirst(session, db.MentorGroup, 'channel_id', channel_id)
        if not mentor_group:
            await turn_context.send_activity("Je kunt dit commando alleen uitvoeren vanuit een mentorgroep kanaal.")
            session.close()
            return

        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        mentor_db_user = db.getUserOnType(session, 'mentor_user', helper.get_user_id(user))
        if not mentor_db_user:
            await turn_context.send_activity("Alleen een mentor kan dit commando uitvoeren.")
            session.close()
            return

        return_message = "De inschrijvingsclub voor de verenigingen komen langs op de volgende tijden:\n\n"
        association_times = db.getAssociationPlanning(session, mentor_group.mg_id)
        for time in association_times:
            return_message += f"- {time[0]}: {time[1]} uur\n\n"

        await turn_context.send_activity(return_message)

    async def save_enrollments(self, turn_context: TurnContext):
        user = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
        session = db.Session()
        db_user = db.getUserOnType(session, 'intro_user', helper.get_user_id(user))

        if not db_user:
            await turn_context.send_activity("Je bent niet gemachtigd om dit command uit te voeren.")
            session.close()
            return
        
        sorted_enrollments = {}

        enrollments = db.getTable(session, db.Enrollment)
        # Build dictionary from database
        for enrollment in enrollments:
            committee = db.getFirst(session, db.Committee, 'committee_id', enrollment.committee_id)
            if committee.name in sorted_enrollments:
                sorted_enrollments[committee.name].append(enrollment)
            else:
                sorted_enrollments[committee.name] = [enrollment]
        
        google_values = [
            ['Voornaam', 'Achternaam', 'UU-mail'],
            ["", "", ""]
        ]
        # Build googlesheets datastructure
        for committee in sorted_enrollments.keys():
            google_values.append([committee, "", ""])
            enrollments = sorted_enrollments[committee]
            for enrollment in enrollments:
                google_values.append([enrollment.first_name, enrollment.last_name, enrollment.email_address])
            google_values.append(["", "", ""])

        GoogleSheet().save_enrollments(google_values)
        session.close()
        await turn_context.send_activity("De intresselijst is succesvol opgeslagen!")

    #Helper functions!
    async def match_group_with_committee(self, turn_context, session, committee, mentor_group):
        if not committee.occupied:
            # Immediately set it as occupied, then do the rest (to make it atomic)
            committee.occupied = True
            db.dbMerge(session, committee)
            # Get mentor group and create a visit.
            mentor_group.occupied = True
            db.dbMerge(session, mentor_group)
            visit = db.Visit(mg_id=mentor_group.mg_id, committee_id=committee.committee_id)
            db.dbInsert(session, visit)
            await turn_context.send_activity(f"De leden van de commissie '{committee.name}' zullen jullie gesprek zo spoedig mogelijk vergezellen!")
            committee_message = MessageFactory.text(f"Jullie worden verwacht bij mentorgroep: '{mentor_group.name}'. Ga er zo spoedig mogelijk heen!")
            await helper.create_channel_conversation(turn_context, committee.channel_id, committee_message)
            enroll_button = await self.create_enrollment_button(committee)
            await turn_context.send_activity(enroll_button)
        else:
            await turn_context.send_activity("Deze commissie is al bezet. Kies een andere.\
                                              Dit is waarschijnlijk gebeurd omdat een andere groep net iets sneller was.")

    #Example functions!
    async def return_members(self, turn_context: TurnContext):
        members = await TeamsInfo.get_team_members(turn_context)
        return_text = ''
        for member in members:
            return_text += f'{member.id} {member.name}   \n'
        await turn_context.send_activity(return_text)

    async def _delete_card_activity(self, turn_context: TurnContext):
        await turn_context.delete_activity(turn_context.activity.reply_to_id)

    async def create_enrollment_button(self, committee):
        card = CardFactory.hero_card(
            HeroCard(
                title='Intresse',
                text=f"De commissie {committee.name} zal jullie vertellen over hun activiteiten. "\
                      'Als je intresse hebt om jezelf bij deze commissie te voegen, klik dan op de onderstaande knop.',
                buttons=[
                    CardAction(
                        type=ActionTypes.message_back,
                        title="Ik ben geïnteresseerd!",
                        text=f"Enroll {committee.committee_id}",
                    ),
                ],
            )
        )
        return MessageFactory.attachment(card)
