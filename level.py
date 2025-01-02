import disnake
from disnake.ext import commands
import sqlite3
import logging
import math
from dbconnection import DatabaseConnection
from globalfile import Globalfile
from rolehierarchy import rolehierarchy
from dotenv import load_dotenv, set_key
import os
import asyncio
import datetime

class Level(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger("Experience")
        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)     
                 
        self.db: sqlite3.Connection = DatabaseConnection()
        self.cursor: sqlite3.Cursor = self.db.connection.cursor()
        self.globalfile = Globalfile(bot)      

        load_dotenv(dotenv_path="envs/settings.env")
        self.factor = int(os.getenv("FACTOR", 100)) # Faktor als Prozentwert
        self.message_worth_per_voicemin = int(os.getenv("MESSAGE_WORTH_PER_VOICEMIN", 1.5))

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS EXPERIENCE (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                MESSAGE INTEGER DEFAULT 0,
                VOICE INTEGER DEFAULT 0,
                LEVEL INTEGER DEFAULT 1
            )
        """)        
        self.db.connection.commit()      

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS VOICE_XP (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                DATE TEXT NOT NULL,
                VOICE INTEGER DEFAULT 0                                
            )
        """)        
        self.db.connection.commit()              
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS MESSAGE_XP (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                DATE TEXT NOT NULL,
                MESSAGE INTEGER DEFAULT 0                                
            )
        """) 
        self.db.connection.commit() 
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS LEVELXP (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                LEVELNAME INTEGER NOT NULL,
                XP TEXT NOT NULL                
            )
        """) 
        self.db.connection.commit() 
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS LEVELXP (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                LEVELNAME INTEGER NOT NULL,
                XP TEXT NOT NULL                
            )
        """) 
        self.db.connection.commit() 
        
        self.last_message_time = {}
        self.voice_check_task = self.bot.loop.create_task(self.check_voice_activity())
   
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(self.create_top_users_view())
                
    async def check_voice_activity(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            current_date = self.globalfile.get_current_time().strftime('%Y-%m-%d')
            for guild in self.bot.guilds:
                for member in guild.members:
                    if member.voice and member.voice.channel:
                        self.cursor.execute("SELECT ID FROM USER WHERE DISCORDID = ?", (member.id,))
                        user_record = self.cursor.fetchone()
                        if user_record:
                            user_id = user_record[0]
                            self.cursor.execute("SELECT * FROM VOICE_XP WHERE USERID = ? AND DATE = ?", (user_id, current_date))
                            result = self.cursor.fetchone()
                            if result:
                                self.cursor.execute("UPDATE VOICE_XP SET VOICE = VOICE + 1 WHERE USERID = ? AND DATE = ?", (user_id, current_date))
                            else:
                                self.cursor.execute("INSERT INTO VOICE_XP (USERID, DATE, VOICE) VALUES (?, ?, 1)", (user_id, current_date))
                            self.db.connection.commit()                        
                            self.cursor.execute("UPDATE EXPERIENCE SET VOICE = VOICE + ? WHERE USERID = ?", (self.message_worth_per_voicemin * self.factor, user_id))
                            self.db.connection.commit()
                            await self.check_level_up(member, user_id)
            await asyncio.sleep(30)

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.bot:
            return
        
        userrecord = self.globalfile.get_user_record(discordid=message.author.id)
        current_datetime = self.globalfile.get_current_time().strftime('%Y-%m-%d %H:%M:%S')
        image_paths = [attachment.url for attachment in message.attachments]
        if len(image_paths) != 0:
            image_path_fields = ", " + ', '.join([f"IMAGEPATH{i+1}" for i in range(len(image_paths))])
            image_path_values = ", " + ', '.join(['?' for _ in range(len(image_paths))])
        else:
            image_path_fields = ""
            image_path_values = ""            
        query = f"INSERT INTO MESSAGE (CONTENT, USERID, CHANNELID, MESSAGEID, INSERT_DATE {image_path_fields}) VALUES (?, ?, ?, ?, ?{image_path_values})"
        self.cursor.execute(query, (message.content, userrecord["ID"], message.channel.id, message.id, current_datetime, *image_paths))
        self.db.connection.commit()

        current_time = self.globalfile.get_current_time()
        last_time = self.last_message_time.get(message.author.id)

        if last_time and (current_time - last_time).total_seconds() < 12:
            return

        self.last_message_time[message.author.id] = current_time

        self.cursor.execute("SELECT ID FROM USER WHERE DISCORDID = ?", (message.author.id,))
        user_record = self.cursor.fetchone()
        if user_record:
            user_id = user_record[0]
            current_date = self.globalfile.get_current_time().strftime('%Y-%m-%d')
            self.cursor.execute("SELECT * FROM MESSAGE_XP WHERE USERID = ? AND DATE = ?", (user_id, current_date))
            result = self.cursor.fetchone()
            if result:
                self.cursor.execute("UPDATE MESSAGE_XP SET MESSAGE = MESSAGE + 1 WHERE USERID = ? AND DATE = ?", (user_id, current_date))
            else:
                self.cursor.execute("INSERT INTO MESSAGE_XP (USERID, DATE, MESSAGE) VALUES (?, ?, 1)", (user_id, current_date))
            self.db.connection.commit()

            self.cursor.execute("UPDATE EXPERIENCE SET MESSAGE = MESSAGE + ? WHERE USERID = ?", (self.factor, user_id))
            self.db.connection.commit()
            await self.check_level_up(message.author, user_id)

    async def check_level_up(self, user, user_id):
        self.cursor.execute("SELECT (MESSAGE + VOICE) AS TOTAL_XP, LEVEL FROM EXPERIENCE WHERE USERID = ?", (user_id,))
        result = self.cursor.fetchone()
        if result:
            total_xp, current_level = result
            new_level = self.calculate_level(total_xp)
            if new_level > current_level:
                self.cursor.execute("UPDATE EXPERIENCE SET LEVEL = ? WHERE USERID = ?", (new_level, user_id))
                self.db.connection.commit()
                await self.send_level_up_message(user, new_level)
                await self.assign_role(user, new_level)

    async def assign_role(self, member: disnake.Member, level):
        # Holen der USERID aus der USER-Tabelle anhand der member.id
        user_record = self.globalfile.get_user_record(discordid=str(member.id))
        if not user_record:
            self.logger.warning(f"USERID für {member.name} ({member.id}) nicht gefunden.")
            return
        user_id = user_record['ID']

        # Finde die neue Rolle basierend auf dem Level
        new_role = None
        while level > 0:
            self.cursor.execute("SELECT ROLE_ID FROM LEVELXP WHERE LEVELNAME = ?", (level,))
            result = self.cursor.fetchone()
            if result and result[0]:
                role_id = result[0]
                new_role = member.guild.get_role(int(role_id))
                if new_role:
                    break
            level -= 1

        if new_role:
            # Überprüfen, ob der Benutzer die neue Rolle bereits hat
            if new_role in member.roles:
                return

            # Entferne alle bestehenden Level-Rollen
            level_roles = []
            for role in member.roles:
                if "level" in role.name.lower():
                    level_roles.append(role)
                else:
                    self.cursor.execute("SELECT 1 FROM LEVELXP WHERE ROLE_ID = ?", (role.id,))
                    if self.cursor.fetchone():
                        level_roles.append(role)
            
            for role in level_roles:
                await member.remove_roles(role)
                self.logger.info(f"Removed role {role.name} from {member.name}")

            # Weisen Sie die neue Rolle zu
            await member.add_roles(new_role)
            self.logger.info(f"Assigned role {new_role.name} to {member.name} for reaching level {level}")
        else:
            self.logger.info(f"No role assigned to {member.name} as no valid role found for their level")
        
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def update_all_users_roles(self, inter: disnake.ApplicationCommandInteraction):
        """Aktualisiert die Rollen aller Benutzer basierend auf ihrem Level in der EXPERIENCE Tabelle."""
        await inter.response.defer()
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.bot:
                    continue

                # Holen der USERID aus der USER-Tabelle anhand der member.id
                user_record = self.globalfile.get_user_record(discordid=str(member.id))
                if not user_record:
                    # Benutzer hat noch kein Level, setze auf Level 1
                    self.cursor.execute("INSERT INTO USER (DISCORDID) VALUES (?)", (str(member.id),))
                    self.db.connection.commit()
                    user_id = self.cursor.lastrowid
                    self.cursor.execute("INSERT INTO EXPERIENCE (USERID, LEVEL) VALUES (?, 1)", (user_id,))
                    self.db.connection.commit()
                    level = 1
                else:
                    user_id = user_record['ID']
                    self.cursor.execute("SELECT LEVEL FROM EXPERIENCE WHERE USERID = ?", (user_id,))
                    result = self.cursor.fetchone()
                    if result:
                        level = result[0]
                    else:
                        # Benutzer hat noch kein Level, setze auf Level 1
                        self.cursor.execute("INSERT INTO EXPERIENCE (USERID, LEVEL) VALUES (?, 1)", (user_id,))
                        self.db.connection.commit()
                        level = 1

                await self.assign_role(member, level)

        await inter.edit_original_response(content="Rollen aller Benutzer wurden erfolgreich aktualisiert.")
                
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def test_assign_role(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, level: int):
        """Testet die Rollenzuweisung für einen bestimmten Benutzer und Level."""
        await self.assign_role(user, level)
        await inter.response.send_message(f"Rolle für {user.mention} basierend auf Level {level} wurde getestet.", ephemeral=True)        

    async def send_level_up_message(self, user: disnake.User, new_level):
        channel = self.bot.get_channel(854698447247769633)  # Replace with your channel ID
        description = (
            f"Herzlichen Glückwunsch {user.mention}!\n"
            f"Du hast Level {new_level} erreicht! 🎉\n"
            f"Vielen Dank für deine Aktivität! 🥳"
        )
        embed = disnake.Embed(title=f"**{user.name} 🔼{new_level}**", description=description, color=disnake.Color.green())
        self.logger.info(f"Level Up Message sent for {user.name} (ID: {user.id}) (Test)")
        embed.set_thumbnail(url=user.avatar.url)
        await channel.send(content=f"{user.mention}", embed=embed)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def calculate_message_xp(self, inter: disnake.ApplicationCommandInteraction):
        """Berechnet die MESSAGE_XP Werte aus der MESSAGE Tabelle."""
        await inter.response.defer()
        cursor = self.db.connection.cursor()

        # Lade das Datum der letzten Ausführung aus der env Datei
        load_dotenv(dotenv_path="envs/settings.env")
        last_run_date = os.getenv("LAST_MESSAGE_XP_CALCULATION")
        if last_run_date:
            last_run_date = datetime.datetime.strptime(last_run_date, '%Y-%m-%d %H:%M:%S')
        else:
            last_run_date = self.globalfile.get_current_time().min

        # Hole alle Nachrichten aus der MESSAGE Tabelle nach dem letzten Ausführungsdatum
        cursor.execute("SELECT USERID, INSERT_DATE FROM MESSAGE WHERE INSERT_DATE > ?", (last_run_date,))
        messages = cursor.fetchall()

        message_xp = {}
        for user_id, insert_date in messages:
            date = insert_date.split(' ')[0]
            if (user_id, date) not in message_xp:
                message_xp[(user_id, date)] = 0
            message_xp[(user_id, date)] += 1

        for (user_id, date), count in message_xp.items():
            cursor.execute("SELECT * FROM MESSAGE_XP WHERE USERID = ? AND DATE = ?", (user_id, date))
            result = cursor.fetchone()
            if result:
                cursor.execute("UPDATE MESSAGE_XP SET MESSAGE = ? WHERE USERID = ? AND DATE = ?", (count, user_id, date))
            else:
                cursor.execute("INSERT INTO MESSAGE_XP (USERID, DATE, MESSAGE) VALUES (?, ?, ?)", (user_id, date, count))
            self.db.connection.commit()

        # Aktualisiere das Datum der letzten Ausführung in der env Datei
        current_time = self.globalfile.get_current_time().strftime('%Y-%m-%d %H:%M:%S')
        set_key("envs/settings.env", "LAST_MESSAGE_XP_CALCULATION", current_time)

        await inter.edit_original_response(content="MESSAGE_XP Werte wurden erfolgreich berechnet und aktualisiert.")

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def set_factor(self, inter: disnake.ApplicationCommandInteraction, value: int):
        """Setzt den Faktor für MESSAGE und VOICE XP."""
        load_dotenv(dotenv_path="envs/settings.env", override=True)
        self.factor = value  # Faktor als Prozentwert
        set_key("envs/settings.env", "FACTOR", str(value))
        
        # Aktualisiere die EXPERIENCE Tabelle
        cursor = self.db.connection.cursor()
        cursor.execute("SELECT USERID FROM EXPERIENCE")
        experience_data = cursor.fetchall()

        for user_id in experience_data:
            user_id = user_id[0]
            cursor.execute("SELECT SUM(MESSAGE) FROM MESSAGE_XP WHERE USERID = ?", (user_id,))
            total_message_xp = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(VOICE) FROM VOICE_XP WHERE USERID = ?", (user_id,))
            total_voice_xp = cursor.fetchone()[0] or 0

            new_message_xp = total_message_xp * self.factor
            new_voice_xp = total_voice_xp * self.message_worth_per_voicemin * self.factor
            cursor.execute("UPDATE EXPERIENCE SET MESSAGE = ?, VOICE = ? WHERE USERID = ?", (new_message_xp, new_voice_xp, user_id))
        self.db.connection.commit()

        await inter.response.send_message(f"Der Faktor wurde auf {value}% gesetzt und die EXPERIENCE Tabelle wurde aktualisiert.", ephemeral=True)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def recalculate_experience(self, inter: disnake.ApplicationCommandInteraction):
        """Berechnet die EXPERIENCE Werte aus der MESSAGE_XP und VOICE_XP Tabelle neu."""
        await inter.response.defer()
        cursor = self.db.connection.cursor()

        cursor.execute("SELECT USERID, SUM(MESSAGE) FROM MESSAGE_XP GROUP BY USERID")
        message_xp_data = cursor.fetchall()

        cursor.execute("SELECT USERID, SUM(VOICE) FROM VOICE_XP GROUP BY USERID")
        voice_xp_data = cursor.fetchall()

        for user_id, total_message_xp in message_xp_data:
            cursor.execute("UPDATE EXPERIENCE SET MESSAGE = ? WHERE USERID = ?", (total_message_xp * self.factor, user_id))
        for user_id, total_voice_xp in voice_xp_data:
            cursor.execute("UPDATE EXPERIENCE SET VOICE = ? WHERE USERID = ?", (total_voice_xp * self.message_worth_per_voicemin * self.factor, user_id))
        self.db.connection.commit()

        await inter.edit_original_response(content="EXPERIENCE Werte wurden erfolgreich neu berechnet.")
        
    @commands.Cog.listener()
    async def on_interaction(self, interaction: disnake.Interaction):
        if interaction.type == disnake.InteractionType.component:
            custom_id = interaction.data.get("custom_id")
            if custom_id in ["sort_by", "time_period"]:
                await self.handle_top_users_interaction(interaction)     
                
    def create_top_users_view(self, sort_by="XP", time_period="total"):
        view = disnake.ui.View(timeout=None)  # Set timeout to None for persistence
        view.add_item(disnake.ui.Select(
            placeholder="Sortieren nach...",
            options=[
                disnake.SelectOption(label="Gesamt XP", value="XP", default=(sort_by == "XP")),
                disnake.SelectOption(label="Message XP", value="MESSAGE_XP", default=(sort_by == "MESSAGE_XP")),
                disnake.SelectOption(label="Voice XP", value="VOICE_XP", default=(sort_by == "VOICE_XP"))
            ],
            custom_id="sort_by"  # Ensure custom_id is set
        ))
        view.add_item(disnake.ui.Select(
            placeholder="Zeitraum...",
            options=[
                disnake.SelectOption(label="Heute", value="today", default=(time_period == "today")),
                disnake.SelectOption(label="Diese Woche", value="week", default=(time_period == "week")),
                disnake.SelectOption(label="Dieser Monat", value="month", default=(time_period == "month")),
                disnake.SelectOption(label="Dieses Jahr", value="year", default=(time_period == "year")),
                disnake.SelectOption(label="Gesamt", value="total", default=(time_period == "total"))
            ],
            custom_id="time_period"  # Ensure custom_id is set
        ))
        return view

    async def handle_top_users_interaction(self, interaction: disnake.Interaction):
        sort_by = "XP"
        time_period = "total"
        if interaction.data["custom_id"] == "sort_by":
            sort_by = interaction.data["values"][0]
        elif interaction.data["custom_id"] == "time_period":
            time_period = interaction.data["values"][0]

        top_users = await self.fetch_top_users(sort_by, time_period)

        # Aktualisiere das Embed
        embed = disnake.Embed(title="Top Benutzer", color=disnake.Color.dark_blue())
        for i, (user_id, message_xp, voice_xp, xp) in enumerate(top_users, start=1):
            cursor = self.db.connection.cursor()
            cursor.execute("SELECT LEVEL FROM EXPERIENCE WHERE USERID = ?", (user_id,))
            level = cursor.fetchone()[0]

            # Hole die Anzahl der Nachrichten und Voice-Minuten
            cursor.execute("SELECT SUM(MESSAGE) FROM MESSAGE_XP WHERE USERID = ?", (user_id,))
            total_message_xp = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(VOICE) FROM VOICE_XP WHERE USERID = ?", (user_id,))
            total_voice_xp = cursor.fetchone()[0] or 0

            try:
                user_record = self.globalfile.get_user_record(user_id=user_id)
                if user_record:
                    discord_id = user_record['DISCORDID']
                    member = interaction.guild.get_member(int(discord_id))
                    if member:
                        embed.add_field(
                            name=f"#{i} {member.name} (Level {level})",
                            value=f"Total: {xp // 10} XP |✍️ {total_message_xp} |🎙️ {total_voice_xp // 2} Min",
                            inline=False
                        )
            except disnake.NotFound:
                continue  # Überspringe Benutzer, die nicht gefunden werden
        await interaction.response.edit_message(embed=embed, view=self.create_top_users_view(sort_by, time_period))    
        
    async def fetch_top_users(self, sort_by: str = "XP", time_period: str = "total"):
        # Bestimme das Zeitfenster
        current_time = self.globalfile.get_current_time()
        if time_period == "today":
            start_date = current_time.strftime('%Y-%m-%d')
        elif time_period == "week":
            start_date = (current_time - datetime.timedelta(days=current_time.weekday())).strftime('%Y-%m-%d')
        elif time_period == "month":
            start_date = current_time.strftime('%Y-%m-01')
        elif time_period == "year":
            start_date = current_time.strftime('%Y-01-01')
        else:
            start_date = None

        # Bestimme die Sortierspalte
        if sort_by == "MESSAGE_XP":
            sort_column = "MESSAGE"
        elif sort_by == "VOICE_XP":
            sort_column = "VOICE"
        elif sort_by == "XP":
            sort_column = "XP"
        else:
            self.logger.error(f"Unkown sort_by value: {sort_by}")

        # Hole die Daten aus der Datenbank
        cursor = self.db.connection.cursor()
        if start_date:
            cursor.execute(f"""
                SELECT USERID, SUM(MESSAGE) AS MESSAGE_XP, SUM(VOICE) AS VOICE_XP, (SUM(MESSAGE) + SUM(VOICE)) AS XP
                FROM EXPERIENCE
                WHERE DATE >= ?
                GROUP BY USERID
                ORDER BY {sort_column} DESC
                LIMIT 10
            """, (start_date,))
        else:
            cursor.execute(f"""
                SELECT USERID, MESSAGE AS MESSAGE_XP, VOICE AS VOICE_XP, (MESSAGE + VOICE) AS XP
                FROM EXPERIENCE
                ORDER BY {sort_column} DESC
                LIMIT 10
            """)
        return cursor.fetchall()        
                
    @commands.slash_command(guild_ids=[854698446996766730])
    async def top_users(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt die Top-Benutzer basierend auf XP, MESSAGE_XP oder VOICE_XP an."""
        await inter.response.defer()

        top_users = await self.fetch_top_users()

        # Erstelle das Embed
        embed = disnake.Embed(title="Top Benutzer", color=disnake.Color.dark_blue())
        for i, (user_id, message_xp, voice_xp, xp) in enumerate(top_users, start=1):
            cursor = self.db.connection.cursor()
            cursor.execute("SELECT LEVEL FROM EXPERIENCE WHERE USERID = ?", (user_id,))
            level = cursor.fetchone()[0]

            # Hole die Anzahl der Nachrichten und Voice-Minuten
            cursor.execute("SELECT SUM(MESSAGE) FROM MESSAGE_XP WHERE USERID = ?", (user_id,))
            total_message_xp = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(VOICE) FROM VOICE_XP WHERE USERID = ?", (user_id,))
            total_voice_xp = cursor.fetchone()[0] or 0

            try:
                user_record = self.globalfile.get_user_record(user_id=user_id)
                if user_record:
                    discord_id = user_record['DISCORDID']
                    member = inter.guild.get_member(int(discord_id))
                    if member:
                        embed.add_field(
                            name=f"#{i} {member.name} (Level {level})",
                            value=f"Total: {xp // 10} XP |✍️ {total_message_xp} |🎙️ {total_voice_xp // 2} Min",
                            inline=False
                        )
            except disnake.NotFound:
                continue  # Überspringe Benutzer, die nicht gefunden werden

        await inter.edit_original_response(embed=embed, view=self.create_top_users_view())

    def calculate_level(self, xp: int) -> int:
        """Berechnet das Level basierend auf den Gesamt-XP."""
        self.cursor.execute("SELECT LEVELNAME FROM LEVELXP WHERE CAST(XP AS INTEGER) > ? ORDER BY CAST(XP AS INTEGER) ASC LIMIT 1", (xp,))        
        result = self.cursor.fetchone()
        return result[0] - 1 if result else 1

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def update_levels(self, inter: disnake.ApplicationCommandInteraction):
        """Aktualisiert die Level aller Benutzer basierend auf ihren Gesamt-XP."""
        await inter.response.defer()
        cursor = self.db.connection.cursor()

        cursor.execute("SELECT USERID, (MESSAGE + VOICE) AS TOTAL_XP FROM EXPERIENCE")
        experience_data = cursor.fetchall()

        for user_id, total_xp in experience_data:
            new_level = self.calculate_level(total_xp)
            cursor.execute("UPDATE EXPERIENCE SET LEVEL = ? WHERE USERID = ?", (new_level, user_id))
        self.db.connection.commit()

        await inter.edit_original_response(content="Level aller Benutzer wurden erfolgreich aktualisiert.")
        
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def test_level_up_message(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, level: int):
        """Testet das Senden einer Level-Up Nachricht."""
        await self.send_level_up_message(user, level)
        await inter.response.send_message(f"Level-Up Nachricht für {user.mention} wurde gesendet.", ephemeral=True)        
    
def setupLevel(bot):
    bot.add_cog(Level(bot))