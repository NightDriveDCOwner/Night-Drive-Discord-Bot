import disnake, os, re
from disnake.ext import commands, tasks
from disnake.ui import Button, View
import disnake.file
import time
import re
from globalfile import Globalfile
from rolehierarchy import rolehierarchy
from datetime import datetime, timedelta, timedelta
import pytz
from dotenv import load_dotenv
import logging
import sqlite3
from dbconnection import DatabaseConnection
import asyncio
import platform
import psutil
import time



class MyCommands(commands.Cog):
    """This will be for a ping command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseConnection()  # Stellen Sie sicher, dass die Datenbankverbindung initialisiert wird

        # Logger initialisieren
        self.logger = logging.getLogger("Commands")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()         
        self.logger.setLevel(logging_level)
        self.globalfile = Globalfile(bot)        
        load_dotenv(dotenv_path="envs/settings.env")
        self.last_info_message = None
        self.last_info_time = None

        # Überprüfen, ob der Handler bereits hinzugefügt wurde
        if not self.logger.handlers:
          
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.db: sqlite3.Connection = DatabaseConnection()
        self.cursor: sqlite3.Cursor = self.db.connection.cursor()            
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS TIMEOUT (
            ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            USERID STRING,
            REASON TEXT,
            TIMEOUTTO TEXT,
            IMAGEPATH TEXT,
            REMOVED INTEGER DEFAULT 0,
            REMOVEDBY INTEGER DEFAULT 0,
            REMOVEDREASON TEXT
        )
        """)
        self.db.connection.commit()            

    def cog_unload(self):
        Globalfile.unban_task.cancel()        

    @commands.slash_command(guild_ids=[854698446996766730])
    async def info(self, inter: disnake.ApplicationCommandInteraction):
        """Get technical information about the bot and server."""
        await inter.response.defer(ephemeral=True)

        # Check cooldown
        if self.last_info_time and (time.time() - self.last_info_time < 300):
            await inter.edit_original_response(content=f"Bitte warte noch {300 - int(time.time() - self.last_info_time)} Sekunden, bevor du diesen Befehl erneut verwendest. [Letzte Nachricht]({self.last_info_message.jump_url})")
            return

        # Gather technical information
        programming_language = "Python"
        guild = inter.guild
        author = inter.guild.owner.mention
        server_os = platform.system()
        guild_info = {
            "user_count": guild.member_count,
            "boosts": guild.premium_subscription_count,
            "bots": sum(1 for member in guild.members if member.bot),
            "created_date": guild.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "owner": guild.owner.mention,
            "guild_lang": guild.preferred_locale
        }
        meta_info = {
            "uptime": time.time() - psutil.boot_time(),
            "system_cpu_time": psutil.cpu_times().system,
            "user_cpu_time": psutil.cpu_times().user,
            "ram_usage": psutil.virtual_memory().used / (1024 ** 3),  # in GB
            "bot_verified": False
        }

        # Create embed
        embed = disnake.Embed(title="Technische Informationen", color=disnake.Color.blue())
        embed.add_field(name="💻 **Programmiersprache**", value=programming_language, inline=True)
        embed.add_field(name="👤 **Autor**", value=author, inline=True)
        embed.add_field(name="🖥️ **Betriebssystem**", value=server_os, inline=True)
        embed.add_field(name="🏰 **Gilde**", value=f"Useranzahl: {guild_info['user_count']}\nBoosts: {guild_info['boosts']}\nBots: {guild_info['bots']}\nErstellt am: {guild_info['created_date']}\nBesitzer: {guild_info['owner']}\nSprache: {guild_info['guild_lang']}", inline=False)
        embed.add_field(name="📊 **Meta**", value=f"Uptime: {meta_info['uptime'] // 3600:.0f} Stunden\nSystem CPU Zeit: {meta_info['system_cpu_time']:.2f} Sekunden\nUser CPU Zeit: {meta_info['user_cpu_time']:.2f} Sekunden\nRAM Nutzung: {meta_info['ram_usage']:.2f} GB\nBot Verifiziert: {meta_info['bot_verified']}", inline=False)

        message = await inter.edit_original_response(embed=embed)

        # Update cooldown
        self.last_info_message = message
        self.last_info_time = time.time()

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Test-Supporter")
    async def server(inter: disnake.ApplicationCommandInteraction):
        await inter.response.send_message(
            f"Server name: {inter.guild.name}\nTotal members: {inter.guild.member_count}",
            ephemeral=True
        )    

    @commands.slash_command(guild_ids=[854698446996766730])
    async def user(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.send_message(
            f"Your tag: {inter.author}\nYour ID: {inter.author.id}", 
            ephemeral=True
        )                                   
                       
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
            ban_end_time = self.globalfile.get_current_time + timedelta(seconds=duration_seconds)
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
    @rolehierarchy.check_permissions("Senior Supporter")
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
    @rolehierarchy.check_permissions("Senior Supporter")
    async def list_banned_users(self, inter: disnake.ApplicationCommandInteraction):
        """Listet alle gebannten Benutzer auf und zeigt den Entbannzeitpunkt an, falls vorhanden."""
        await inter.response.defer(ephemeral=True)  # Verzögere die Interaktion        
        try:
            cursor = self.db.connection.cursor()
            cursor.execute("SELECT USERID, BANNEDTO FROM BAN WHERE UNBAN = 0")
            bans = cursor.fetchall()
        except sqlite3.Error as e:
            await inter.edit_original_response(f"Ein Fehler ist aufgetreten: {e}")
            return

        if not bans:
            await inter.edit_original_response("Es gibt keine gebannten Benutzer.")
            return

        # Erstellen eines Embeds
        embed = disnake.Embed(title="Liste der gebannten Benutzer", color=disnake.Color.red())

        # Formatierung der Ausgabe
        for ban in bans:
            user_id, unban_time = ban
            cursor.execute("SELECT USERNAME FROM USER WHERE ID = ?", (user_id,))
            username_result = cursor.fetchone()
            username = username_result[0] if username_result else "Unbekannt"

            if unban_time:
                # Konvertiere Unix-Zeitstempel in ein lesbares Datum
                unban_date = datetime.fromtimestamp(unban_time).strftime('%Y-%m-%d %H:%M:%S')
                embed.add_field(name=f"User ID: {user_id}", value=f"Username: {username}\nEntbannzeitpunkt: {unban_date}", inline=False)
            else:
                embed.add_field(name=f"User ID: {user_id}", value=f"Username: {username}\nEntbannzeitpunkt: Nicht festgelegt", inline=False)

        # Sende die Liste der gebannten Benutzer
        await inter.edit_original_response(embed=embed)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Moderator")
    async def badword_add(self, inter: disnake.ApplicationCommandInteraction, word: str):
        """Füge ein Wort zur Badword-Liste hinzu, wenn es noch nicht existiert."""
        await inter.response.defer()  # Verzögere die Interaktion

        word = word.strip()  # Entferne führende und abschließende Leerzeichen
        cursor = self.db.connection.cursor()
        
        # Überprüfe, ob das Wort bereits in der Tabelle existiert
        cursor.execute("SELECT word FROM BADWORD WHERE WORD = ?", (word,))
        result = cursor.fetchone()
        
        embed = disnake.Embed(title="Badword Hinzufügen", color=disnake.Color.green())

        if not result:
            # Wort existiert nicht, füge es hinzu
            cursor.execute("INSERT INTO BADWORD (word) VALUES (?)", (word,))
            self.db.connection.commit()
            embed.description = f"{word} wurde zur Badword-Liste hinzugefügt."
        else:
            embed.description = f"{word} existiert bereits in der Badword-Liste."

        await inter.edit_original_response(embed=embed)
            
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Moderator")
    async def badword_remove(self, inter: disnake.ApplicationCommandInteraction, word: str):
        """Entferne ein Wort von der Badword-Liste."""
        await inter.response.defer()  # Verzögere die Interaktion

        word = word.strip()  # Entferne führende und abschließende Leerzeichen
        cursor = self.db.connection.cursor()
        
        # Überprüfe, ob das Wort in der Tabelle existiert
        cursor.execute("SELECT word FROM Badword WHERE word = ?", (word,))
        result = cursor.fetchone()
        
        embed = disnake.Embed(title="Badword Entfernen", color=disnake.Color.red())

        if result:
            # Wort existiert, entferne es
            cursor.execute("DELETE FROM Badword WHERE word = ?", (word,))
            self.db.connection.commit()
            embed.description = f"{word} wurde von der Badword-Liste entfernt."
        else:
            embed.description = f"{word} existiert nicht in der Badword-Liste."

        await inter.edit_original_response(embed=embed)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Moderator")
    async def badwords_list(self, inter: disnake.ApplicationCommandInteraction):
        """Zeige die aktuelle Badword-Liste."""
        await inter.response.defer()  # Verzögere die Interaktion

        cursor = self.db.connection.cursor()
        
        # Hole alle Wörter aus der Tabelle
        cursor.execute("SELECT word FROM Badword")
        badwords = cursor.fetchall()
        
        embed = disnake.Embed(title="Aktuelle Badwords", color=disnake.Color.red())

        if badwords:
            badwords_list = "\n".join(word[0] for word in badwords)
            embed.add_field(name="Badwords", value=badwords_list, inline=False)
        else:
            embed.add_field(name="Badwords", value="Die Badword-Liste ist leer.", inline=False)

        await inter.edit_original_response(embed=embed)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Test-Supporter")
    async def add_user_to_ticket(self, inter: disnake.ApplicationCommandInteraction, ticket_id: int, user: disnake.User):
        """Fügt einen Benutzer zu einem Ticket-Channel hinzu."""
        await inter.response.defer()         
        # Suche nach dem Ticket-Channel
        ticket_channel = None
        for channel in inter.guild.text_channels:
            if channel.name.startswith("ticket") and str(ticket_id) in channel.name:
                ticket_channel = channel
                break

        if not ticket_channel:
            await inter.response.send_message("Ticket-Channel nicht gefunden.")
            return

        # Berechtigungen setzen
        overwrite = disnake.PermissionOverwrite()
        overwrite.read_messages = True
        overwrite.send_messages = True

        # Benutzer zum Channel hinzufügen
        try:
            await ticket_channel.set_permissions(user, overwrite=overwrite)
            await inter.edit_original_response(f"{user.mention} wurde zum Ticket-Channel hinzugefügt.")
        except Exception as e:
            await inter.edit_original_response(f"Fehler beim Hinzufügen des Benutzers: {e}") 

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Test-Supporter")
    async def note_add(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, reason: str, proof: disnake.Attachment = None, show: str = "True"):
        """Erstellt eine Notiz für einen Benutzer."""
        await inter.response.defer()           
        # Überprüfe, ob ein Attachment in der Nachricht vorhanden ist      
        image_path = None

        avatar_url = user.avatar.url if user.avatar else user.default_avatar.url

        if proof:
            image_path = await self.globalfile.save_image(proof, f"{user.id}")

        userrecord = self.globalfile.get_user_record(discordid=user.id)

        cursor = self.db.connection.cursor()
        current_datetime = self.globalfile.get_current_time().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("INSERT INTO NOTE (NOTE, USERID, IMAGEPATH, INSERT_DATE) VALUES (?, ?, ?, ?)", (reason, userrecord['ID'], image_path, current_datetime))
        self.db.connection.commit()

        # Hole die zuletzt eingefügte ID
        caseid = cursor.lastrowid

        self.logger.info(f"Note added: {reason}")

        # Sende eine Bestätigungsnachricht
        embed = disnake.Embed(title=f"Notiz erstellt [ID: {caseid}]", description=f"Für {user.mention} wurde eine Notiz erstellt.", color=disnake.Color.green())
        embed.set_author(name=user.name, icon_url=avatar_url)
        embed.add_field(name="Grund", value=reason, inline=False)
        if image_path:
            embed.add_field(name="Bildpfad", value=image_path, inline=False)
        embed.set_footer(text=f"ID: {user.id} - heute um {(self.globalfile.get_current_time().strftime('%H:%M:%S'))} Uhr")
        await inter.edit_original_response(embed=embed)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Senior Supporter")
    async def note_delete(self, inter: disnake.ApplicationCommandInteraction, caseid: int):
        """Löscht eine Note basierend auf der Note ID."""
        await inter.response.defer()        
        try:
            cursor = self.db.connection.cursor()
            cursor.execute("DELETE FROM NOTE WHERE ID = ?", (caseid,))
            self.db.connection.commit()

            embed = disnake.Embed(title="Note gelöscht", description=f"Note mit der ID {caseid} wurde gelöscht.", color=disnake.Color.green())
            self.logger.info(f"Note deleted: {caseid}")
            await inter.edit_original_response(embed=embed)
        except sqlite3.Error as e:
            embed = disnake.Embed(title="Fehler", description=f"Ein Fehler ist aufgetreten: {e}", color=disnake.Color.red())
            await inter.edit_original_response(embed=embed)
            self.logger.critical(f"An error occurred: {e}")

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
            self.logger.info(f"Warn deleted: {caseid}, Warnlevel adjusted for user {user_id}")
            await inter.edit_original_response(embed=embed)
        except sqlite3.Error as e:
            embed = disnake.Embed(title="Fehler", description=f"Ein Fehler ist aufgetreten: {e}", color=disnake.Color.red())
            await inter.edit_original_response(embed=embed)
            self.logger.critical(f"An error occurred: {e}")

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Test-Supporter")
    async def user_profile(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User):
        """Zeigt das Profil eines Benutzers an, einschließlich Notizen und Warnungen."""
        await inter.response.defer()
        cursor = self.db.connection.cursor()
        userrecord = self.globalfile.get_user_record(discordid=user.id)

        # Hole die Benutzerinformationen aus der Tabelle User
        cursor.execute("SELECT * FROM USER WHERE ID = ?", (userrecord['ID'],))
        user_info = cursor.fetchone()

        if not user_info:
            await inter.response.send_message(f"Keine Informationen für Benutzer {user.mention} gefunden.")
            return

        # Hole alle Notizen des Benutzers aus der Tabelle Note
        cursor.execute("SELECT * FROM NOTE WHERE USERID = ?", (userrecord['ID'],))
        notes = cursor.fetchall()

        # Hole alle Warnungen des Benutzers aus der Tabelle Warn
        cursor.execute("SELECT * FROM WARN WHERE USERID = ?", (userrecord['ID'],))
        warns = cursor.fetchall()

        # Erstelle ein Embed
        embed = disnake.Embed(title=f"Profil von {user.name}", color=disnake.Color.blue())
        embed.set_author(name=user.name, icon_url=user.avatar.url if user.avatar else user.default_avatar.url)

        # Füge Benutzerinformationen hinzu
        # embed.add_field(name="User ID", value=user_info[0], inline=False)        
        # embed.add_field(name="Discord ID", value=user_info[1], inline=False)
        # embed.add_field(name="Benutzername", value=user_info[2], inline=False)   
        current_time = self.globalfile.get_current_time().strftime('%H:%M:%S')
        embed.set_footer(text=f"ID: {user_info[1]} | {user_info[0]} - heute um {(current_time)} Uhr") 

        # Füge Notizen hinzu
        if notes:
            for note in notes:
                caseid = note[0]
                reason = note[2]
                image_path = note[3]
                note_text = f"Grund: {reason}"
                if image_path:
                    note_text += f"\nBildpfad: {image_path}"
                embed.add_field(name=f"Note [ID: {caseid}]", value=note_text, inline=False)
                if image_path and os.path.exists(image_path):
                    embed.set_image(file=disnake.File(image_path))

        # Füge Warnungen hinzu
        if warns:
            for warn in warns:
                caseid = warn[0]
                reason = warn[1]
                image_path = warn[2]
                warn_text = f"Grund: {reason}"
                if image_path:
                    warn_text += f"\nBildpfad: {image_path}"
                embed.add_field(name=f"Warnung [ID: {caseid}]", value=warn_text, inline=False)
                if image_path and os.path.exists(image_path):
                    embed.set_image(file=disnake.File(image_path))

        await inter.edit_original_response(embed=embed)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator") # Stellen Sie sicher, dass nur autorisierte Personen diesen Befehl ausführen können
    async def disconnect(self, inter: disnake.ApplicationCommandInteraction):
        """Schließt alle Verbindungen des Bots und beendet den Bot-Prozess."""
        await inter.response.send_message("Der Bot wird nun alle Verbindungen schließen und beendet werden.", ephemeral=True)
        await self.bot.close()

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Senior Moderator")
    async def sync_users(self, inter: disnake.ApplicationCommandInteraction):
        """Synchronisiere alle Benutzer des Servers mit der Users Tabelle."""
        await inter.response.defer()
        guild = inter.guild
        members = guild.members

        cursor = self.db.connection.cursor()

        for member in members:
            # Überprüfen, ob der Benutzer bereits in der Tabelle Users existiert
            cursor.execute("SELECT ID, USERNAME FROM USER WHERE DISCORDID = ?", (str(member.id),))
            result = cursor.fetchone()

            if not result:
                # Benutzer existiert nicht, füge ihn in die Tabelle Users ein
                cursor.execute("INSERT INTO USER (DISCORDID, USERNAME) VALUES (?, ?)", (str(member.id), member.name))
                self.db.connection.commit()
            else:
                # Benutzer existiert, überprüfe den Benutzernamen
                user_id, db_username = result
                if db_username != member.name:
                    # Benutzername ist nicht korrekt, aktualisiere ihn
                    cursor.execute("UPDATE USER SET USERNAME = ? WHERE ID = ?", (member.name, user_id))
                    self.db.connection.commit()

        await inter.edit_original_response(content="Benutzer-Synchronisation abgeschlossen.")

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Co. Owner")
    async def delete_old_messages(self, inter: disnake.ApplicationCommandInteraction):
        """Löscht alle Nachrichten, die älter als sieben Tage sind, aus der Datenbank."""
        await inter.response.defer()
        cursor = self.db.connection.cursor()

        # Berechne das Datum vor sieben Tagen
        seven_days_ago = self.globalfile.get_current_time - timedelta(days=7)

        # Hole alle Nachrichten aus der Datenbank
        cursor.execute("SELECT MESSAGEID, INSERT_DATE FROM Message")
        all_messages = cursor.fetchall()

        for message_id, insert_date in all_messages:
            # Konvertiere den Timestamp-String in ein datetime-Objekt
            message_timestamp = datetime.strptime(insert_date, '%Y-%m-%d %H:%M:%S')

            # Überprüfe, ob die Nachricht älter als sieben Tage ist
            if message_timestamp < seven_days_ago:
                # Lösche die Nachricht aus der Datenbank
                cursor.execute("DELETE FROM Message WHERE MESSAGEID = ?", (message_id,))
                self.db.connection.commit()

        await inter.edit_original_response(content="Alle Nachrichten, die älter als sieben Tage sind, wurden aus der Datenbank gelöscht.")
             
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Co. Owner")
    async def remove_role_from_all(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        """Entfernt eine bestimmte Rolle bei allen Benutzern in der Gilde."""
        await inter.response.defer()
        guild = inter.guild
        members = guild.members

        removed_count = 0

        for member in members:
            if role in member.roles:
                try:
                    await member.remove_roles(role)
                    removed_count += 1
                except disnake.Forbidden:
                    await inter.edit_original_response(content=f"Ich habe keine Berechtigung, die Rolle {role.name} bei {member.mention} zu entfernen.")
                    return
                except disnake.HTTPException as e:
                    await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")
                    return
        await inter.edit_original_response(content=f"Die Rolle {role.name} wurde bei {removed_count} Benutzern entfernt.")

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def unban_all_users(self, inter: disnake.ApplicationCommandInteraction):
        """Entbannt alle gebannten Benutzer in der Gilde."""
        await inter.response.defer()
        guild = inter.guild

        try:
            bans = await guild.bans().flatten()
            if not bans:
                await inter.edit_original_response(content="Es gibt keine gebannten Benutzer.")
                return

            unbanned_count = 0
            for ban_entry in bans:
                user = ban_entry.user
                try:
                    await guild.unban(user)
                    unbanned_count += 1
                except disnake.Forbidden:
                    await inter.edit_original_response(content=f"Ich habe keine Berechtigung, {user.mention} zu entbannen.")
                    return
                except disnake.HTTPException as e:
                    await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")
                    return

            await inter.edit_original_response(content=f"Alle gebannten Benutzer wurden entbannt. Anzahl der entbannten Benutzer: {unbanned_count}")
        except disnake.HTTPException as e:
            await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")
  
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Co. Owner")
    async def kick_inactive_users(self, inter: disnake.ApplicationCommandInteraction, months: int, execute: bool = False):
        """Kicke alle Benutzer, die innerhalb der angegebenen Monate keine Nachrichten geschrieben haben."""
        await inter.response.defer()
        await inter.edit_original_response(content=f"Starte das Überprüfen von inaktiven Benutzern, die in den letzten {months} Monaten nichts geschrieben haben.")
        await self.kick_inactive_users_task(inter, months, execute)       

    async def kick_inactive_users_task(self, inter: disnake.ApplicationCommandInteraction, months: int, execute: bool):

        def split_into_chunks(text, max_length):
            """Splits text into chunks of a maximum length."""
            return [text[i:i + max_length] for i in range(0, len(text), max_length)]

        def create_embed(title, color, fields):
            embed = disnake.Embed(title=title, color=color)
            for name, value in fields:
                embed.add_field(name=name, value=value, inline=False)
            return embed  
              
        MAX_EMBED_FIELD_LENGTH = 1024
        MAX_EMBED_TOTAL_LENGTH = 5000 
        guild = inter.guild
        cutoff_date = self.globalfile.get_current_time - timedelta(days=months*30)
        active_users = set()
        kicked_users = []
        failed_kicks = []
        self.logger.info(f"Starte Kick-Prozess für inaktive Benutzer, die in den letzten {months} Monaten nichts geschrieben haben...")   
        embeds = []
        current_embed_fields = []
        current_embed_length = 0

        semaphore = asyncio.Semaphore(500)
        tasks = []

        start_time = time.time()  # Startzeit erfassen

        for channel in guild.text_channels:
            tasks.append(self.log_active_users(channel, cutoff_date, semaphore, active_users))

        await asyncio.gather(*tasks)

        end_time = time.time()  # Endzeit erfassen
        elapsed_time = end_time - start_time  # Zeitdifferenz berechnen

        inactive_users = [member for member in guild.members if member.id not in active_users and not member.bot]

        self.logger.info(f"Lesevorgang abgeschlossen. {len(inactive_users)} inaktive Benutzer gefunden, die gekickt werden sollen.")
        self.logger.info(f"Das Einlesen der Channels hat {elapsed_time:.2f} Sekunden gedauert.")            
        i = 0

        for member in inactive_users:
            if execute:
                try:
                    # Sende Nachricht an den Benutzer
                    invite = await guild.text_channels[0].create_invite(max_uses=1, unique=True)
                    embed = disnake.Embed(title="Du wurdest gekickt von Aincrad", color=disnake.Color.dark_blue())
                    embed.set_author(name="Aincrad", icon_url=guild.icon.url)
                    embed.add_field(name="Grund", value=f"Inaktiv für {months} Monate. Grund für diesen Prozess ist das entfernen von inaktiven/Scammer Accounts.", inline=False)                    
                    embed.add_field(name="Wiederbeitreten", value=f"[Hier klicken]({invite.url}) um dem Server wieder beizutreten. Wir empfangen dich gerne erneut, solltest du dem Server wieder beitreten wollen.", inline=False)
                    try:
                        await member.send(embed=embed)
                    except disnake.Forbidden:
                        self.logger.warning(f"Keine Berechtigung, Nachricht an {member.name} (ID: {member.id}) zu senden.")
                        await member.kick(reason=f"Inaktiv für {months} Monate")
                        kicked_users.append(member)
                        self.logger.info(f"User {member.name} (ID: {member.id}) wurde gekickt. {i}/{len(inactive_users)}")                                            
                except disnake.Forbidden:
                    failed_kicks.append(member)
                    self.logger.warning(f"Keine Berechtigung, {member.name} (ID: {member.id}) zu kicken.")
                except disnake.HTTPException as e:
                    failed_kicks.append(member)
                    self.logger.error(f"Fehler beim Kicken von {member.name} (ID: {member.id}): {e}")
            else:
                kicked_users.append(member)

        embed = disnake.Embed(title="Kick Inaktive Benutzer", color=disnake.Color.red())
        embed.add_field(name="Anzahl der gekickten Benutzer", value=len(kicked_users), inline=False)

        if kicked_users:
            kicked_list = "\n".join([f"{member.name} (ID: {member.id})" for member in kicked_users])
            if len(kicked_list) > MAX_EMBED_FIELD_LENGTH:
                chunks = split_into_chunks(kicked_list, MAX_EMBED_FIELD_LENGTH)
                for i, chunk in enumerate(chunks):
                    field_name = f"Gekickte Benutzer (Teil {i+1})" if execute else f"Benutzer, die gekickt werden würden (Teil {i+1})"
                    current_embed_fields.append((field_name, chunk))
                    current_embed_length += len(field_name) + len(chunk)
                    if current_embed_length > MAX_EMBED_TOTAL_LENGTH:
                        embeds.append(create_embed("Kick Inaktive Benutzer", disnake.Color.red(), current_embed_fields))
                        current_embed_fields = []
                        current_embed_length = 0
            else:
                current_embed_fields.append(("Gekickte Benutzer" if execute else "Benutzer, die gekickt werden würden", kicked_list))
                current_embed_length += len("Gekickte Benutzer" if execute else "Benutzer, die gekickt werden würden") + len(kicked_list)

        # Add failed kicks to embed fields
        if failed_kicks:
            failed_list = "\n".join([f"{member.name} (ID: {member.id})" for member in failed_kicks])
            if len(failed_list) > MAX_EMBED_FIELD_LENGTH:
                chunks = split_into_chunks(failed_list, MAX_EMBED_FIELD_LENGTH)
                for i, chunk in enumerate(chunks):
                    field_name = f"Fehlgeschlagene Kicks (Teil {i+1})"
                    current_embed_fields.append((field_name, chunk))
                    current_embed_length += len(field_name) + len(chunk)
                    if current_embed_length > MAX_EMBED_TOTAL_LENGTH:
                        embeds.append(create_embed("Kick Inaktive Benutzer", disnake.Color.red(), current_embed_fields))
                        current_embed_fields = []
                        current_embed_length = 0
            else:
                current_embed_fields.append(("Fehlgeschlagene Kicks", failed_list))
                current_embed_length += len("Fehlgeschlagene Kicks") + len(failed_list)

        if current_embed_fields:
            embeds.append(create_embed("Kick Inaktive Benutzer", disnake.Color.red(), current_embed_fields))

        # Send all embeds
        first_embed = True
        channel = inter.channel
        for embed in embeds:
            if first_embed:
                await inter.edit_original_response(embed=embed)
                first_embed = False
            else:
                await channel.send(embed=embed)

        self.logger.info(f"Kick-Prozess abgeschlossen. {len(kicked_users)} Benutzer wurden gekickt." if execute else f"{len(kicked_users)} Benutzer würden gekickt werden.")

    async def log_active_users(self, channel, cutoff_date, semaphore, active_users):
        async with semaphore:
            try:
                async for message in channel.history(limit=None):
                    if message.created_at < cutoff_date:
                        break
                    active_users.add(message.author.id)
            except Exception as e:
                self.logger.warning(f"Fehler beim Durchsuchen der Nachrichten in Kanal {channel.name}: {e}")

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Leitung")
    async def test_kick(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        """Testet das Senden einer Nachricht an einen Benutzer."""
        await inter.response.defer()        
        self.logger.info(f"User {member.name} (ID: {member.id}) wurde gekickt. (Test)")
        # Sende Nachricht an den Benutzer
        invite = await inter.guild.text_channels[0].create_invite(max_uses=1, unique=True)
        embed = disnake.Embed(title="Du wurdest gekickt von Aincrad", color=disnake.Color.dark_blue())
        embed.set_author(name="Aincrad", icon_url=inter.guild.icon.url)
        embed.add_field(name="Grund", value=f"Inaktiv für test Monate. Grund für diesen Prozess ist das entfernen von inaktiven/Scammer Accounts", inline=False)                    
        embed.add_field(name="Wiederbeitreten", value=f"[Hier klicken]({invite.url}) um dem Server wieder beizutreten. Wir empfangen dich gerne erneut, solltest du dem Server wieder beitreten wollen.", inline=False)
        try:
            await member.send(embed=embed)        
            await member.kick(reason=f"Test kick")
        except Exception as e:
            self.logger.warning(f"Fehler beim Test kick: {e}")
        await inter.edit_original_response(content=f"Test kick für {member.mention} wurde durchgeführt.")
        
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
    async def help_moderation(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt alle Moderationsbefehle an."""
        await inter.response.defer(ephemeral=True)
        commands_list = [
            {"name": "ban", "description": "Banne einen Benutzer und speichere ein Bild als Beweis.", "rank": "Senior Supporter"},
            {"name": "unban", "description": "Entbanne einen Benutzer von diesem Server.", "rank": "Senior Supporter"},
            {"name": "list_banned_users", "description": "Listet alle gebannten Benutzer auf und zeigt den Entbannzeitpunkt an, falls vorhanden.", "rank": "Senior Supporter"},
            {"name": "note_add", "description": "Erstellt eine Notiz für einen Benutzer.", "rank": "Test-Supporter"},
            {"name": "note_delete", "description": "Löscht eine Note basierend auf der Note ID.", "rank": "Senior Supporter"},
            {"name": "warn_add", "description": "Erstellt eine Warnung für einen Benutzer.", "rank": "Test-Supporter"},
            {"name": "warn_delete", "description": "Löscht eine Warn basierend auf der Warn ID und setzt das Warnlevel zurück.", "rank": "Senior Supporter"},
            {"name": "timeout", "description": "Timeout einen Benutzer für eine bestimmte Dauer und optional eine Warnung erstellen.", "rank": "Senior Supporter"},
            {"name": "timeout_remove", "description": "Entfernt einen Timeout basierend auf der Timeout ID.", "rank": "Moderator"},
            {"name": "badword_add", "description": "Füge ein Wort zur Badword-Liste hinzu, wenn es noch nicht existiert.", "rank": "Moderator"},
            {"name": "badword_remove", "description": "Entferne ein Wort von der Badword-Liste.", "rank": "Moderator"},
            {"name": "badwords_list", "description": "Zeige die aktuelle Badword-Liste.", "rank": "Moderator"},
            {"name": "kick_inactive_users", "description": "Kicke alle Benutzer, die innerhalb der angegebenen Monate keine Nachrichten geschrieben haben.", "rank": "Leitung"},
            {"name": "remove_role_from_all", "description": "Entfernt eine bestimmte Rolle bei allen Benutzern in der Gilde.", "rank": "Administrator"},
            {"name": "unban_all_users", "description": "Entbannt alle gebannten Benutzer in der Gilde.", "rank": "Administrator"},
            {"name": "delete_old_messages", "description": "Löscht alle Nachrichten, die älter als sieben Tage sind, aus der Datenbank.", "rank": "Leitung"},
            {"name": "sync_users", "description": "Synchronisiere alle Benutzer des Servers mit der Users Tabelle.", "rank": "Moderator"},
            {"name": "disconnect", "description": "Schließt alle Verbindungen des Bots und beendet den Bot-Prozess.", "rank": "Administrator"}
        ]

        await self.paginate_commands(inter, commands_list, "Moderationsbefehle")

    @commands.slash_command(guild_ids=[854698446996766730])
    async def help_user(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt alle Benutzerbefehle an."""
        await inter.response.defer(ephemeral=True)
        commands_list = [
            {"name": "ping", "description": "Get the bot's current websocket latency.", "rank": "Test-Supporter"},
            {"name": "server", "description": "Get the server's name and member count.", "rank": "Test-Supporter"},
            {"name": "user", "description": "Get your tag and ID.", "rank": "Test-Supporter"},
            {"name": "add_user_to_ticket", "description": "Fügt einen Benutzer zu einem Ticket-Channel hinzu.", "rank": "Test-Supporter"},
            {"name": "user_profile", "description": "Zeigt das Profil eines Benutzers an, einschließlich Notizen und Warnungen.", "rank": "Test-Supporter"}
        ]

        await self.paginate_commands(inter, commands_list, "Benutzerbefehle")

    async def paginate_commands(self, inter: disnake.ApplicationCommandInteraction, commands_list, title):
        MAX_COMMANDS_PER_PAGE = 5

        def get_role_mention(role_name):
            role = disnake.utils.get(inter.guild.roles, name=role_name)
            return role.mention if role else role_name

        def create_embed(page):
            embed = disnake.Embed(title=title, color=disnake.Color.blue())
            start = page * MAX_COMMANDS_PER_PAGE
            end = start + MAX_COMMANDS_PER_PAGE
            for command in commands_list[start:end]:
                embed.add_field(
                    name=f"📜 {command['name']}",
                    value=f"📝 {command['description']}\n🔒 Rang: {get_role_mention(command['rank'])}",
                    inline=False
                )
            embed.set_footer(text=f"Seite {page + 1} von {len(commands_list) // MAX_COMMANDS_PER_PAGE + 1}")
            return embed

        async def update_embed(interaction, page):
            embed = create_embed(page)
            await interaction.response.edit_message(embed=embed, view=create_view(page))

        def create_view(page):
            view = View()
            if page > 0:
                view.add_item(Button(label="Zurück", style=disnake.ButtonStyle.primary, custom_id=f"prev_{page}"))
            if (page + 1) * MAX_COMMANDS_PER_PAGE < len(commands_list):
                view.add_item(Button(label="Weiter", style=disnake.ButtonStyle.primary, custom_id=f"next_{page}"))
            return view

        current_page = 0
        embed = create_embed(current_page)
        view = create_view(current_page)

        message = await inter.edit_original_response(embed=embed, view=view)

        def check(interaction: disnake.MessageInteraction):
            return interaction.message.id == message.id and interaction.user.id == inter.user.id

        while True:
            interaction = await self.bot.wait_for("interaction", check=check)
            if interaction.data["custom_id"].startswith("prev_"):
                current_page -= 1
            elif interaction.data["custom_id"].startswith("next_"):
                current_page += 1
            await update_embed(interaction, current_page)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Supporter")
    async def verify_user(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, proof: disnake.Attachment):
        """Verifiziert einen Benutzer, speichert ein Bild und gibt ihm die Rolle 'Verified'."""
        await inter.response.defer()

        # Überprüfe, ob ein Attachment in der Nachricht vorhanden ist
        image_path = None
        if proof:
            image_path = await self.globalfile.save_image(proof, f"{user.id}_verification")

        # Hole die Benutzerinformationen aus der Tabelle User
        userrecord = self.globalfile.get_user_record(discordid=user.id)

        cursor = self.db.connection.cursor()
        cursor.execute("UPDATE USER SET verified = 1, imagepath = ? WHERE ID = ?", (image_path, userrecord['ID']))
        self.db.connection.commit()

        # Rolle "Verified" hinzufügen
        verified_role = disnake.utils.get(inter.guild.roles, name="Verified")
        if verified_role:
            await user.add_roles(verified_role)
            await inter.edit_original_response(content=f"{user.mention} wurde verifiziert und die Rolle <@1066793314482913391> wurde hinzugefügt.")
        else:
            await inter.edit_original_response(content="Die Rolle 'Verified' wurde nicht gefunden.")    
            
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Supporter")
    async def add_verify_image(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, proof: disnake.Attachment):
        """Fügt ein weiteres Bild zu einem Benutzer hinzu."""
        await inter.response.defer()

        # Überprüfe, ob ein Attachment in der Nachricht vorhanden ist
        if not proof:
            await inter.edit_original_response(content="Bitte füge ein Bild hinzu.")
            return

        # Hole die Benutzerinformationen aus der Tabelle User
        userrecord = self.globalfile.get_user_record(discordid=user.id)

        # Hole den aktuellen Bildpfad
        cursor = self.db.connection.cursor()
        cursor.execute("SELECT imagepath FROM USER WHERE ID = ?", (userrecord['ID'],))
        current_imagepath = cursor.fetchone()[0]

        # Bestimme den neuen Bildpfad
        base_path = f"{user.id}_verification"
        if current_imagepath:
            image_paths = current_imagepath.split(';')
            new_image_index = len(image_paths)
            new_image_path = await self.globalfile.save_image(proof, f"{base_path}_{new_image_index}")
            updated_imagepath = f"{current_imagepath};{new_image_path}"
        else:
            new_image_path = await self.globalfile.save_image(proof, base_path)
            updated_imagepath = new_image_path

        # Aktualisiere den Bildpfad in der Datenbank
        cursor.execute("UPDATE USER SET imagepath = ? WHERE ID = ?", (updated_imagepath, userrecord['ID']))
        self.db.connection.commit()

        await inter.edit_original_response(content=f"Ein weiteres Bild wurde für {user.mention} hinzugefügt.")                        

def setupCommands(bot: commands.Bot):
    bot.add_cog(MyCommands(bot))
