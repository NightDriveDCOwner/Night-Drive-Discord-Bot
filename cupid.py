from disnake.ext import commands
from disnake import Embed, ButtonStyle, SelectOption
from disnake.ui import Select, View, Button
import disnake
import sqlite3
import logging
import asyncio
from globalfile import Globalfile
from rolehierarchy import rolehierarchy
from dbconnection import DatabaseConnection
from dotenv import load_dotenv
import os
from exceptionhandler import exception_handler


class Cupid(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger("Cupid")
        self.globalfile = Globalfile(bot)
        self.db: sqlite3.Connection = DatabaseConnection()
        self.cursor: sqlite3.Cursor = self.db.connection.cursor()
        self.globalfile = Globalfile(bot)  

        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.setup_database()

    def setup_database(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS QUESTION (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                QUESTION TEXT NOT NULL
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS ANSWER (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                QUESTIONID INTEGER NOT NULL,
                ANSWER TEXT NOT NULL,
                UNIQUE(USERID, QUESTIONID)
            )
        """)
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS USER_SETTINGS (
            ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            USERID INTEGER NOT NULL,
            SETTING TEXT NOT NULL,
            VALUE TEXT NOT NULL
        )
        """)
        self.db.connection.commit() 

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.debug("DatingBot is ready.")
        self.bot.add_view(self.create_main_view())

    def create_main_view(self):
        view = View(timeout=None)
        view.add_item(Button(label="Fragen beantworten", style=ButtonStyle.blurple, custom_id="answer_questions"))
        view.add_item(Button(label="Passende User finden", style=ButtonStyle.green, custom_id="find_matches"))
        view.add_item(Button(label="Einstellungen", style=ButtonStyle.gray, custom_id="user_settings"))
        return view

    @exception_handler
    async def _dating_info(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt Informationen über den Dating Bot an."""
        embed = Embed(
            title="Cupid",
            description=(
                "Willkommen beim Dating Bot von Date Night!\n\n"
                "Du kannst Fragen beantworten, um herauszufinden, welche User am besten zu dir passen. Vorerst ist nur das Beantworten von Fragen möglich "
                "damit ich morgen die Funktion bzgl. dem finden der passenden User hinzufügen und testen kann.\n\n"
                "Es wird ebenfalls so eingerichtet, dass nur User, die die Fragen beantwortet haben, miteinander gematcht werden können. Ebenfalls wird das matchen verhindert "
                "wenn du die Rolle <@&1066800831225147512> hast. Du findest nur User die diese Rolle nicht haben. "
                "Solltest du also keine DMs von anderen Usern erhalten wollen, dann kannst du dir diese Rolle [hier](https://discord.com/channels/854698446996766730/1039167130190491709/1327047028710309960) hinzufügen.\n\n"
                "Der Bot ist noch in der Entwicklung und wird ständig verbessert.\nFalls du Bugs findest oder Verbesserungsvorschläge hast, melde dich bitte in <#1039195922539761684>.\n\n"
                "Viel Spaß beim Fragen beantworten!\n\n"
                "Liebe Grüße, dein Date Night Team"
            ),
            color=disnake.Color.blue()
        )
        await inter.channel.send(embed=embed, view=self.create_main_view())
        await inter.response.send_message("Embed wurde erfolgreich gesendet.", ephemeral=True)

    @exception_handler
    @commands.Cog.listener()
    async def on_interaction(self, interaction: disnake.MessageInteraction):
        if isinstance(interaction, disnake.MessageInteraction):
            custom_id = interaction.data.custom_id
            if custom_id == "answer_questions":
                self.logger.info(f"User {interaction.user.name} wants to answer questions.")
                # await interaction.response.defer(ephemeral=True)
                await self.show_next_question(interaction)
            elif custom_id == "find_matches":
                await self.find_matches(interaction)
            elif custom_id == "user_settings":
                await self.show_user_settings(interaction)
            elif custom_id.startswith("gender_"):
                await interaction.response.defer(ephemeral=True)
                selected_gender = custom_id.split("_")[1]
                userrecord = await self.globalfile.get_user_record(discordid=interaction.user.id)
                await self.save_user_preference(userrecord['ID'], "preference", selected_gender)
                embed = Embed(
                    title="Einstellungen",
                    description=f"Du hast erfolgreich {selected_gender} als Präferenz ausgewählt.",
                    color=disnake.Color.green()
                )
                await interaction.edit_original_message(embed=embed, view=None)

    @exception_handler
    async def show_user_settings(self, interaction: disnake.MessageInteraction):
        embed = Embed(
            title="Einstellungen",
            description="Bitte wähle das Geschlecht aus, das du suchst:",
            color=disnake.Color.blue()
        )
        embed.set_footer(text="Deine Auswahl bleibt anonym und ist allein fürs Team einsehbar.")

        view = View(timeout=None)
        view.add_item(Button(label="Männer", style=ButtonStyle.blurple, custom_id="gender_male"))
        view.add_item(Button(label="Frauen", style=ButtonStyle.red, custom_id="gender_female"))
        view.add_item(Button(label="Divers", style=ButtonStyle.grey, custom_id="gender_divers"))

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @exception_handler
    async def show_next_question(self, interaction: disnake.MessageInteraction, edit=False):
        user_record = await self.globalfile.get_user_record(discordid=str(interaction.user.id))
        user_id = user_record['ID']

        self.cursor.execute("SELECT COUNT(*) FROM ANSWER WHERE USERID = ?", (user_id,))
        answered_count = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT COUNT(*) FROM QUESTION")
        total_questions = self.cursor.fetchone()[0]

        self.cursor.execute("""
            SELECT q.ID, q.QUESTION 
            FROM QUESTION q 
            LEFT JOIN ANSWER a ON q.ID = a.QUESTIONID AND a.USERID = ? 
            WHERE a.QUESTIONID IS NULL 
            LIMIT 1
        """, (user_id,))
        question = self.cursor.fetchone()

        if not question:
            if edit:
                await interaction.edit_original_message(content="Du hast bereits alle aktuellen Fragen beantwortet.", embed=None, view=None)
            else:
                await interaction.response.send_message("Du hast bereits alle Fragen beantwortet.", ephemeral=True)
            return

        question_id, question_text = question
        embed = Embed(
            title=f"Frage {answered_count + 1}/{total_questions}",
            description=question_text,
            color=disnake.Color.blurple()
        )
        view = await self.create_answer_view(question_id)
        
        if edit:
            await interaction.edit_original_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @exception_handler
    async def create_answer_view(self, question_id):
        view = View(timeout=None)
        view.add_item(Button(label="no", style=ButtonStyle.red, custom_id=f"answer_{question_id}_no"))
        view.add_item(Button(label="Neutral", style=ButtonStyle.gray, custom_id=f"answer_{question_id}_neutral"))
        view.add_item(Button(label="yes", style=ButtonStyle.green, custom_id=f"answer_{question_id}_yes"))
        return view

    @exception_handler
    @commands.Cog.listener()
    async def on_button_click(self, interaction: disnake.MessageInteraction):
        custom_id = interaction.component.custom_id
        if custom_id.startswith("answer_"):
            parts = custom_id.split("_")
            if len(parts) == 3:
                _, question_id, answer = parts
                await self.save_answer(interaction.user.id, int(question_id), answer)
                await self.handle_answer(interaction, question_id)

    @exception_handler
    async def save_answer(self, user_id, question_id, answer):
        user_record = await self.globalfile.get_user_record(discordid=str(user_id))
        if user_record:
            user_id = user_record['ID']
            self.cursor.execute("""
                INSERT INTO ANSWER (USERID, QUESTIONID, ANSWER)
                VALUES (?, ?, ?)
                ON CONFLICT(USERID, QUESTIONID) DO UPDATE SET ANSWER=excluded.ANSWER
            """, (user_id, question_id, answer))
            self.db.connection.commit()

    @exception_handler
    async def handle_answer(self, interaction, question_id):
        embed = interaction.message.embeds[0]
        embed.add_field(name="Status", value="Frage erfolgreich beantwortet. ✅", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
        await asyncio.sleep(1.5)
        await self.show_next_question(interaction, edit=True)

    @exception_handler
    async def find_matches(self, interaction: disnake.MessageInteraction):
        await interaction.response.defer()
        try:
            # Define role IDs
            MALE_ROLE_ID = 1065695971540996317
            FEMALE_ROLE_ID = 1065696210771517572
            DIVERS_ROLE_ID = 1065696212377927680
            DMS_CLOSED_ROLE_ID = 1066800831225147512

            member = await interaction.guild.fetch_member(interaction.user.id)

            if DMS_CLOSED_ROLE_ID in [role.id for role in member.roles]:
                await interaction.followup.send("Du hast die Rolle 'DMs Geschlossen'. Bitte entferne diese Rolle, um fortzufahren.", ephemeral=True)
                return
                    
            if MALE_ROLE_ID in [role.id for role in member.roles]:
                user_sex = "male"
            elif FEMALE_ROLE_ID in [role.id for role in member.roles]:
                user_sex = "female"
            else:
                user_sex = "divers"

            userrecord = await self.globalfile.get_user_record(discordid=interaction.user.id)
            user_id = userrecord['ID']

            # Update user's sex in the database
            self.cursor.execute("""
                INSERT INTO USER_SETTINGS (USERID, SETTING, VALUE)
                VALUES (?, 'sex', ?)
                ON CONFLICT(USERID, SETTING) DO UPDATE SET VALUE = excluded.VALUE
            """, (user_id, user_sex))
            self.db.connection.commit()

            self.cursor.execute("SELECT QUESTIONID, ANSWER FROM ANSWER WHERE USERID = ?", (user_id,))
            user_answers = self.cursor.fetchall()

            if not user_answers:
                await interaction.followup.send("Du hast noch keine Fragen beantwortet.", ephemeral=True)
                return

            self.cursor.execute("SELECT COUNT(*) FROM QUESTION")
            total_questions = self.cursor.fetchone()[0]

            if len(user_answers) < total_questions:
                await interaction.followup.send("Du hast noch nicht alle Fragen beantwortet.", ephemeral=True)
                return

            self.cursor.execute("SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'preference'", (user_id,))
            user_preference = self.cursor.fetchone()
            if not user_preference:
                await interaction.followup.send("Du hast noch keine Präferenzen gesetzt. Mache das bitte über den ""Einstellungs""-Button", ephemeral=True)
                return
            user_preference = user_preference[0]

            embed = Embed(
                title="Berechnungen laufen",
                description="Die Berechnungen laufen und es kann ein paar Minuten dauern. Bitte gedulde dich.",
                color=disnake.Color.orange()
            )
            sent_message: disnake.WebhookMessage = await interaction.followup.send(embed=embed, ephemeral=True)
            message_id = sent_message.id

            matches = {}
            for question_id, user_answer in user_answers:
                self.cursor.execute("SELECT USERID, ANSWER FROM ANSWER WHERE QUESTIONID = ?", (question_id,))
                matching_users = self.cursor.fetchall()
                for match in matching_users:
                    match_user_id, match_answer = match
                    if match_user_id == user_id:
                        continue

                    self.cursor.execute("SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'preference'", (match_user_id,))
                    match_preference = self.cursor.fetchone()
                    if not match_preference or match_preference[0] != user_sex:
                        continue

                    match_user_record = await self.globalfile.get_user_record(user_id=match_user_id)
                    match_discord_id = match_user_record['DISCORDID']
                    match_member = await interaction.guild.fetch_member(match_discord_id)
                    if not match_member:
                        continue

                    # Check if the match has the DMs Closed role
                    if DMS_CLOSED_ROLE_ID in [role.id for role in match_member.roles]:
                        continue                

                    # Check if the match has the preferred role
                    if user_preference == "male" and MALE_ROLE_ID not in [role.id for role in match_member.roles]:
                        continue
                    if user_preference == "female" and FEMALE_ROLE_ID not in [role.id for role in match_member.roles]:
                        continue
                    if user_preference == "divers" and DIVERS_ROLE_ID not in [role.id for role in match_member.roles]:
                        continue

                    score = matches.get(match_user_id, 0)
                    if user_answer == match_answer:
                        score += 2
                        self.logger.debug(f"User {match_user_id}: +2 Punkte für gleiche Antwort bei Frage {question_id}")
                    elif (user_answer == "neutral" and match_answer in ["yes", "no"]) or (match_answer == "neutral" and user_answer in ["yes", "no"]):
                        score += 1
                        self.logger.debug(f"User {match_user_id}: +1 Punkt für neutrale Antwort bei Frage {question_id}")
                    elif (user_answer == "yes" and match_answer == "no") or (user_answer == "no" and match_answer == "yes"):
                        score += 0
                        self.logger.debug(f"User {match_user_id}: +0 Punkte für unterschiedliche Antwort bei Frage {question_id}")
                    matches[match_user_id] = score

            matches = {k: (v / (total_questions * 2)) * 100 for k, v in matches.items()}

            sorted_matches = sorted(matches.items(), key=lambda x: x[1], reverse=True)[:10]
            match_list = "\n".join([f"<@{(await self.globalfile.get_user_record(user_id=match_id))['DISCORDID']}>: {score:.2f}% übereinstimmende Antworten" for match_id, score in sorted_matches])

            embed = Embed(
                title="Passende User",
                description=match_list if match_list else "Keine passenden User gefunden.",
                color=disnake.Color.green()
            )
            await interaction.followup.edit_message(message_id, embed=embed)
        except Exception as e:
            self.logger.critical(f"An error occurred: {e}")

    @exception_handler
    async def _debug_top_matches(self, inter: disnake.ApplicationCommandInteraction):        
        """Zeigt die Top 10 Benutzer mit den besten Übereinstimmungen an."""
        try:
            await inter.response.defer()

            # Define role IDs
            MALE_ROLE_ID = 1065695971540996317
            FEMALE_ROLE_ID = 1065696210771517572
            DIVERS_ROLE_ID = 1065696212377927680  # Example ID for the divers role

            member = await inter.guild.fetch_member(inter.user.id)
            if MALE_ROLE_ID in [role.id for role in member.roles]:
                user_sex = "male"
            elif FEMALE_ROLE_ID in [role.id for role in member.roles]:
                user_sex = "female"
            else:
                user_sex = "divers"

            userrecord = await self.globalfile.get_user_record(discordid=inter.user.id)
            user_id = userrecord['ID']

            # Update user's sex in the database
            self.cursor.execute("""
                INSERT INTO USER_SETTINGS (USERID, SETTING, VALUE)
                VALUES (?, 'sex', ?)
                ON CONFLICT(USERID, SETTING) DO UPDATE SET VALUE = excluded.VALUE
            """, (user_id, user_sex))
            self.db.connection.commit()

            self.cursor.execute("SELECT QUESTIONID, ANSWER FROM ANSWER WHERE USERID = ?", (user_id,))
            user_answers = self.cursor.fetchall()

            if not user_answers:
                await inter.followup.send("Du hast noch keine Fragen beantwortet.", ephemeral=True)
                return

            self.cursor.execute("SELECT COUNT(*) FROM QUESTION")
            total_questions = self.cursor.fetchone()[0]

            if len(user_answers) < total_questions:
                await inter.followup.send("Du hast noch nicht alle Fragen beantwortet.", ephemeral=True)
                return

            self.cursor.execute("SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'preference'", (user_id,))
            user_preference = self.cursor.fetchone()
            if not user_preference:
                await inter.followup.send("Du hast noch keine Präferenzen gesetzt. Mache das bitte über den ""Einstellungs""-Button", ephemeral=True)
                return
            user_preference = user_preference[0]

            matches = {}
            match_details = {}
            for question_id, user_answer in user_answers:
                self.cursor.execute("SELECT USERID, ANSWER FROM ANSWER WHERE QUESTIONID = ?", (question_id,))
                matching_users = self.cursor.fetchall()
                for match in matching_users:
                    match_user_id, match_answer = match
                    if match_user_id == user_id:
                        continue

                    self.cursor.execute("SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'preference'", (match_user_id,))
                    match_preference = self.cursor.fetchone()
                    if not match_preference or match_preference[0] != user_sex:
                        continue

                    match_user_record = await self.globalfile.get_user_record(user_id=match_user_id)
                    match_discord_id = match_user_record['DISCORDID']
                    match_member = await inter.guild.fetch_member(match_discord_id)
                    if not match_member:
                        continue

                    # Check if the match has the preferred role
                    if user_preference == "male" and MALE_ROLE_ID not in [role.id for role in match_member.roles]:
                        continue
                    if user_preference == "female" and FEMALE_ROLE_ID not in [role.id for role in match_member.roles]:
                        continue
                    if user_preference == "divers" and DIVERS_ROLE_ID not in [role.id for role in match_member.roles]:
                        continue

                    score = matches.get(match_user_id, 0)
                    if user_answer == match_answer:
                        score += 2
                        match_details.setdefault(match_user_id, {"+2": 0, "+1": 0, "+0.5": 0})["+2"] += 1
                        self.logger.debug(f"User {match_user_id}: +2 Punkte für gleiche Antwort bei Frage {question_id}")
                    elif (user_answer == "neutral" and match_answer in ["yes", "no"]) or (match_answer == "neutral" and user_answer in ["yes", "no"]):
                        score += 1
                        match_details.setdefault(match_user_id, {"+2": 0, "+1": 0, "+0.5": 0})["+1"] += 1
                        self.logger.debug(f"User {match_user_id}: +1 Punkt für neutrale Antwort bei Frage {question_id}")
                    elif (user_answer == "yes" and match_answer == "no") or (user_answer == "no" and match_answer == "yes"):
                        score += 0
                        match_details.setdefault(match_user_id, {"+2": 0, "+1": 0, "+0.5": 0})["+0.5"] += 1
                        self.logger.debug(f"User {match_user_id}: +0.5 Punkte für unterschiedliche Antwort bei Frage {question_id}")
                    matches[match_user_id] = score

            matches = {k: (v / (total_questions * 2)) * 100 for k, v in matches.items()}

            sorted_matches = sorted(matches.items(), key=lambda x: x[1], reverse=True)[:10]
            match_list = "\n".join([f"<@{await self.globalfile.get_user_record(user_id=match_id)['DISCORDID']}>: {score:.2f}% übereinstimmende Antworten" for match_id, score in sorted_matches])

            for match_id, score in sorted_matches:
                self.logger.debug(f"User {match_id}: {score:.2f}% übereinstimmende Antworten")

            embed = Embed(
                title="Top 10 Passende User",
                description=match_list if match_list else "Keine passenden User gefunden.",
                color=disnake.Color.green()
            )
            await inter.followup.send(embed=embed, ephemeral=True)

            # Create a debug embed for the first match
            if sorted_matches:
                top_match_id, top_match_score = sorted_matches[0]
                top_match_details = match_details.get(top_match_id, {"+2": 0, "+1": 0, "+0.5": 0})
                debug_embed = Embed(
                    title="Debug Informationen für den Top-Match",
                    description=f"User: <@{await self.globalfile.get_user_record(user_id=top_match_id)['DISCORDID']}>",
                    color=disnake.Color.blue()
                )
                debug_embed.add_field(name="+2 Punkte", value=str(top_match_details["+2"]), inline=True)
                debug_embed.add_field(name="+1 Punkt", value=str(top_match_details["+1"]), inline=True)
                debug_embed.add_field(name="+0.5 Punkte", value=str(top_match_details["+0.5"]), inline=True)
                await inter.followup.send(embed=debug_embed, ephemeral=True)
        except Exception as e:
            self.logger.critical(f"An error occurred: {e}")

    @exception_handler
    async def save_user_preference(self, user_id, setting, value):
        self.cursor.execute("""
            SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = ?
        """, (user_id, setting))
        existing_value = self.cursor.fetchone()

        if existing_value:
            self.cursor.execute("""
                UPDATE USER_SETTINGS SET VALUE = ? WHERE USERID = ? AND SETTING = ?
            """, (value, user_id, setting))
        else:
            self.cursor.execute("""
                INSERT INTO USER_SETTINGS (USERID, SETTING, VALUE)
                VALUES (?, ?, ?)
            """, (user_id, setting, value))

        self.db.connection.commit()

    @exception_handler
    async def _recalculate_invite_xp(self, inter: disnake.ApplicationCommandInteraction):
        """Berechnet die INVITEXP Werte aus der INVITE_XP Tabelle neu."""
        await inter.response.defer()
        cursor = self.db.connection.cursor()
        
        # Lade den Faktor aus der env Datei
        load_dotenv(dotenv_path="envs/settings.env", override=True)
        factor = int(os.getenv("FACTOR", 50))

        # Hole alle Einträge aus der INVITE_XP-Tabelle
        cursor.execute("SELECT USERID, SUM(COUNT) FROM INVITE_XP GROUP BY USERID")
        invite_xp_data = cursor.fetchall()

        for user_id, total_invite_count in invite_xp_data:
            invite_xp = total_invite_count * factor
            cursor.execute("UPDATE EXPERIENCE SET INVITE = ? WHERE USERID = ?", (invite_xp, user_id))
        
        self.db.connection.commit()
        await inter.edit_original_response(content="INVITEXP Werte wurden erfolgreich neu berechnet.") 

    @exception_handler
    async def _deletedata_for_nonexistent_user(self, inter: disnake.ApplicationCommandInteraction):
        # Hole alle Benutzer-IDs aus der ANSWER-Tabelle
        await inter.response.defer()
        cursor = self.db.connection.cursor()
        self.cursor.execute("SELECT DISTINCT USERID FROM ANSWER")
        answer_user_ids = [row[0] for row in self.cursor.fetchall()]

        # Hole alle Benutzer-IDs aus der USER_SETTINGS-Tabelle
        self.cursor.execute("SELECT DISTINCT USERID FROM USER_SETTINGS")
        settings_user_ids = [row[0] for row in self.cursor.fetchall()]

        # Kombiniere alle Benutzer-IDs
        all_user_ids = set(answer_user_ids + settings_user_ids)

        # Überprüfe, ob die Benutzer noch auf dem Server sind
        for user_id in all_user_ids:
            user_record = await self.globalfile.get_user_record(user_id=user_id)
            if user_record:
                discord_id = user_record['DISCORDID']
                member = inter.guild.get_member(int(discord_id))
                if not member:
                    # Lösche die Daten des Benutzers, wenn er nicht mehr auf dem Server ist
                    cursor.execute("DELETE FROM ANSWER WHERE USERID = ?", (int(user_id),))
                    cursor.execute("DELETE FROM USER_SETTINGS WHERE USERID = ?", (int(user_id),))
                    self.logger.debug(f"Deleted data for user ID {user_id} who is no longer on the server.")
        self.db.connection.commit()
        
        await inter.edit_original_response(content="Daten für Benutzer, die nicht mehr auf dem Server sind, wurden erfolgreich gelöscht.")

def setupCupid(bot):
    bot.add_cog(Cupid(bot))