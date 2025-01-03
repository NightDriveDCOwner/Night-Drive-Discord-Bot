import disnake, time, os, dotenv
from disnake.ext import commands
from globalfile import Globalfile
import logging
from dbconnection import DatabaseConnection
from rolehierarchy import rolehierarchy
import sqlite3
from datetime import datetime, timedelta, timedelta, date, timezone


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message = disnake.message
        self.userid = int
        self.logger = logging.getLogger("Moderation")     
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper() 
        self.logger.setLevel(logging_level)
        self.globalfile = Globalfile(bot)  
        self.db: sqlite3.Connection = DatabaseConnection()
        self.cursor: sqlite3.Cursor = self.db.connection.cursor()
                
        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS KICK (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER,
                REASON TEXT,
                IMAGEPATH TEXT
            )
        """)
        self.db.connection.commit()
               

    def add_user_to_badwords_times(user_id: int):
        expiry_time = time.time() + 24 * 60 * 60 # 24 Stunden ab jetzt
        with open('badwords_times.txt', 'a', encoding='utf-8') as file:
            file.write(f"{user_id},{expiry_time}\n")

    def is_user_banned_from_badwords(self, user_id: int) -> bool:
        current_time = time.time()
        file_path = 'updated_badwords_times.txt'  # Geänderter Dateipfad
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as file:
                pass  # Erstellt die Datei, wenn sie nicht existiert
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                user_id_in_file, expiry_time = line.strip().split(',')
                if int(user_id_in_file) == user_id and float(expiry_time) > current_time:
                    return True
        return False      

    async def delete_message_by_id(self, channel_id: int, message_id: int):
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            self.logger.warning(f"Kanal mit ID {channel_id} nicht gefunden.")
            return

        async for message in channel.history(limit=None):
            if message.id == message_id:
                await message.delete()
                self.logger.info(f"Nachricht mit ID {message_id} gelöscht.")
                return

        self.logger.warning(f"Nachricht mit ID {message_id} nicht gefunden.")    

    async def check_message_for_badwords(self, message: disnake.Message):
        self.message = message
        self.userid = message.author.id
        self.channelid = message.channel.id
        self.messageid = message.id

        cursor = self.db.connection.cursor()

        # Lade die Badwords aus der Datenbank
        cursor.execute("SELECT word FROM Badword")
        badwords = [row[0].lower() for row in cursor.fetchall()]

        if any(badword in (' ' + message.content.lower() + ' ') for badword in badwords):
            # Hole die Benutzer-ID aus der Tabelle User
            user_record_id = Globalfile.get_user_record_id(username=message.author.name, user_id=message.author.id)
            if not user_record_id:
                await message.channel.send(f"Benutzer {message.author.name} nicht in der Datenbank gefunden.")
                return

            # Lade die aktuelle Fall-ID aus der Datenbank
            cursor.execute("SELECT MAX(ID) FROM BADWORD_CASSES")
            case_id = cursor.fetchone()[0] or 0
            new_case_id = case_id + 1
            record_message_id = Globalfile.get_message_record_id(self.messageid)

            # Dokumentiere den Fall in der Datenbank
            cursor.execute("INSERT INTO BADWORD_CASSES (USERID, MESSAGEID) VALUES (?, ?)",
                           (user_record_id, record_message_id))
            self.db.connection.commit()

            notification_channel_id = 854698447113027594  # Ersetzen Sie dies durch die tatsächliche ID Ihres Kanals
            embed = disnake.Embed(title="Badword Verstoß", description="Ein Benutzer hat ein Badword verwendet.", color=0xff0000)
            # Fügen Sie Felder hinzu, um die Informationen zu speichern
            notification_channel = self.bot.get_channel(notification_channel_id)
            if notification_channel:
                if not self.is_user_banned_from_badwords(message.author.id):
                    embed.add_field(name="Nachricht", value=message.content, inline=False)
                    embed.add_field(name="Von", value=f"{message.author.name} (ID: {message.author.id})", inline=False)
                    embed.add_field(name="In", value=f"{message.channel.name} (ID: {message.channel.id})", inline=False)
                    allow_button = disnake.ui.Button(label="Nachricht erlauben", custom_id=f"allow_message;{new_case_id}", style=disnake.ButtonStyle.success)
                    delete_button = disnake.ui.Button(label="Nachricht löschen", custom_id=f"delete_message;{new_case_id}", style=disnake.ButtonStyle.danger)
                    view = disnake.ui.View()
                    view.add_item(allow_button)
                    view.add_item(delete_button)
                    await notification_channel.send(embed=embed, view=view)
                else:
                    embed.add_field(name="Nachricht wurde gelöscht (Eintrag vorhanden)", value=message.content, inline=False)
                    embed.add_field(name="Von", value=f"{message.author.name} (ID: {message.author.id})", inline=False)
                    embed.add_field(name="In", value=f"{message.channel.name} (ID: {message.channel.id})", inline=False)
                    await message.delete()
                    await notification_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_button_click(self, interaction: disnake.MessageInteraction):
        embed = disnake.Embed(title="Badword Verstoß", description="Ein Benutzer hat ein Badword verwendet.", color=0xff0000)
        if interaction.component.custom_id == "allow_message":
            # Logik zum Erlauben der Nachricht        
            await interaction.message.delete()
            await interaction.response.send_message("Nachricht erlaubt.", ephemeral=True)
        elif interaction.component.custom_id == "delete_message":
            # Logik zum Löschen der Nachricht
            await interaction.message.delete()
            await interaction.response.send_message("Nachricht gelöscht.", ephemeral=True)
            self.message.delete(self.channelid, self.messageid)
            
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Senior Supporter")
    async def timeout(self, inter: disnake.ApplicationCommandInteraction, 
                        member: disnake.Member, 
                        duration: str = commands.Param(name="dauer", description="Dauer des Timeouts in Sek., Min., Std., Tagen oder Jahre.(Bsp.: 0s0m0h0d0j)"),
                        reason: str = commands.Param(name="begründung", description="Grund für den Timeout", default="Kein Grund angegeben"),
                        warn: bool = commands.Param(name="warn", description="Soll eine Warnung erstellt werden?", default=False),
                        warn_level: int = commands.Param(name="warnstufe", description="Warnstufe (1-3) | Default = 1 wenn warn_level = True", default=1)):
        """Timeout einen Benutzer für eine bestimmte Dauer und optional eine Warnung erstellen."""
        await inter.response.defer()

        # Berechnen der Timeout-Dauer
        duration_seconds = self.globalfile.convert_duration_to_seconds(duration)
        if duration_seconds < 60 or duration_seconds > 28 * 24 * 60 * 60:
            await inter.edit_original_response(content="Die Timeout-Dauer muss zwischen 60 Sekunden und 28 Tagen liegen.")
            return

        timeout_end_time = self.globalfile.get_current_time() + timedelta(seconds=duration_seconds)

        try:
            await member.timeout(duration=timedelta(seconds=duration_seconds), reason=reason)            
            self.logger.info(f"Timeout for User {member.name} (ID: {member.id}) created by {inter.user.name} (ID: {inter.user.id})") 
            embed = disnake.Embed(title="Benutzer getimeoutet", description=f"{member.mention} wurde erfolgreich getimeoutet!", color=disnake.Color.red())
            embed.set_author(name=member.name, icon_url=member.avatar.url if member.avatar else member.default_avatar.url)
            embed.add_field(name="Grund", value=reason, inline=False)
            embed.add_field(name="Dauer", value=duration, inline=True)
            embed.add_field(name="Ende des Timeouts", value=timeout_end_time.strftime('%Y-%m-%d %H:%M:%S'), inline=True)
            await inter.edit_original_response(embed=embed)

            # Speichere den Timeout in der Datenbank
            cursor = self.db.connection.cursor()
            current_datetime = self.globalfile.get_current_time().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("INSERT INTO TIMEOUT (USERID, REASON, TIMEOUTTO) VALUES (?, ?, ?)", (member.id, reason, timeout_end_time.strftime('%Y-%m-%d %H:%M:%S')))
            self.db.connection.commit()

        except disnake.Forbidden:
            await inter.edit_original_response(content=f"Ich habe keine Berechtigung, {member.mention} zu timeouten.")
            return
        except disnake.HTTPException as e:
            await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")           

        if warn:
            # Warnung erstellen
            if warn_level < 1 or warn_level > 3:
                await inter.edit_original_response(content="Warnlevel muss zwischen 1 und 3 liegen.")
                return

            avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
            userrecord = self.globalfile.get_user_record(discordid=member.id)

            cursor = self.db.connection.cursor()
            current_datetime = self.globalfile.get_current_time().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("INSERT INTO WARN (USERID, REASON, LEVEL, INSERTDATE) VALUES (?, ?, ?, ?)", (userrecord['ID'], reason, warn_level, current_datetime))
            self.db.connection.commit()

            # Hole die zuletzt eingefügte ID
            caseid = cursor.lastrowid

            # Aktualisiere das Warnlevel in der User-Tabelle
            cursor.execute("UPDATE USER SET WARNLEVEL = ? WHERE ID = ?", (warn_level, userrecord['ID']))
            self.db.connection.commit()

            self.logger.info(f"Warn added to User {userrecord['USERNAME']} : {reason}")

            # Sende eine Warn-Nachricht an den Benutzer
            try:
                user_embed = disnake.Embed(title="Warnung erhalten", description=f"Du hast eine Warnung erhalten.", color=disnake.Color.red())
                user_embed.set_author(name=member.name, icon_url=avatar_url)
                user_embed.add_field(name="Grund", value=reason, inline=False)
                user_embed.add_field(name="Warnlevel", value=str(warn_level), inline=False)
                user_embed.set_footer(text=f"ID: {member.id} - heute um {(self.globalfile.get_current_time().strftime('%H:%M:%S'))} Uhr")
                await member.send(embed=user_embed)
            except Exception as e:
                await inter.edit_original_response(content=f"Fehler beim Senden der Warn-Nachricht: {e}")

            # Sende eine Bestätigungsnachricht
            warn_embed = disnake.Embed(title=f"Warnung erstellt [ID: {caseid}]", description=f"Für {member.mention} wurde eine Warnung erstellt.", color=disnake.Color.red())
            warn_embed.set_author(name=member.name, icon_url=avatar_url)
            warn_embed.add_field(name="Grund", value=reason, inline=False)
            warn_embed.add_field(name="Warnlevel", value=str(warn_level), inline=False)
            warn_embed.set_footer(text=f"ID: {member.id} - heute um {(self.globalfile.get_current_time().strftime('%H:%M:%S'))} Uhr")
            await inter.edit_original_response(embed=warn_embed)
            self.logger.info(f"Warn for User {member.name} (ID: {member.id}) created by {inter.user.name} (ID: {inter.user.id})")

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Moderator")
    async def timeout_remove(self, inter: disnake.ApplicationCommandInteraction, timeout_id: int, reason: str = commands.Param(name="begründung", description="Grund für das Entfernen des Timeouts", default="Kein Grund angegeben")):
        """Entfernt einen Timeout basierend auf der Timeout ID."""
        await inter.response.defer()

        cursor = self.db.connection.cursor()
        cursor.execute("SELECT * FROM TIMEOUT WHERE ID = ?", (timeout_id,))
        timeout_record = cursor.fetchone()

        if not timeout_record:
            await inter.edit_original_response(content=f"Kein Timeout mit der ID {timeout_id} gefunden.")
            return

        user_id = timeout_record[1]
        user = await self.bot.fetch_user(user_id)

        try:
            await user.timeout(duration=None, reason=reason)
            self.logger.info(f"Timeout removed for User {user.name} (ID: {user.id}) by {inter.user.name} (ID: {inter.user.id})")
            cursor.execute("UPDATE TIMEOUT SET REMOVED = 1, REMOVEDBY = ?, REMOVEDREASON = ? WHERE ID = ?", (inter.author.id, reason, timeout_id))
            self.db.connection.commit()

            embed = disnake.Embed(title="Timeout entfernt", description=f"Der Timeout für {user.mention} wurde erfolgreich entfernt.", color=disnake.Color.green())
            embed.set_author(name=user.name, icon_url=user.avatar.url if user.avatar else user.default_avatar.url)
            embed.add_field(name="Grund", value=reason, inline=False)
            await inter.edit_original_response(embed=embed)
        except disnake.Forbidden:
            await inter.edit_original_response(content=f"Ich habe keine Berechtigung, den Timeout für {user.mention} zu entfernen.")
        except disnake.HTTPException as e:
            await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Test-Supporter")
    async def warn_add(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, reason: str, level: int = 1, proof: disnake.Attachment = None, show: str = "True"):
        """Erstellt eine Warnung für einen Benutzer."""
        # Überprüfe, ob ein Attachment in der Nachricht vorhanden ist
        await inter.response.defer()               
        image_path = None

        if level < 1 or level > 3:
            await inter.edit_original_response(content="Warnlevel muss zwischen 1 und 3 liegen.")
            return

        avatar_url = user.avatar.url if user.avatar else user.default_avatar.url

        if proof:
            image_path = await Globalfile.save_image(proof, f"{user.id}")

        userrecord = self.globalfile.get_user_record(discordid=user.id)            

        cursor = self.db.connection.cursor()
        current_datetime = self.globalfile.get_current_time().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("INSERT INTO WARN (USERID, REASON, IMAGEPATH, LEVEL, INSERTDATE) VALUES (?, ?, ?, ?, ?)", (userrecord['ID'], reason, image_path, level, current_datetime))
        self.db.connection.commit()

        # Hole die zuletzt eingefügte ID
        caseid = cursor.lastrowid

        # Aktualisiere das Warnlevel in der User-Tabelle
        cursor.execute("UPDATE USER SET WARNLEVEL = ? WHERE ID = ?", (level, userrecord['ID']))
        self.db.connection.commit()

        self.logger.info(f"Warn added to User {userrecord['USERNAME']} : {reason}")

        # Sende eine Warn-Nachricht an den Benutzer
        try:
            user_embed = disnake.Embed(title="Warnung erhalten", description=f"Du hast eine Warnung erhalten.", color=disnake.Color.red())
            user_embed.set_author(name=user.name, icon_url=avatar_url)
            user_embed.add_field(name="Grund", value=reason, inline=False)
            user_embed.add_field(name="Warnlevel", value=str(level), inline=False)
            if image_path:
                user_embed.add_field(name="Bildpfad", value=image_path, inline=False)
            user_embed.set_footer(text=f"ID: {user.id} - heute um {(self.globalfile.get_current_time().strftime('%H:%M:%S'))} Uhr")
            await user.send(embed=user_embed)
        except Exception as e:
            await inter.edit_original_response(content=f"Fehler beim Senden der Warn-Nachricht: {e}")

        # Sende eine Bestätigungsnachricht
        embed = disnake.Embed(title=f"Warnung erstellt [ID: {caseid}]", description=f"Für {user.mention} wurde eine Warnung erstellt.", color=disnake.Color.red())
        embed.set_author(name=user.name, icon_url=avatar_url)
        embed.add_field(name="Grund", value=reason, inline=False)
        embed.add_field(name="Warnlevel", value=str(level), inline=False)
        if image_path:
            embed.add_field(name="Bildpfad", value=image_path, inline=False)
        embed.set_footer(text=f"ID: {user.id} - heute um {(self.globalfile.get_current_time().strftime('%H:%M:%S'))} Uhr")
        await inter.edit_original_response(embed=embed)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Moderator")
    async def warn_delete(self, inter: disnake.ApplicationCommandInteraction, caseid: int):
        """Löscht eine Warn basierend auf der Warn ID und setzt das Warnlevel zurück."""
        await inter.response.defer()        
        try:
            cursor = self.db.connection.cursor()
            cursor.execute("SELECT * FROM WARN WHERE ID = ?", (caseid,))
            warn = cursor.fetchone()

            if warn is None:
                embed = disnake.Embed(title="Warn nicht gefunden", description=f"Es gibt keine Warnung mit der ID {caseid}.", color=disnake.Color.red())
                await inter.edit_original_response(embed=embed)
                self.logger.info(f"Warn not found: {caseid}")
                return

            user_id = warn[1]  # Assuming USERID is the second column in WARN table
            warn_level = warn[4]  # Assuming LEVEL is the fifth column in WARN table

            # Reduziere das Warnlevel des Benutzers
            cursor.execute("SELECT WARNLEVEL FROM USER WHERE ID = ?", (user_id,))
            current_warn_level = cursor.fetchone()[0]
            new_warn_level = max(0, current_warn_level - warn_level)
            cursor.execute("UPDATE USER SET WARNLEVEL = ? WHERE ID = ?", (new_warn_level, user_id))
            self.db.connection.commit()

            # Lösche die Warnung
            cursor.execute("DELETE FROM WARN WHERE ID = ?", (caseid,))
            self.db.connection.commit()

            embed = disnake.Embed(title="Warn gelöscht", description=f"Warn mit der ID {caseid} wurde gelöscht und das Warnlevel wurde angepasst.", color=disnake.Color.green())
            self.logger.info(f"Warn deleted: {caseid}, Warnlevel adjusted for user {user_id} to {new_warn_level} by {inter.author.name} (ID: {inter.author.id}).")
            await inter.edit_original_response(embed=embed)
        except sqlite3.Error as e:
            embed = disnake.Embed(title="Fehler", description=f"Ein Fehler ist aufgetreten: {e}", color=disnake.Color.red())
            await inter.edit_original_response(embed=embed)
            self.logger.critical(f"An error occurred: {e}")
                       
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Senior Supporter")
    async def ban(self, 
                  inter: disnake.ApplicationCommandInteraction, 
                  member: disnake.Member = commands.Param(name="benutzer", description="Der Benutzer, der gebannt werden soll."), 
                  reason: str = commands.Param(name="begründung", description="Grund warum der Benutzer gebannt werden soll", default="Kein Grund angegeben"),
                  duration: str = commands.Param(name="dauer", description="Dauer des Bans in Sek., Min., Std., Tagen oder Jahre.(Bsp.: 0s0m0h0d0j) Nichts angegeben = Dauerhaft", default=""),
                  delete_days: int = commands.Param(name="geloeschte_nachrichten", description="Anzahl der Tage, für die Nachrichten des Benutzers gelöscht werden sollen. (0-7, Default = 0)", default=0),
                  proof: disnake.Attachment = commands.Param(name="beweis", description="Ein Bild als Beweis für den Ban und zur Dokumentation", default=None)):
        """Banne einen Benutzer und speichere ein Bild als Beweis."""
        await inter.response.defer()  # Verzögere die Interaktion
        image_path = ""
        # Berechnen der Banndauer
        if duration != "0s":
            duration_seconds = self.globalfile.convert_duration_to_seconds(duration)
            ban_end_time = self.globalfile.get_current_time() + timedelta(seconds=duration_seconds)
            ban_end_timestamp = int(ban_end_time.timestamp())
            ban_end_formatted = ban_end_time.strftime('%Y-%m-%d %H:%M:%S')
        else:
            ban_end_timestamp = None
            ban_end_formatted = "Unbestimmt"

        userrecord = self.globalfile.get_user_record(discordid=member.id)

        cursor = self.db.connection.cursor()
        cursor.execute("SELECT * FROM BAN WHERE USERID = ?", (userrecord['ID'],))
        bans = cursor.fetchall()
        
        ban_found = False
        for ban in bans:
            if not ban[6] == 1:  # Assuming 'Unban' is a column in your BANS table
                ban_found = True

        if not ban_found:
            try:
                await member.ban(reason=reason, delete_message_days=delete_days)
                ban_successful = True
            except disnake.Forbidden:
                ban_successful = False
                await inter.edit_original_response(content=f"Ich habe keine Berechtigung, {member.mention} zu bannen.")
            except disnake.HTTPException as e:
                ban_successful = False
                await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")

            if ban_successful:
                if proof:
                    image_path = await self.globalfile.save_image(proof, f"{member.id}_{duration_seconds}")

                cursor.execute(
                    "INSERT INTO BAN (USERID, REASON, BANNEDTO, DELETED_DAYS, IMAGEPATH) VALUES (?, ?, ?, ?, ?)",
                    (userrecord['ID'], reason, ban_end_timestamp, str(delete_days), image_path)
                )
                self.db.connection.commit()        
                
                embed = disnake.Embed(title="Benutzer gebannt", description=f"{member.mention} wurde erfolgreich gebannt!", color=disnake.Color.red())
                avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                embed.set_author(name=member.name, icon_url=avatar_url)
                embed.set_footer(text=f"User ID: {member.id} | {userrecord['ID']}")
                embed.add_field(name="Grund", value=reason, inline=False)
                embed.add_field(name="Dauer", value=duration, inline=True)
                embed.add_field(name="Ende des Banns", value=ban_end_formatted, inline=True)
                embed.add_field(name="Gelöschte Nachrichten (Tage)", value=str(delete_days), inline=True)
                if proof:
                    embed.set_image(url=proof.url)  # Setze das Bild des Beweises, falls vorhanden

                await inter.edit_original_response(embed=embed)
        else:
            await inter.edit_original_response(content=f"{member.mention} ist bereits gebannt! Ban nicht möglich.")
            self.logger.info(f"User {member.id} ban not possible. User is already banned.")

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Moderator")
    async def unban(self, inter: disnake.ApplicationCommandInteraction, 
                    userid: int = commands.param(name="userid", description="Hier kannst du die UserID unserer Datenbank angeben.", default=0), 
                    username: str = commands.Param(name="username", description="Hier kannst du den Benutzernamen angeben, falls die UserID nicht bekannt ist.", default=""), 
                    reason: str = commands.Param(name="begruendung", description="Bitte gebe eine Begründung für den Unban an.", default="Kein Grund angegeben")):
        """Entbanne einen Benutzer von diesem Server."""
        await inter.response.defer()  # Verzögere die Interaktion und mache sie nur für den Benutzer sichtbar
        try:
            userrecord = self.globalfile.get_user_record(user_id=userid,username=username)                
            user = await self.bot.fetch_user(int(userrecord['DISCORDID']))        

            # Überprüfen, ob ein offener Ban existiert
            cursor = self.db.connection.cursor()
            cursor.execute("SELECT * FROM BAN WHERE USERID = ?", (str(userrecord['ID']),))
            bans = cursor.fetchall()
            
            ban_found = False
            for ban in bans:
                if not ban[6] == "1":  # Assuming 'Unban' is a column in your BANS table
                    ban_found = True

            if not ban_found:
                await inter.edit_original_response(content=f"{user.mention} ist nicht gebannt! Unban nicht möglich.")
                self.logger.info(f"User {user.id} unban not possible. User is not banned.")
            else:
                guild = inter.guild
                await guild.unban(user)
                cursor.execute("UPDATE BAN SET UNBAN = 1 WHERE USERID = ? AND UNBAN = 0", (str(userrecord['ID']),))
                self.db.connection.commit()

                embed = disnake.Embed(title="Benutzer entbannt", description=f"{user.mention} wurde erfolgreich entbannt!", color=disnake.Color.green())
                avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
                embed.set_author(name=user.name, icon_url=avatar_url)
                embed.set_footer(text=f"User ID: {userrecord['DISCORDID']} | {userrecord['ID']}")                            

                await inter.edit_original_response(embed=embed)
                self.logger.info(f"User {user.id} unbanned.")
        except Exception as e:
            self.logger.critical(f"An error occurred: {e}")
            await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")            

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def kick_users_underage(self, inter: disnake.ApplicationCommandInteraction):
        """Kicke alle Benutzer mit zwei bestimmten Rollen und sende ihnen eine Nachricht."""
        await inter.response.defer()
        guild = inter.guild

        # Definiere die Rollen-IDs
        role1_id = 1300559732905607269  # Ersetze dies durch die tatsächliche ID der ersten Rolle
        role2_id = 987654321098765432  # Ersetze dies durch die tatsächliche ID der zweiten Rolle

        role1 = guild.get_role(role1_id)
        role2 = guild.get_role(role2_id)
        members_to_kick1 = [member for member in guild.members if role1 in member.roles]
        members_to_kick2 =[member for member in guild.members if role2 in member.roles]
        embed = disnake.Embed(
            title="Server-Umstellung auf 18+",
            description=(
                "Aufgrund der Umstellung des Servers auf einen Dating-Server für 18+ müssen wir uns leider von dir verabschieden. Vielen Dank, dass du Teil unseres Projektes warst."
                "Ich, Tatzu, der Owner des Servers entschuldige mich für diese Schritt."
                ),
            color=disnake.Color.dark_blue()
        )
        embed.set_footer(text="Wir wünschen dir alles Gute!")
        embed.set_author(name=inter.guild.name, icon_url=guild.icon.url)

        for member in members_to_kick1:
            try:
                try:
                    await member.send(embed=embed)
                except Exception as e:
                    self.logger.error(f"Fehler beim Senden der Nachricht an {member.name} (ID: {member.id}): {e}")
                await member.kick(reason="Server-Umstellung auf 18+")
                self.logger.info(f"User {member.name} (ID: {member.id}) wurde gekickt.")
            except Exception as e:
                self.logger.error(f"Fehler beim Kicken von {member.name} (ID: {member.id}): {e}")
                
        for member in members_to_kick2:
            try:
                try:
                    await member.send(embed=embed)
                except Exception as e:
                    self.logger.error(f"Fehler beim Senden der Nachricht an {member.name} (ID: {member.id}): {e}")
                await member.kick(reason="Server-Umstellung auf 18+")
                self.logger.info(f"User {member.name} (ID: {member.id}) wurde gekickt.")
            except Exception as e:
                self.logger.error(f"Fehler beim Kicken von {member.name} (ID: {member.id}): {e}")                

        await inter.edit_original_response(content=f"{len(members_to_kick1)+len(members_to_kick2)} Benutzer wurden gekickt.")
        self.logger.info(f"{len(members_to_kick1)+len(members_to_kick2)} Benutzer wurden gekickt.")
 
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Senior Supporter")
    async def kick(self, 
                inter: disnake.ApplicationCommandInteraction, 
                member: disnake.Member = commands.Param(name="benutzer", description="Der Benutzer, der gekickt werden soll."), 
                reason: str = commands.Param(name="begründung", description="Grund warum der Benutzer gekickt werden soll", default="Kein Grund angegeben"),
                proof: disnake.Attachment = commands.Param(name="beweis", description="Ein Bild als Beweis für den Kick und zur Dokumentation", default=None)):
        """Kicke einen Benutzer und speichere ein Bild als Beweis."""
        await inter.response.defer()  # Verzögere die Interaktion
        image_path = ""

        try:
            await member.kick(reason=reason)
            kick_successful = True
        except disnake.Forbidden:
            kick_successful = False
            await inter.edit_original_response(content=f"Ich habe keine Berechtigung, {member.mention} zu kicken.")
        except disnake.HTTPException as e:
            kick_successful = False
            await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")

        if kick_successful:
            if proof:
                image_path = await self.globalfile.save_image(proof, f"{member.id}_kick")

            cursor = self.db.connection.cursor()
            cursor.execute(
                "INSERT INTO KICK (USERID, REASON, IMAGEPATH) VALUES (?, ?, ?)",
                (member.id, reason, image_path)
            )
            self.db.connection.commit()

            embed = disnake.Embed(title="Benutzer gekickt", description=f"{member.mention} wurde erfolgreich gekickt!", color=disnake.Color.red())
            avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
            embed.set_author(name=member.name, icon_url=avatar_url)
            embed.set_footer(text=f"User ID: {member.id}")
            embed.add_field(name="Grund", value=reason, inline=False)
            if proof:
                embed.set_image(url=proof.url)  # Setze das Bild des Beweises, falls vorhanden

            await inter.edit_original_response(embed=embed)
       
def setupModeration(bot: commands.Bot):
    bot.add_cog(Moderation(bot))                
