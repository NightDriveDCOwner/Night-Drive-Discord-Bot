from disnake.ext import commands
from disnake import Embed, ButtonStyle, SelectOption, SelectMenu
from disnake.ui import Select, View, Button
import disnake
import sqlite3
import logging
import asyncio
from globalfile import Globalfile
from rolehierarchy import rolehierarchy
from dbconnection import DatabaseConnectionManager
from dotenv import load_dotenv
import os
from exceptionhandler import exception_handler
from concurrent.futures import ThreadPoolExecutor
import queue
from rolemanager import RoleManager


class Cupid(commands.Cog):
    def __init__(self, bot: commands.Bot, rolemanager: RoleManager):
        self.bot = bot
        self.logger = logging.getLogger("Cupid")
        self.globalfile : Globalfile = self.bot.get_cog('Globalfile')
        # ThreadPoolExecutor for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=50)
        self.running_calculations = {}  # Dictionary to keep track of running calculations
        self.result_queue = queue.Queue()
        self.MALE_ROLE_ID = 1065695971540996317
        self.FEMALE_ROLE_ID = 1065696210771517572
        self.DIVERS_ROLE_ID = 1065696212377927680
        self.DMS_CLOSED_ROLE_ID = 1066800831225147512
        self.rolemanager = rolemanager

        if not self.logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    @commands.Cog.listener()
    async def on_ready(self):        
        self.bot.add_view(self.create_main_view())
        await self.sync_all_dm_status()
        self.logger.info("DatingBot Cog is ready.")

    def create_main_view(self):
        view = View(timeout=None)
        view.add_item(Button(label="Fragen beantworten",
                    style=ButtonStyle.blurple, custom_id="answer_questions"))
        view.add_item(Button(label="Passende User finden",
                    style=ButtonStyle.green, custom_id="find_matches"))
        view.add_item(Button(label="Einstellungen",
                    style=ButtonStyle.gray, custom_id="user_settings"))
        view.add_item(Button(label="Commands anzeigen",
                    style=ButtonStyle.primary, custom_id="show_commands"))  # New Button
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
                "Liebe Grüße\n"
                "Dein Date Night Team\n"                
            ),
            color=disnake.Color.blue()
        )
        embed.set_author(name=f"{inter.guild.name}", icon_url=inter.guild.icon.url)
        embed.set_footer(text="")
        await inter.channel.send(embed=embed, view=self.create_main_view())
        await inter.response.send_message("Embed wurde erfolgreich gesendet.", ephemeral=True)

    @exception_handler
    async def show_commands(self, interaction: disnake.MessageInteraction):
        """Zeigt alle relevanten Commands des Dating Bots an."""
        embed = Embed(
            title="Dating Bot Commands",
            description=(                
                "Folgende Befehle stehen dir im Zusammenhang mit dem Dating Bot zur Verfügung:\n\n"
                "`/my_answers` - Zeigt dir die Fragen an, die du bereits beantwortet hast.\n"
                "`/edit_answer` - Ermöglicht es dir, eine Antwort zu einer Frage zu bearbeiten.\n"
                "`/match_users` - Dort findest du eine Detailierte Ausgabe der Fragenanalyse mit dem angegeben User.\n"
                "`/delete_answers` - Löscht alle Antworten eines Users.\n"
                "`/set_partipation` - Ermöglicht es dir, deine Teilnahme am Dating Bot zu aktivieren oder zu deaktivieren.\n"
                "`/privacy_settings` - Ermöglicht es dir, deine Privatsphäre Einstellungen zu bearbeiten.\n"
                "`/create_intro` - Ermöglicht es dir, eine Vorstellung zu erstellen.\n"
                "`/show_intro` - Zeigt dir deine oder die Vorstellung eines anderen Users an unter Berücksichtigung der Privatsphäre Einstellungen.\n"
            ),
            color=disnake.Color.blue()
        )
        embed.set_footer(text="Bitte beachte, dass die Befehle in jedem Chat funktionieren in dem du auch schreibberechigtigt bist.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @exception_handler
    @commands.Cog.listener()
    async def on_interaction(self, interaction: disnake.MessageInteraction):
        if isinstance(interaction, disnake.MessageInteraction):
            custom_id = interaction.data.custom_id
            if custom_id == "answer_questions":
                self.logger.info(
                    f"User {interaction.user.name} wants to answer questions.")
                await self.show_next_question(interaction)
            elif custom_id == "find_matches":
                await self.find_matches(interaction)
            elif custom_id == "user_settings":
                await self.show_user_settings(interaction)
            elif custom_id == "show_commands":  # New condition
                await self.show_commands(interaction)
            elif custom_id.startswith("gender_"):
                await interaction.response.defer()
                selected_gender = custom_id.split("_")[1]
                userrecord = await self.globalfile.get_user_record(guild=interaction.guild, discordid=interaction.user.id)
                current_preference = await self.get_user_preference(userrecord['ID'], interaction.guild)

                if f",{selected_gender}," in current_preference:
                    new_preference = current_preference.replace(
                        f",{selected_gender},", ",")
                else:
                    new_preference = current_preference + f"{selected_gender},"

                await self.save_user_preference(userrecord['ID'], "preference", new_preference, interaction.guild)
                await self.show_user_settings(interaction, edit=True)

    @exception_handler
    async def show_user_settings(self, interaction: disnake.MessageInteraction, edit=False):
        userrecord = await self.globalfile.get_user_record(guild=interaction.guild, discordid=interaction.user.id)
        current_preference = await self.get_user_preference(userrecord['ID'], interaction.guild)

        if current_preference == ",":
            current_preference = ",male,female,divers,"
            await self.save_user_preference(userrecord['ID'], "preference", current_preference, interaction.guild)

        embed = Embed(
            title="Einstellungen",
            description="Bitte wähle hier die Geschlechter aus, welche du suchst.\n(Grün bedeutet, dass du das Geschlecht suchst, rot bedeutet, dass du das Geschlecht nicht suchst.)",
            color=disnake.Color.blue()
        )
        embed.set_footer(
            text="Deine Auswahl bleibt anonym und ist allein fürs Team einsehbar.")

        view = View(timeout=None)
        view.add_item(Button(
            label="Männer", style=ButtonStyle.green if ",male," in current_preference else ButtonStyle.red, custom_id="gender_male"))
        view.add_item(Button(
            label="Frauen", style=ButtonStyle.green if ",female," in current_preference else ButtonStyle.red, custom_id="gender_female"))
        view.add_item(Button(
            label="Divers", style=ButtonStyle.green if ",divers," in current_preference else ButtonStyle.red, custom_id="gender_divers"))

        if edit:
            await interaction.edit_original_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @exception_handler
    async def show_next_question(self, interaction: disnake.MessageInteraction, edit=False):
        user_record = await self.globalfile.get_user_record(guild=interaction.guild, discordid=str(interaction.user.id))
        user_id = user_record['ID']

        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "SELECT COUNT(*) FROM ANSWER WHERE USERID = ?", (user_id,))
        answered_count = (await cursor.fetchone())[0]

        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name,"SELECT COUNT(*) FROM QUESTION")
        total_questions = (await cursor.fetchone())[0]

        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, """
            SELECT q.ID, q.QUESTION 
            FROM QUESTION q 
            LEFT JOIN ANSWER a ON q.ID = a.QUESTIONID AND a.USERID = ? 
            WHERE a.QUESTIONID IS NULL 
            LIMIT 1
        """, (user_id,))
        question = (await cursor.fetchone())

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
        view.add_item(Button(label="Eher nicht", style=ButtonStyle.red,
                      custom_id=f"answer_{question_id}_no"))
        view.add_item(Button(label="Neutral", style=ButtonStyle.gray,
                      custom_id=f"answer_{question_id}_neutral"))
        view.add_item(Button(label="Eher ja", style=ButtonStyle.green,
                      custom_id=f"answer_{question_id}_yes"))
        return view

    @exception_handler
    @commands.Cog.listener()
    async def on_button_click(self, interaction: disnake.MessageInteraction):
        custom_id = interaction.component.custom_id
        if custom_id.startswith("answer_"):
            parts = custom_id.split("_")
            if len(parts) == 3:
                await interaction.response.defer(ephemeral=True)
                _, question_id, answer = parts
                await self.save_answer(interaction.user.id, int(question_id), answer, interaction)
                await self.handle_answer(interaction, question_id)

    @exception_handler
    async def save_answer(self, user_id, question_id, answer, interaction: disnake.MessageInteraction = None):
        user_record = await self.globalfile.get_user_record(guild=interaction.guild, discordid=str(user_id))
        if user_record:
            user_id = user_record['ID']
            await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, """
                INSERT INTO ANSWER (USERID, QUESTIONID, ANSWER)
                VALUES (?, ?, ?)
                ON CONFLICT(USERID, QUESTIONID) DO UPDATE SET ANSWER=excluded.ANSWER
            """, (user_id, question_id, answer))

    @exception_handler
    async def handle_answer(self, interaction: disnake.MessageInteraction, question_id):
        try:
            embed = interaction.message.embeds[0]
            embed.add_field(
                name="Status", value="Frage erfolgreich beantwortet. ✅", inline=False)
            await interaction.edit_original_message(embed=embed, view=None)
            await asyncio.sleep(1.5)
            await self.show_next_question(interaction, edit=True)
        except disnake.errors.NotFound:
            self.logger.error("Interaction not found or already responded to.")
        except Exception as e:
            self.logger.error(f"An error occurred in handle_answer: {e}")
            await interaction.followup.send("Ein Fehler ist aufgetreten. Bitte versuche es später erneut oder öffne ein Ticket.", ephemeral=True)

    @exception_handler
    async def find_matches(self, interaction: disnake.MessageInteraction):
        await interaction.response.defer()
        user_id = (await self.globalfile.get_user_record(guild=interaction.guild, discordid=interaction.user.id))['ID']
        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'preference'", (user_id,))	
        user_preference = (await cursor.fetchone())
        if user_preference is None:
            await interaction.followup.send("Du hast noch keine Präferenzen gesetzt. Mache das bitte über den ""Einstellungs""-Button. Bitte beachte beim Einstellen die Beschreibung.", ephemeral=True)
            return
        user_id = interaction.user.id
        # Mark the calculation as running
        if user_id in self.running_calculations:
            await interaction.followup.send("Die Berechnungen laufen bereits.", ephemeral=True)
            return
        self.running_calculations[user_id] = True
        try:
            self.logger.info(
                f"User {interaction.user.name} wants to find matches.")
            member = await interaction.guild.fetch_member(user_id)

            if member is None:
                await interaction.followup.send("Du bist nicht mehr auf dem Server. Bitte trete dem Server erneut bei, um fortzufahren.", ephemeral=True)
                del self.running_calculations[user_id]
                return

            userrecord = await self.globalfile.get_user_record(guild=interaction.guild, discordid=user_id)
            user_db_id = userrecord['ID']
            dmstatus = await self.get_user_dmstatus(user_db_id, interaction.guild)
            user_sex = await self.get_user_sex(user_db_id, interaction.guild)

            if "close" == dmstatus:
                await interaction.followup.send("Du hast die Rolle 'DMs Geschlossen'. Bitte entferne diese Rolle, um fortzufahren.", ephemeral=True)
                del self.running_calculations[user_id]
                return

            await self.update_user_sex(user_db_id, user_sex, interaction.guild)
            user_answers = await self.get_user_answers(user_db_id, interaction.guild)

            if not user_answers:
                await interaction.followup.send("Du hast noch keine Fragen beantwortet.", ephemeral=True)
                del self.running_calculations[user_id]
                return

            total_questions = await self.get_total_questions(interaction.guild)

            if len(user_answers) < total_questions:
                await interaction.followup.send("Du hast noch nicht alle Fragen beantwortet.", ephemeral=True)
                del self.running_calculations[user_id]
                return

            user_preference = await self.get_user_preference(user_db_id, interaction.guild)
            if not user_preference:
                await interaction.followup.send("Du hast noch keine Präferenzen gesetzt. Mache das bitte über den ""Einstellungs""-Button", ephemeral=True)
                del self.running_calculations[user_id]
                return

            embed = Embed(
                title="Berechnungen laufen",
                description="Die Berechnungen laufen und es kann ein paar Minuten dauern. Bitte gedulde dich.",
                color=disnake.Color.orange()
            )
            sent_message: disnake.WebhookMessage = await interaction.followup.send(embed=embed, ephemeral=True)
            message_id = sent_message.id

            # Run the calculation in a separate thread
            self.executor.submit(self.calculate_matches, interaction, user_db_id,
                                 user_answers, total_questions, user_preference, message_id)

            # Process results directly after calculation
            await self.process_results()
        except Exception as e:
            self.logger.critical(f"An error occurred: {e}")
            del self.running_calculations[user_id]

    @exception_handler
    async def update_user_sex(self, user_db_id, user_sex, guild: disnake.Guild):
        await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, """
            INSERT INTO USER_SETTINGS (USERID, SETTING, VALUE)
            VALUES (?, 'sex', ?)
            ON CONFLICT(USERID, SETTING) DO UPDATE SET VALUE = excluded.VALUE
        """, (user_db_id, user_sex))

    async def get_user_dmstatus(self, db_user_id, guild: disnake.Guild):
        cursor = await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, "SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'dmstatus'", (db_user_id,))
        result = (await cursor.fetchone())
        return result[0] if result else None

    @exception_handler
    async def get_user_sex(self, db_user_id, guild: disnake.Guild):
        cursor = await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, "SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'sex'", (db_user_id,))
        result = (await cursor.fetchone())
        return result[0] if result else None

    @exception_handler
    async def get_user_answers(self, user_db_id, guild: disnake.Guild):
        cursor = await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, "SELECT QUESTIONID, ANSWER FROM ANSWER WHERE USERID = ?", (user_db_id,))
        return await cursor.fetchall()

    @exception_handler
    async def get_total_questions(self, guild: disnake.Guild):
        cursor = await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, "SELECT COUNT(*) FROM QUESTION")
        return (await cursor.fetchone())[0]

    @exception_handler
    async def get_user_preference(self, user_db_id, guild: disnake.Guild):
        cursor = await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, "SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'preference'", (user_db_id,))
        result = (await cursor.fetchone())
        return result[0] if result else ","

    def calculate_matches(self, interaction, user_db_id, user_answers, total_questions, user_preference, message_id):
        asyncio.run_coroutine_threadsafe(
            self._calculate_matches(
                interaction, user_db_id, user_answers, total_questions, user_preference, message_id),
            self.bot.loop
        )

    @exception_handler
    async def _calculate_matches(self, interaction: disnake.MessageInteraction, user_db_id, user_answers, total_questions, user_preference, message_id):
        try:
            matches = {}
            user_sex = await self.get_user_sex(user_db_id, interaction.guild)

            # Get all answers for all users for the questions the current user answered
            question_ids = [question_id for question_id, _ in user_answers]
            cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, """
                SELECT USERID, QUESTIONID, ANSWER 
                FROM ANSWER 
                WHERE QUESTIONID IN ({}) 
                AND USERID IN (
                    SELECT USERID 
                    FROM ANSWER 
                    GROUP BY USERID 
                    HAVING COUNT(DISTINCT QUESTIONID) = (SELECT COUNT(*) FROM QUESTION)
                )
            """.format(','.join('?' * len(question_ids))), question_ids)
            all_answers = await cursor.fetchall()
            # Group answers by user
            answers_by_user = {}
            for match_user_id, question_id, match_answer in all_answers:
                if match_user_id == user_db_id:
                    continue
                if match_user_id not in answers_by_user:
                    answers_by_user[match_user_id] = {}
                answers_by_user[match_user_id][question_id] = match_answer

            for match_user_id, match_answers in answers_by_user.items():
                cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'preference'", (match_user_id,))
                match_preference = (await cursor.fetchone())
                if not match_preference or not any(f",{user_sex}," in match_preference[0] for user_sex in ["male", "female", "divers"]):
                    continue

                cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'participation'", (match_user_id,))
                participation = (await cursor.fetchone())
                if participation and participation[0] == "no":
                    continue

                match_user_record = await self.globalfile.get_user_record(guild=interaction.guild, user_id=match_user_id)
                if not match_user_record:
                    continue

                match_discord_id = match_user_record['DISCORDID']
                try:
                    match_member = await interaction.guild.fetch_member(int(match_discord_id))
                except Exception:
                    continue

                if not match_member:
                    continue

                dmstatus = await self.get_user_dmstatus(match_user_record['ID'], interaction.guild)
                if dmstatus == "close":
                    continue

                matches_sex = await self.get_user_sex(match_user_record['ID'], interaction.guild)
                if f",{matches_sex}," not in user_preference:
                    continue

                score = matches.get(match_user_id, 0)
                for question_id, user_answer in user_answers:
                    match_answer = match_answers.get(question_id)
                    if match_answer is None:
                        continue
                    if user_answer == match_answer:
                        score += 2
                    elif (user_answer == "neutral" and match_answer in ["yes", "no"]) or (match_answer == "neutral" and user_answer in ["yes", "no"]):
                        score += 1
                    elif (user_answer == "yes" and match_answer == "no") or (user_answer == "no" and match_answer == "yes"):
                        score += 0
                matches[match_user_id] = score

            self.logger.debug(
                f"User {user_db_id}: {len(matches)} matches found.")
            matches = {k: (v / (total_questions * 2)) *
                    100 for k, v in matches.items()}
            sorted_matches = sorted(
                matches.items(), key=lambda x: x[1], reverse=True)[:10]
            match_list = "\n".join([f"<@{(await self.globalfile.get_user_record(guild=interaction.guild, user_id=match_id))['DISCORDID']}>: {score:.2f}% übereinstimmende Antworten" for match_id, score in sorted_matches])

            embed = Embed(
                title="Top 10 Passende User",
                description=match_list if match_list else "Keine passenden User gefunden.",
                color=disnake.Color.green()
            )
            self.result_queue.put((interaction, message_id, embed))
        finally:
            del self.running_calculations[interaction.user.id]
            await self.process_results()

    async def process_results(self):
        while not self.result_queue.empty():
            try:
                interaction: disnake.MessageInteraction
                interaction, message_id, embed = self.result_queue.get()
                try:
                    await interaction.followup.send(content=f"||{interaction.user.mention}||", embed=embed, ephemeral=True)
                except disnake.HTTPException as e:
                    if e.code == 50027:  # Invalid Webhook Token
                        self.logger.error(f"Invalid Webhook Token: {e}")
                        await interaction.followup.send(embed=embed)
                    else:
                        raise e
                except disnake.errors.NotFound:
                    await interaction.followup.send(embed=embed)
                finally:
                    self.result_queue.task_done()
            except Exception as e:
                self.logger.error(f"Error in process_results: {e}")
            await asyncio.sleep(1)

    async def running_calculations(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt die Benutzer, für die die Berechnungen noch laufen."""
        running_users = [
            f"<@{user_id}>" for user_id in self.running_calculations.keys()]
        description = "\n".join(
            running_users) if running_users else "Keine laufenden Berechnungen."
        embed = Embed(
            title="Laufende Berechnungen",
            description=description,
            color=disnake.Color.blue()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)

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

            userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
            user_id = userrecord['ID']

            # Update user's sex in the database
            cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, """
                INSERT INTO USER_SETTINGS (USERID, SETTING, VALUE)
                VALUES (?, 'sex', ?)
                ON CONFLICT(USERID, SETTING) DO UPDATE SET VALUE = excluded.VALUE
            """, (user_id, user_sex))

            cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT QUESTIONID, ANSWER FROM ANSWER WHERE USERID = ?", (user_id,))
            user_answers = await cursor.fetchall()
            if not user_answers:
                await inter.followup.send("Du hast noch keine Fragen beantwortet.", ephemeral=True)
                return

            cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT COUNT(*) FROM QUESTION")
            total_questions = (await cursor.fetchone())[0]

            if len(user_answers) < total_questions:
                await inter.followup.send("Du hast noch nicht alle Fragen beantwortet.", ephemeral=True)
                return

            cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'preference'", (user_id,))
            user_preference = (await cursor.fetchone())
            if not user_preference:
                await inter.followup.send("Du hast noch keine Präferenzen gesetzt. Mache das bitte über den ""Einstellungs""-Button", ephemeral=True)
                return
            user_preference = user_preference[0]

            matches = {}
            match_details = {}
            for question_id, user_answer in user_answers:
                cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT USERID, ANSWER FROM ANSWER WHERE QUESTIONID = ?", (question_id,))
                matching_users = await cursor.fetchall()
                for match in matching_users:
                    match_user_id, match_answer = match
                    if match_user_id == user_id:
                        continue

                    cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'preference'", (match_user_id,))
                    match_preference = (await cursor.fetchone())
                    if not match_preference or match_preference[0] != user_sex:
                        continue

                    match_user_record = await self.globalfile.get_user_record(guild=inter.guild, user_id=match_user_id)
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
                        match_details.setdefault(
                            match_user_id, {"+2": 0, "+1": 0, "+0": 0})["+2"] += 1
                        self.logger.debug(
                            f"User {match_user_id}: +2 Punkte für gleiche Antwort bei Frage {question_id}")
                    elif (user_answer == "neutral" and match_answer in ["yes", "no"]) or (match_answer == "neutral" and user_answer in ["yes", "no"]):
                        score += 1
                        match_details.setdefault(
                            match_user_id, {"+2": 0, "+1": 0, "+0": 0})["+1"] += 1
                        self.logger.debug(
                            f"User {match_user_id}: +1 Punkt für neutrale Antwort bei Frage {question_id}")
                    elif (user_answer == "yes" and match_answer == "no") or (user_answer == "no" and match_answer == "yes"):
                        score += 0
                        match_details.setdefault(
                            match_user_id, {"+2": 0, "+1": 0, "+0": 0})["+0"] += 1
                        self.logger.debug(
                            f"User {match_user_id}: +0 Punkte für unterschiedliche Antwort bei Frage {question_id}")
                    matches[match_user_id] = score

            matches = {k: (v / (total_questions * 2)) *
                       100 for k, v in matches.items()}

            sorted_matches = sorted(
                matches.items(), key=lambda x: x[1], reverse=True)[:10]
            match_list = "\n".join([f"<@{await self.globalfile.get_user_record(guild=inter.guild, user_id=match_id)['DISCORDID']}>: {score:.2f}% übereinstimmende Antworten" for match_id, score in sorted_matches])

            for match_id, score in sorted_matches:
                self.logger.debug(
                    f"User {match_id}: {score:.2f}% übereinstimmende Antworten")

            embed = Embed(
                title="Top 10 Passende User",
                description=match_list if match_list else "Keine passenden User gefunden.",
                color=disnake.Color.green()
            )
            await inter.followup.send(embed=embed, ephemeral=True)

            # Create a debug embed for the first match
            if sorted_matches:
                top_match_id, top_match_score = sorted_matches[0]
                top_match_details = match_details.get(
                    top_match_id, {"+2": 0, "+1": 0, "+0": 0})
                debug_embed = Embed(
                    title="Debug Informationen für den Top-Match",
                    description=f"User: <@{await self.globalfile.get_user_record(guild=inter.guild, user_id=top_match_id)['DISCORDID']}>",
                    color=disnake.Color.blue()
                )
                debug_embed.add_field(
                    name="+2 Punkte", value=str(top_match_details["+2"]), inline=True)
                debug_embed.add_field(
                    name="+1 Punkt", value=str(top_match_details["+1"]), inline=True)
                debug_embed.add_field(
                    name="+0 Punkte", value=str(top_match_details["+0"]), inline=True)
                await inter.followup.send(embed=debug_embed, ephemeral=True)
        except Exception as e:
            self.logger.critical(f"An error occurred: {e}")

    @exception_handler
    async def save_user_preference(self, user_id, setting, value, guild: disnake.Guild):
        try:
            cursor = await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, """
                SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = ?
            """, (user_id, setting))
            existing_value = (await cursor.fetchone())

            if existing_value:
                await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, """
                    UPDATE USER_SETTINGS SET VALUE = ? WHERE USERID = ? AND SETTING = ?
                """, (value, user_id, setting))
            else:
                await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, """
                    INSERT INTO USER_SETTINGS (USERID, SETTING, VALUE)
                    VALUES (?, ?, ?)
                """, (user_id, setting, value))
        except Exception as e:
            self.logger.critical(f"An error occurred: {e}")
            member = await guild.fetch_member(461969832074543105)
            await member.send(f"An error occurred: {e} in {setting} for user {user_id}")

    @exception_handler
    async def _recalculate_invite_xp(self, inter: disnake.ApplicationCommandInteraction):
        """Berechnet die INVITEXP Werte aus der INVITE_XP Tabelle neu."""
        await inter.response.defer()

        # Lade den Faktor aus der env Datei
        load_dotenv(dotenv_path="envs/settings.env", override=True)
        factor = int(os.getenv("FACTOR", 50))

        # Hole alle Einträge aus der INVITE_XP-Tabelle
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT USERID, SUM(COUNT) FROM INVITE_XP GROUP BY USERID")
        invite_xp_data = await cursor.fetchall()
        for user_id, total_invite_count in invite_xp_data:
            invite_xp = total_invite_count * factor
            await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "UPDATE EXPERIENCE SET INVITE = ? WHERE USERID = ?", (invite_xp, user_id))

        await inter.edit_original_response(content="INVITEXP Werte wurden erfolgreich neu berechnet.")

    @exception_handler
    async def _deletedata_for_nonexistent_user(self, inter: disnake.ApplicationCommandInteraction):
        # Hole alle Benutzer-IDs aus der ANSWER-Tabelle
        await inter.response.defer()

        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT DISTINCT USERID FROM ANSWER")
        answer_user_ids = [row[0] for row in cursor.fetchall()]

        # Hole alle Benutzer-IDs aus der USER_SETTINGS-Tabelle
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT DISTINCT USERID FROM USER_SETTINGS")
        settings_user_ids = [row[0] for row in cursor.fetchall()]

        # Kombiniere alle Benutzer-IDs
        all_user_ids = set(answer_user_ids + settings_user_ids)

        # Überprüfe, ob die Benutzer noch auf dem Server sind
        for user_id in all_user_ids:
            user_record = await self.globalfile.get_user_record(guild=inter.guild, user_id=user_id)
            if user_record:
                discord_id = user_record['DISCORDID']
                member = inter.guild.get_member(int(discord_id))
                if not member:
                    # Lösche die Daten des Benutzers, wenn er nicht mehr auf dem Server ist
                    cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "DELETE FROM ANSWER WHERE USERID = ?", (int(user_id),))
                    cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "DELETE FROM USER_SETTINGS WHERE USERID = ?", (int(user_id),))
                    self.logger.debug(
                        f"Deleted data for user ID {user_id} who is no longer on the server.")

        await inter.edit_original_response(content="Daten für Benutzer, die nicht mehr auf dem Server sind, wurden erfolgreich gelöscht.")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.roles != after.roles:
            await self.update_dm_status(after)

    async def sync_all_dm_status(self):
        for guild in self.bot.guilds:
            await self.sync_dm_status(guild)

    async def sync_dm_status(self, guild: disnake.Guild):
        # Replace with your guild ID    
        for member in guild.members:
            await self.update_dm_status(member)

    async def update_dm_status(self, member: disnake.Member):
        if self.DMS_CLOSED_ROLE_ID in [role.id for role in member.roles]:
            dm_status = "close"
        else:
            dm_status = "open"

        if self.MALE_ROLE_ID in [role.id for role in member.roles]:
            gender = "male"
        elif self.FEMALE_ROLE_ID in [role.id for role in member.roles]:
            gender = "female"
        elif self.DIVERS_ROLE_ID in [role.id for role in member.roles]:
            gender = "divers"
        else:
            gender = None

        user_record = await self.globalfile.get_user_record(guild=member.guild, discordid=member.id)
        if user_record:
            user_db_id = user_record['ID']
            cursor = await DatabaseConnectionManager.execute_sql_statement(member.guild.id, member.guild.name, "SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'dmstatus' AND VALUE = ?", (user_db_id, dm_status))
            if not (await cursor.fetchone()):
                await self.save_user_preference(user_db_id, 'dmstatus', dm_status, member.guild)

            if gender:
                cursor = await DatabaseConnectionManager.execute_sql_statement(member.guild.id, member.guild.name, "SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'sex' AND VALUE = ?", (user_db_id, gender))
                if not (await cursor.fetchone()):
                    await self.save_user_preference(user_db_id, 'sex', gender, member.guild)

    @commands.Cog.listener()
    async def _my_answers(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt die Antworten des Benutzers an."""
        await inter.response.defer(ephemeral=True)

        user_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
        user_id = user_record['ID']

        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, """
            SELECT q.QUESTION, a.ANSWER 
            FROM ANSWER a 
            LEFT JOIN QUESTION q ON a.QUESTIONID = q.ID 
            WHERE a.USERID = ?
        """, (user_id,))
        answers = await cursor.fetchall()

        if not answers:
            await inter.edit_original_response(content="Du hast noch keine Fragen beantwortet.")
            return

        # Pagination variables
        items_per_page = 10
        total_pages = (len(answers) + items_per_page - 1) // items_per_page

        async def send_page(page):
            start = page * items_per_page
            end = start + items_per_page
            embed = Embed(
                title="Deine Antworten",                
                color=disnake.Color.green()
            )
            for question, answer in answers[start:end]:
                embed.add_field(name=f"Frage {answers.index((question, answer)) + 1}", value=f"**Frage:** {question}\n**Antwort:** {answer}", inline=False)
            view = View()
            if page > 0:
                view.add_item(Button(label="◀️", style=ButtonStyle.blurple, custom_id=f"prev_{page}"))
            if page < total_pages - 1:
                view.add_item(Button(label="▶️", style=ButtonStyle.blurple, custom_id=f"next_{page}"))
            await inter.edit_original_response(embed=embed, view=view)

        await send_page(0)
        self.logger.info(f"User {inter.user.name} has requested their answers.")

        @self.bot.event
        async def on_button_click(interaction: disnake.MessageInteraction):
            await interaction.response.defer()
            if interaction.component.custom_id.startswith("prev_"):
                page = int(interaction.component.custom_id.split("_")[1])
                await send_page(page - 1)
            elif interaction.component.custom_id.startswith("next_"):
                page = int(interaction.component.custom_id.split("_")[1])
                await send_page(page + 1)
            interaction.response.is_done()

    async def _edit_answer(self, inter: disnake.ApplicationCommandInteraction, question_id: int, value: str):
        user_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
        user_id = user_record['ID']

        # Map the value to the corresponding database value
        value_map = {
            "Eher nicht": "no",
            "Neutral": "neutral",
            "Eher ja": "yes"
        }
        db_value = value_map.get(value, "neutral")  # Default to "neutral" if value is not recognized

        await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, """
            INSERT INTO ANSWER (USERID, QUESTIONID, ANSWER)
            VALUES (?, ?, ?)
            ON CONFLICT(USERID, QUESTIONID) DO UPDATE SET ANSWER = excluded.ANSWER
        """, (user_id, question_id, db_value))

        self.logger.info(f"User {inter.user.name} has updated their answer for question {question_id} to {db_value}.")
        await inter.edit_original_response(content="Antwort erfolgreich aktualisiert.")

    async def _match_users(self, inter: disnake.ApplicationCommandInteraction, matchuser: disnake.Member):
        userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
        user_db_id = userrecord['ID']
        matchuserrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=matchuser.id)
        matchuser_db_id = matchuserrecord['ID']

        user_answers = await self.get_user_answers(user_db_id, inter.guild)
        matchuser_answers = await self.get_user_answers(matchuser_db_id, inter.guild)

        if not user_answers or not matchuser_answers:
            await inter.response.send_message("Einer der Benutzer hat noch keine Fragen beantwortet.", ephemeral=True)
            return

        total_questions = await self.get_total_questions(inter.guild)

        # Berechnung der Übereinstimmung
        score = 0
        match_details = {"+2": 0, "+1": 0, "+0": 0}
        for question_id, user_answer in user_answers:
            match_answer = next((answer for q_id, answer in matchuser_answers if q_id == question_id), None)
            if match_answer is not None:
                if user_answer == match_answer:
                    score += 2
                    match_details["+2"] += 1
                elif (user_answer == "neutral" and match_answer in ["yes", "no"]) or (match_answer == "neutral" and user_answer in ["yes", "no"]):
                    score += 1
                    match_details["+1"] += 1
                elif (user_answer == "yes" and match_answer == "no") or (user_answer == "no" and match_answer == "yes"):
                    score += 0
                    match_details["+0"] += 1

        match_percentage = (score / (total_questions * 2)) * 100

        # Anzeige der Fragen und Antworten
        items_per_page = 10
        total_pages = (len(user_answers) + items_per_page - 1) // items_per_page

        async def send_page(page):
            start = page * items_per_page
            end = start + items_per_page
            embed = Embed(
                title=f"Vergleich der Antworten von {inter.user.name} und {matchuser.name}",
                color=disnake.Color.blue()
            )
            for question_id, user_answer in user_answers[start:end]:
                match_answer = next((answer for q_id, answer in matchuser_answers if q_id == question_id), "Nicht beantwortet")
                cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT QUESTION FROM QUESTION WHERE ID = ?", (question_id,))
                question_text = (await cursor.fetchone())[0]
                embed.add_field(name=f"Frage: {question_text}", value=f"{inter.user.name}: {user_answer}\n{matchuser.name}: {match_answer}", inline=False)

            view = View()
            if page > 0:
                view.add_item(Button(label="◀️", style=ButtonStyle.blurple, custom_id=f"prev_{page}"))
            if page < total_pages - 1:
                view.add_item(Button(label="▶️", style=ButtonStyle.blurple, custom_id=f"next_{page}"))
            view.add_item(Button(label="Ergebnis", style=ButtonStyle.green, custom_id="show_match_result"))

            await inter.edit_original_response(embed=embed, view=view)

        await inter.response.send_message(embed=Embed(title="Lade..."), ephemeral=True)
        await send_page(0)

        @self.bot.event
        async def on_button_click(interaction: disnake.MessageInteraction):
            await interaction.response.defer()
            if interaction.component.custom_id.startswith("prev_"):
                page = int(interaction.component.custom_id.split("_")[1])
                await send_page(page - 1)
            elif interaction.component.custom_id.startswith("next_"):
                page = int(interaction.component.custom_id.split("_")[1])
                await send_page(page + 1)
            elif interaction.component.custom_id == "show_match_result":
                result_embed = Embed(
                    title="Ergebnis der Übereinstimmung",
                    description=f"Übereinstimmung: {match_percentage:.2f}%\n\n"
                                f"+2 Punkte: {match_details['+2']}\n"
                                f"+1 Punkt: {match_details['+1']}\n"
                                f"+0 Punkte: {match_details['+0']}",
                    color=disnake.Color.green()
                )
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=result_embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=result_embed, ephemeral=True)

    @exception_handler
    async def save_user_participation(self, user, value, guild: disnake.Guild):
        if value == "Ja/Aktiviert":
            value = "yes"
        elif value == "Nein/Deaktiviert":
            value = "no"
        
        user_id = (await self.globalfile.get_user_record(guild=guild, discordid=user.id))['ID']
        cursor = await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, """
            SELECT VALUE FROM USER_SETTINGS WHERE USERID = ? AND SETTING = 'participation'
        """, (user_id,))
        existing_value = (await cursor.fetchone())

        if existing_value:
            await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, """
                UPDATE USER_SETTINGS SET VALUE = ? WHERE USERID = ? AND SETTING = 'participation'
            """, (value, user_id))
        else:
            await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, """
                INSERT INTO USER_SETTINGS (USERID, SETTING, VALUE)
                VALUES (?, 'participation', ?)
            """, (user_id, value))

    async def _set_user_participation(self, inter: disnake.ApplicationCommandInteraction, value: str):
        await self.save_user_participation(inter.user, value, inter.guild)
        await inter.response.send_message(f"Teilnahme-Status für {inter.user.mention} erfolgreich auf {value} gesetzt.", ephemeral=True)
    
    async def _delete_answers(self, inter: disnake.MessageInteraction, guild: disnake.Guild):
        await inter.response.defer(ephemeral=True)
        user_id = (await self.globalfile.get_user_record(guild=guild, discordid=inter.user.id))['ID']
        await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, "DELETE FROM ANSWER WHERE USERID = ?", (user_id,))
        await inter.edit_original_message("Deine Antworten wurden erfolgreich gelöscht.")

def setupCupid(bot: commands.Bot, rolemanager: RoleManager):
    bot.add_cog(Cupid(bot, rolemanager))
