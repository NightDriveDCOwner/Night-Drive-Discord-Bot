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
from exceptionhandler import exception_handler


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
        self.message_worth_per_voicemin = float(os.getenv("MESSAGE_WORTH_PER_VOICEMIN", 0.5))

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS EXPERIENCE (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                MESSAGE INTEGER DEFAULT 0,
                VOICE INTEGER DEFAULT 0,
                LEVEL INTEGER DEFAULT 1,
                INVITE INTEGER DEFAULT 0 
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
            CREATE TABLE IF NOT EXISTS BONUS_XP (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                REASON TEXT NOT NULL,
                INSERT_DATE TEXT NOT NULL,
                ORIGINAL_XP INTEGER NOT NULL,
                CALCULATED_XP INTEGER NOT NULL
            )
        """)         
        self.db.connection.commit() 
        
        self.last_message_time = {}
        self.voice_check_task = self.bot.loop.create_task(self.check_voice_activity())
   
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(await self.create_top_users_view())

    @exception_handler                
    async def check_voice_activity(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            current_date = (await self.globalfile.get_current_time()).strftime('%Y-%m-%d')
            for guild in self.bot.guilds:
                for member in guild.members:
                    if member.voice and member.voice.channel and not member.voice.afk and not member.voice.self_mute:
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
                            
                            # Überprüfen, ob die Person die Zweitaccount-Rolle hat
                            second_account_role_id = 1329202926916472902  # Ersetze dies durch die tatsächliche ID der Zweitaccount-Rolle
                            if second_account_role_id not in [role.id for role in member.roles]:
                                self.cursor.execute("UPDATE EXPERIENCE SET VOICE = VOICE + ? WHERE USERID = ?", (self.message_worth_per_voicemin * self.factor, user_id))
                                self.db.connection.commit() 
                                await self.check_level_up(member, user_id)
            await asyncio.sleep(30)

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.bot:
            if message.author.id == 302050872383242240:  # Replace with the actual bot ID
                if "has bumped the server!" in message.content:  # Adjust this to match the actual message content
                    bumper_id = message.mentions[0].id  # Assuming the user who bumped is mentioned in the message
                    self.logger.info(f"User {bumper_id} has bumped the server.")
                    # Save the bumper_id to your database or perform any other action you need        
            return

        userrecord = await self.globalfile.get_user_record(discordid=message.author.id)
        if not userrecord:
            self.logger.warning(f"User record not found for {message.author.id}")
            return

        current_datetime = ((await self.globalfile.get_current_time())).strftime('%Y-%m-%d %H:%M:%S')
        image_paths = []

        for attachment in message.attachments:
            image_path = await self.globalfile.save_image(attachment, f"{message.author.id}")
            if image_path:
                image_paths.append(image_path)

        if image_paths:
            # Ensure IMAGEPATH columns exist
            for i in range(1, len(image_paths) + 1):
                column_name = f"IMAGEPATH{i}"
                self.cursor.execute(f"PRAGMA table_info(MESSAGE)")
                columns = [info[1] for info in self.cursor.fetchall()]
                if column_name not in columns:
                    self.cursor.execute(f"ALTER TABLE MESSAGE ADD COLUMN {column_name} TEXT")
            self.db.connection.commit()

            image_path_fields = ", " + ', '.join([f"IMAGEPATH{i+1}" for i in range(len(image_paths))])
            image_path_values = ", " + ', '.join(['?' for _ in range(len(image_paths))])
        else:
            image_path_fields = ""
            image_path_values = ""

        query = f"INSERT INTO MESSAGE (CONTENT, USERID, CHANNELID, MESSAGEID, INSERT_DATE {image_path_fields}) VALUES (?, ?, ?, ?, ?{image_path_values})"
        self.cursor.execute(query, (message.content, userrecord["ID"], message.channel.id, message.id, current_datetime, *image_paths))
        self.db.connection.commit()

        current_time = (await self.globalfile.get_current_time())
        last_time = self.last_message_time.get(message.author.id)

        if last_time and (current_time - last_time).total_seconds() < 12:
            return

        self.last_message_time[message.author.id] = current_time

        self.cursor.execute("SELECT ID FROM USER WHERE DISCORDID = ?", (message.author.id,))
        user_record = self.cursor.fetchone()
        if user_record:
            user_id = user_record[0]
            current_date = (await self.globalfile.get_current_time()).strftime('%Y-%m-%d')
            self.cursor.execute("SELECT * FROM MESSAGE_XP WHERE USERID = ? AND DATE = ?", (user_id, current_date))
            result = self.cursor.fetchone()
            if result:
                self.cursor.execute("UPDATE MESSAGE_XP SET MESSAGE = MESSAGE + 1 WHERE USERID = ? AND DATE = ?", (user_id, current_date))
            else:
                self.cursor.execute("INSERT INTO MESSAGE_XP (USERID, DATE, MESSAGE) VALUES (?, ?, 1)", (user_id, current_date))
            self.db.connection.commit()

            # Überprüfen, ob die Person die Zweitaccount-Rolle hat
            second_account_role_id = 1329202926916472902  # Ersetze dies durch die tatsächliche ID der Zweitaccount-Rolle
            if second_account_role_id not in [role.id for role in message.author.roles]:
                self.cursor.execute("UPDATE EXPERIENCE SET MESSAGE = MESSAGE + ? WHERE USERID = ?", (self.factor, user_id))
                self.db.connection.commit()
                await self.check_level_up(message.author, user_id)

    @exception_handler
    async def check_level_up(self, user, user_id):
        self.cursor.execute("SELECT (MESSAGE + VOICE + BONUS + INVITE) AS TOTAL_XP, LEVEL FROM EXPERIENCE WHERE USERID = ?", (user_id,))
        result = self.cursor.fetchone()
        if result:
            total_xp, current_level = result
            new_level = await self.calculate_level(total_xp)-1
            if new_level > current_level:
                self.cursor.execute("UPDATE EXPERIENCE SET LEVEL = ? WHERE USERID = ?", (new_level, user_id))
                self.db.connection.commit()
                await self.send_level_up_message(user, new_level)
                await self.assign_role(user, new_level)

    @exception_handler
    async def assign_role(self, member: disnake.Member, level):
        # Holen der USERID aus der USER-Tabelle anhand der member.id
        user_record = await self.globalfile.get_user_record(discordid=str(member.id))
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
                return False

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
            self.logger.info(f"Assigned role {new_role.name} to {member.name} for reaching level {level}")#
            return True 
        else:
            self.logger.info(f"No role assigned to {member.name} as no valid role found for their level")
            return False
  
    @exception_handler      
    async def _update_all_users_roles(self, inter: disnake.ApplicationCommandInteraction, send_level_up_messages: bool = False):
        """Aktualisiert die Rollen aller Benutzer basierend auf ihrem Level in der EXPERIENCE Tabelle."""
        await inter.response.defer()
        await self._update_all_users_roles(send_level_up_messages)
        await inter.edit_original_response(content="Rollen aller Benutzer wurden erfolgreich aktualisiert.")

    @exception_handler
    async def _update_all_users_roles(self, send_level_up_messages: bool = False):
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.bot:
                    continue

                # Holen der USERID aus der USER-Tabelle anhand der member.id
                user_record = await self.globalfile.get_user_record(discordid=str(member.id))
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

                tmp = await self.assign_role(member, level)

                if send_level_up_messages and level > 1 and tmp == True:
                    await self.send_level_up_message(member, level)                

    @exception_handler
    async def send_level_up_message(self, user: disnake.User, new_level):
        channel = self.bot.get_channel(1328753729419345950)  # Replace with your channel ID
        description = (
            f"Herzlichen Glückwunsch {user.mention}!\n"
            f"Du hast Level {new_level} erreicht! 🎉\n"
            f"Vielen Dank für deine Aktivität! 🥳"
        )
        embed = disnake.Embed(title=f"**{user.name} 🎖️ {new_level}**", description=description, color=disnake.Color.green())
        self.logger.info(f"Level Up Message sent for {user.name}. (ID: {user.id})")
        embed.set_thumbnail(url=user.avatar.url)
        await channel.send(content=f"{user.mention}", embed=embed)

    @exception_handler
    async def _calculate_message_xp(self, inter: disnake.ApplicationCommandInteraction):
        """Berechnet die MESSAGE_XP Werte aus der MESSAGE Tabelle."""
        await inter.response.defer()
        cursor = self.db.connection.cursor()

        # Lade das Datum der letzten Ausführung aus der env Datei
        load_dotenv(dotenv_path="envs/settings.env")
        last_run_date = os.getenv("LAST_MESSAGE_XP_CALCULATION")
        if last_run_date:
            last_run_date = datetime.datetime.strptime(last_run_date, '%Y-%m-%d %H:%M:%S')
        else:
            last_run_date = (await self.globalfile.get_current_time()).min

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
        current_time = (await self.globalfile.get_current_time()).strftime('%Y-%m-%d %H:%M:%S')
        set_key("envs/settings.env", "LAST_MESSAGE_XP_CALCULATION", current_time)

        await inter.edit_original_response(content="MESSAGE_XP Werte wurden erfolgreich berechnet und aktualisiert.")

    @exception_handler
    async def _recalculate_experience(self, inter: disnake.ApplicationCommandInteraction, send_level_up_messages: bool = False):
        """Berechnet die EXPERIENCE Werte aus der MESSAGE_XP, VOICE_XP, INVITE_XP und BONUS_XP Tabelle neu."""
        await inter.response.defer()
        await self._recalculate_experience(send_level_up_messages)
        await inter.edit_original_response(content="EXPERIENCE Werte wurden erfolgreich neu berechnet, Level und Rollen wurden aktualisiert.")
        
    @exception_handler
    async def _recalculate_experience(self, send_level_up_messages: bool = False):
        cursor = self.db.connection.cursor()
        load_dotenv(dotenv_path="envs/settings.env", override=True)
        self.factor = int(os.getenv("FACTOR"))
        self.message_worth_per_voicemin = float(os.getenv("MESSAGE_WORTH_PER_VOICEMIN"))

        # Recalculate MESSAGE_XP values
        cursor.execute("""
            SELECT USERID, SUM(MESSAGE) 
            FROM MESSAGE_XP 
            WHERE USERID NOT IN (SELECT SECONDACC_USERID FROM USER WHERE SECONDACC_USERID IS NOT NULL)
            GROUP BY USERID
        """)
        message_xp_data = cursor.fetchall()

        # Recalculate VOICE_XP values
        cursor.execute("""
            SELECT USERID, SUM(VOICE) 
            FROM VOICE_XP 
            WHERE USERID NOT IN (SELECT SECONDACC_USERID FROM USER WHERE SECONDACC_USERID IS NOT NULL)
            GROUP BY USERID
        """)
        voice_xp_data = cursor.fetchall()

        # Recalculate INVITE_XP values
        cursor.execute("""
            SELECT USERID, SUM(COUNT) 
            FROM INVITE_XP 
            WHERE USERID NOT IN (SELECT SECONDACC_USERID FROM USER WHERE SECONDACC_USERID IS NOT NULL)
            GROUP BY USERID
        """)
        invite_xp_data = cursor.fetchall()

        # Recalculate BONUS_XP values
        cursor.execute("""
            SELECT USERID, SUM(CALCULATED_XP) 
            FROM BONUS_XP 
            WHERE USERID NOT IN (SELECT SECONDACC_USERID FROM USER WHERE SECONDACC_USERID IS NOT NULL)
            GROUP BY USERID
        """)
        bonus_xp_data = cursor.fetchall()

        # Reset EXPERIENCE table
        cursor.execute("""
            UPDATE EXPERIENCE 
            SET MESSAGE = 0, VOICE = 0, INVITE = 0, BONUS = 0 
            WHERE USERID NOT IN (SELECT SECONDACC_USERID FROM USER WHERE SECONDACC_USERID IS NOT NULL)
        """)
        self.db.connection.commit()

        # Update EXPERIENCE table with new values
        for user_id, total_message_xp in message_xp_data:
            cursor.execute("UPDATE EXPERIENCE SET MESSAGE = ? WHERE USERID = ?", (total_message_xp * self.factor, user_id))
        for user_id, total_voice_xp in voice_xp_data:
            cursor.execute("UPDATE EXPERIENCE SET VOICE = ? WHERE USERID = ?", (total_voice_xp * self.message_worth_per_voicemin * self.factor, user_id))
        for user_id, total_invite_xp in invite_xp_data:
            cursor.execute("UPDATE EXPERIENCE SET INVITE = ? WHERE USERID = ?", (total_invite_xp * self.factor * 60, user_id))
        for user_id, total_bonus_xp in bonus_xp_data:
            cursor.execute("UPDATE EXPERIENCE SET BONUS = ? WHERE USERID = ?", (total_bonus_xp, user_id))
        self.db.connection.commit()

        # Update levels
        await self._update_levels()

        # Update roles and send level-up messages if required
        await self._update_all_users_roles(send_level_up_messages)

    @exception_handler
    async def _update_levels(self, inter: disnake.ApplicationCommandInteraction):
        """Aktualisiert die Level aller Benutzer basierend auf ihren Gesamt-XP."""
        await inter.response.defer()
        await self.update_levels()
        await inter.edit_original_response(content="Level aller Benutzer wurden erfolgreich aktualisiert. Bitte als nächstes update_all_users_roles ausführen.")

    @exception_handler
    async def update_levels(self):
        cursor = self.db.connection.cursor()

        cursor.execute("SELECT USERID, (MESSAGE + VOICE + INVITE + BONUS) AS TOTAL_XP FROM EXPERIENCE")
        experience_data = cursor.fetchall()

        for user_id, total_xp in experience_data:
            new_level = await self.calculate_level(total_xp)
            cursor.execute("UPDATE EXPERIENCE SET LEVEL = ? WHERE USERID = ?", (new_level, user_id))
        self.db.connection.commit()        

    @commands.Cog.listener()
    async def on_interaction(self, interaction: disnake.Interaction):
        if interaction.type == disnake.InteractionType.component:
            custom_id = interaction.data.get("custom_id")
            if custom_id in ["sort_by", "time_period"]:
                await self.handle_top_users_interaction(interaction)
      
    @exception_handler          
    async def create_top_users_view(self, sort_by="XP", time_period="total"):
        view = disnake.ui.View(timeout=None)  # Set timeout to None for persistence
        view.add_item(disnake.ui.Select(
            placeholder="Sortieren nach...",
            options=[
                disnake.SelectOption(label="Gesamt XP", value="XP", default=(sort_by == "XP")),
                disnake.SelectOption(label="Message XP", value="MESSAGE_XP", default=(sort_by == "MESSAGE_XP")),
                disnake.SelectOption(label="Voice XP", value="VOICE_XP", default=(sort_by == "VOICE_XP")),
                disnake.SelectOption(label="Invite XP", value="INVITE_XP", default=(sort_by == "INVITE_XP")),
                disnake.SelectOption(label="Bonus XP", value="BONUS_XP", default=(sort_by == "BONUS_XP"))
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

    @exception_handler
    async def handle_top_users_interaction(self, interaction: disnake.Interaction):
        await interaction.response.defer()  # Sofortige Antwort auf die Interaktion

        sort_by = "XP"
        time_period = "total"
        if interaction.data["custom_id"] == "sort_by":
            sort_by = interaction.data["values"][0]
        if interaction.data["custom_id"] == "time_period":
            time_period = interaction.data["values"][0]

        top_users = await self.fetch_top_users(sort_by, time_period)

        # Aktualisiere das Embed
        embed = disnake.Embed(title="Top Benutzer", color=disnake.Color.dark_blue())
        for i, (user_id, message_xp, voice_xp, invite_xp, bonus_xp, xp) in enumerate(top_users, start=1):
            cursor = self.db.connection.cursor()
            cursor.execute("SELECT LEVEL FROM EXPERIENCE WHERE USERID = ?", (user_id,))
            level = cursor.fetchone()[0]

            self.logger.debug(user_id, message_xp, voice_xp, invite_xp, bonus_xp, xp)
            try:
                user_record = await self.globalfile.get_user_record(user_id=user_id)
                if user_record:
                    discord_id = user_record['DISCORDID']
                    member = interaction.guild.get_member(int(discord_id))
                    if member:
                        embed.add_field(
                            name=f"#{i} {member.name} (Level {level})",
                            value=f"Total: {int(xp) // 10} XP |✍️ {int(message_xp)} |🎙️ {int(voice_xp // 2)} Min |📩 {int(invite_xp)} |✨ {int(bonus_xp)}",
                            inline=False
                        )
            except disnake.NotFound:
                continue  # Überspringe Benutzer, die nicht gefunden werden

        await interaction.edit_original_response(embed=embed, view=await self.create_top_users_view(sort_by, time_period))
        
    @exception_handler
    async def fetch_top_users(self, sort_by: str = "XP", time_period: str = "total"):
        # Bestimme das Zeitfenster
        current_time = (await self.globalfile.get_current_time())
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

        sort_column_index = {
            "MESSAGE_XP": 1,
            "VOICE_XP": 2,
            "INVITE_XP": 3,
            "BONUS_XP": 4,
            "XP": 5
        }.get(sort_by, 5)             

        # Hole die Daten aus der Datenbank
        cursor = self.db.connection.cursor()
        results = []
        cursor.execute("""
            SELECT EXPERIENCE.USERID
            FROM EXPERIENCE
        """)
        user_ids = cursor.fetchall()    

        if start_date:
            for user_id in user_ids:
                user_id = user_id[0]
                cursor.execute("SELECT SUM(MESSAGE) FROM MESSAGE_XP WHERE USERID = ? AND DATE >= ?", (user_id, start_date))
                message_xp = cursor.fetchone()[0] or 0 

                cursor.execute("SELECT SUM(VOICE) FROM VOICE_XP WHERE USERID = ? AND DATE >= ?", (user_id, start_date))
                voice_xp = cursor.fetchone()[0] or 0

                cursor.execute("SELECT SUM(COUNT) FROM INVITE_XP WHERE USERID = ? AND DATE >= ?", (user_id, start_date))
                invite_xp = cursor.fetchone()[0] or 0

                cursor.execute("SELECT SUM(CALCULATED_XP) FROM BONUS_XP WHERE USERID = ? AND INSERT_DATE >= ?", (user_id, start_date))
                bonus_xp = cursor.fetchone()[0] or 0
                
                total_xp = (message_xp*self.factor) + (voice_xp*self.factor*self.message_worth_per_voicemin) + (invite_xp*self.factor*60) + bonus_xp
                results.append((user_id, message_xp, voice_xp, invite_xp, bonus_xp, total_xp))

        else:
            for user_id in user_ids:
                user_id = user_id[0]
                cursor.execute("SELECT SUM(MESSAGE) FROM MESSAGE_XP WHERE USERID = ?", (user_id,))
                message_xp = cursor.fetchone()[0] or 0 

                cursor.execute("SELECT SUM(VOICE) FROM VOICE_XP WHERE USERID = ?", (user_id,))
                voice_xp = cursor.fetchone()[0] or 0

                cursor.execute("SELECT SUM(COUNT) FROM INVITE_XP WHERE USERID = ?", (user_id,))
                invite_xp = cursor.fetchone()[0] or 0

                cursor.execute("SELECT SUM(CALCULATED_XP) FROM BONUS_XP WHERE USERID = ?", (user_id,))
                bonus_xp = cursor.fetchone()[0] or 0

                total_xp = (message_xp*self.factor) + (voice_xp*self.factor*self.message_worth_per_voicemin) + (invite_xp*self.factor*60) + bonus_xp
                results.append((user_id, message_xp, voice_xp, invite_xp, bonus_xp, total_xp))       

        results.sort(key=lambda x: x[sort_column_index], reverse=True)
        results = results[:10]  # Limit to top 10 results
        return results
          
    @exception_handler          
    async def _top_users(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt die Top-Benutzer basierend auf XP, MESSAGE_XP oder VOICE_XP an."""
        await inter.response.defer()

        top_users = await self.fetch_top_users()

        # Erstelle das Embed
        embed = disnake.Embed(title="Top Benutzer", color=disnake.Color.dark_blue())
        for i, (user_id, message_xp, voice_xp, invite_xp, bonus_xp, xp) in enumerate(top_users, start=1):
            cursor = self.db.connection.cursor()
            cursor.execute("SELECT LEVEL FROM EXPERIENCE WHERE USERID = ?", (user_id,))
            level = cursor.fetchone()[0]

            try:
                user_record = await self.globalfile.get_user_record(user_id=user_id)
                if user_record:
                    discord_id = user_record['DISCORDID']
                    member = inter.guild.get_member(int(discord_id))
                    if member:
                        embed.add_field(
                            name=f"#{i} {member.name} ⯎ {level}",
                            value=f"Total: {int(xp)//10} XP 💠 ✍️ {message_xp} | 🎙️ {voice_xp // 2} | 📩 {invite_xp} | ✨ {bonus_xp} ",
                            inline=False
                        )
            except disnake.NotFound:
                continue  # Überspringe Benutzer, die nicht gefunden werden

        await inter.edit_original_response(embed=embed, view=await self.create_top_users_view())

    @exception_handler
    async def calculate_level(self, xp: int) -> int:
        """Berechnet das Level basierend auf den Gesamt-XP."""
        self.cursor.execute("SELECT LEVELNAME FROM LEVELXP WHERE CAST(XP AS INTEGER) > ? ORDER BY CAST(XP AS INTEGER) ASC LIMIT 1", (xp,))
        result = self.cursor.fetchone()
        return result[0] if result else 1
    
    @exception_handler
    async def _add_xp_to_levels(self, inter: disnake.ApplicationCommandInteraction, addxp: int):
        """Fügt jedem Level XP hinzu, berechnet die Level neu und vergibt die Rollen neu."""
        await inter.response.defer()
        cursor = self.db.connection.cursor()

        cursor.execute("SELECT LEVELNAME, XP FROM LEVELXP")
        levelxp_data = cursor.fetchall()

        for levelname, xp in levelxp_data:
            additional_xp = levelname * addxp
            new_xp = int(xp) + additional_xp
            cursor.execute("UPDATE LEVELXP SET XP = ? WHERE LEVELNAME = ?", (str(new_xp), levelname))
        self.db.connection.commit()

        await inter.edit_original_response(content="XP wurden hinzugefügt, Level neu berechnet und Rollen neu vergeben. (Bitte als nächstes recalculate_experience ausführen.)")    

    @exception_handler
    async def _add_xp_to_user(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, xp: int, reason: str):
        """Fügt einem einzelnen Benutzer XP hinzu."""
        await inter.response.defer()
        await self.add_bonus_xp(user, xp, reason)
        await inter.edit_original_response(content=f"{xp} XP wurden erfolgreich an {user.mention} vergeben.")

    @exception_handler
    async def add_bonus_xp(self, user: disnake.User, xp: int, reason: str):
        userrecord = await self.globalfile.get_user_record(discordid=user.id)
        if not userrecord:
            self.logger.warning(f"User record not found for {user.id}")
            return

        user_id = userrecord['ID']
        calculated_xp = xp // self.factor
        current_datetime = (await self.globalfile.get_current_time()).strftime('%Y-%m-%d %H:%M:%S')

        # Insert into BONUS_XP table
        self.cursor.execute("""
            INSERT INTO BONUS_XP (USERID, REASON, INSERT_DATE, ORIGINAL_XP, CALCULATED_XP)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, reason, current_datetime, xp, calculated_xp))
        self.db.connection.commit()

        # Überprüfen, ob die Person die Zweitaccount-Rolle hat
        guild = self.bot.get_guild(userrecord['GUILD_ID'])  # Ersetze 'GUILD_ID' durch das tatsächliche Feld, falls vorhanden
        member = guild.get_member(user.id)
        second_account_role_id = 123456789012345678  # Ersetze dies durch die tatsächliche ID der Zweitaccount-Rolle
        if second_account_role_id not in [role.id for role in member.roles]:
            # Update EXPERIENCE table
            self.cursor.execute("UPDATE EXPERIENCE SET BONUS = BONUS + ? WHERE USERID = ?", (calculated_xp, user_id))
            self.db.connection.commit()
        else:
            return

        # Send an embed to the user
        embed = disnake.Embed(
            title="XP Awarded!",
            description=f"You have been awarded {xp} XP.",
            color=disnake.Color.green()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Calculated XP", value=calculated_xp // 10, inline=False)
        embed.set_footer(text="Keep up the good work!")
        await user.send(embed=embed)

    @exception_handler
    async def _add_xp_to_voice_channel(self, inter: disnake.ApplicationCommandInteraction, channel_id: int, xp: int, reason: str):
        """Gibt allen Benutzern in einem bestimmten Voice-Channel einen XP-Wert."""
        await inter.response.defer()
        channel = self.bot.get_channel(channel_id)
        if not channel or not isinstance(channel, disnake.VoiceChannel):
            await inter.edit_original_response(content="Ungültiger Voice-Channel.")
            return

        for member in channel.members:
            await self.add_bonus_xp(member, xp, reason)

        await inter.edit_original_response(content=f"XP wurden erfolgreich an alle Benutzer im Voice-Channel {channel.name} vergeben.")        

    @exception_handler
    async def _activity_since(self, inter: disnake.ApplicationCommandInteraction, start_date: str, user: disnake.User = None):
        """Zeigt die Aktivität der Benutzer seit einem bestimmten Datum an."""
        await inter.response.defer()

        try:
            start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        except ValueError:
            await inter.edit_original_response(content="Ungültiges Datum. Bitte verwende das Format YYYY-MM-DD.")
            return

        cursor = self.db.connection.cursor()

        if user:
            user_record = await self.globalfile.get_user_record(discordid=user.id)
            user_id = user_record['ID']
            cursor.execute("SELECT SUM(MESSAGE) FROM MESSAGE_XP WHERE USERID = ? AND DATE >= ?", (user_id, start_date.strftime('%Y-%m-%d')))
            message_xp = cursor.fetchone()[0] or 0 

            cursor.execute("SELECT SUM(VOICE) FROM VOICE_XP WHERE USERID = ? AND DATE >= ?", (user_id, start_date.strftime('%Y-%m-%d')))
            voice_xp = cursor.fetchone()[0] or 0

            cursor.execute("SELECT SUM(COUNT) FROM INVITE_XP WHERE USERID = ? AND DATE >= ?", (user_id, start_date.strftime('%Y-%m-%d')))
            invite_xp = cursor.fetchone()[0] or 0

            cursor.execute("SELECT SUM(CALCULATED_XP) FROM BONUS_XP WHERE USERID = ? AND INSERT_DATE >= ?", (user_id, start_date.strftime('%Y-%m-%d')))
            bonus_xp = cursor.fetchone()[0] or 0

            total_xp = (message_xp * self.factor) + (voice_xp * self.factor * self.message_worth_per_voicemin) + (invite_xp * self.factor * 60) + bonus_xp
            activity_data = [(user_id, message_xp, voice_xp, invite_xp, bonus_xp, total_xp)]
        else:
            cursor.execute("SELECT USERID FROM EXPERIENCE")
            user_ids = cursor.fetchall()

            activity_data = []
            for user_id in user_ids:
                user_id = user_id[0]
                cursor.execute("SELECT SUM(MESSAGE) FROM MESSAGE_XP WHERE USERID = ? AND DATE >= ?", (user_id, start_date.strftime('%Y-%m-%d')))
                message_xp = cursor.fetchone()[0] or 0 

                cursor.execute("SELECT SUM(VOICE) FROM VOICE_XP WHERE USERID = ? AND DATE >= ?", (user_id, start_date.strftime('%Y-%m-%d')))
                voice_xp = cursor.fetchone()[0] or 0

                cursor.execute("SELECT SUM(COUNT) FROM INVITE_XP WHERE USERID = ? AND DATE >= ?", (user_id, start_date.strftime('%Y-%m-%d')))
                invite_xp = cursor.fetchone()[0] or 0

                cursor.execute("SELECT SUM(CALCULATED_XP) FROM BONUS_XP WHERE USERID = ? AND INSERT_DATE >= ?", (user_id, start_date.strftime('%Y-%m-%d')))
                bonus_xp = cursor.fetchone()[0] or 0

                total_xp = (message_xp * self.factor) + (voice_xp * self.factor * self.message_worth_per_voicemin) + (invite_xp * self.factor * 60) + bonus_xp
                activity_data.append((user_id, message_xp, voice_xp, invite_xp, bonus_xp, total_xp))

        if not activity_data:
            await inter.edit_original_response(content="Keine Aktivität seit dem angegebenen Datum gefunden.")
            return

        # Erstelle das Embed
        embed = disnake.Embed(title=f"Aktivität seit {start_date.strftime('%Y-%m-%d')}", color=disnake.Color.blue())
        for user_id, message_xp, voice_xp, invite_xp, bonus_xp, total_xp in activity_data:
            user_record = await self.globalfile.get_user_record(user_id=user_id)
            if user_record:
                discord_id = user_record['DISCORDID']
                member = inter.guild.get_member(int(discord_id))
                if member:
                    embed.add_field(
                        name=f"{member.name}",
                        value=f"✍️ Nachrichten XP: {message_xp}\n🎙️ Voice XP: {voice_xp}\n📩 Invite XP: {invite_xp}\n✨ Bonus XP: {bonus_xp}\nTotal XP: {int(total_xp)}",
                        inline=False
                    )

        await inter.edit_original_response(embed=embed)

def setupLevel(bot):
    bot.add_cog(Level(bot))