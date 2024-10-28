import disnake, os, re
from disnake.ext import commands, tasks
import disnake.file
import time
import re
from globalfile import Globalfile
from RoleHierarchy import RoleHierarchy
from datetime import datetime, timedelta, timedelta
from dotenv import load_dotenv
import logging
import sqlite3
from DBConnection import DatabaseConnection



class MyCommands(commands.Cog):
    """This will be for a ping command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseConnection()  # Stellen Sie sicher, dass die Datenbankverbindung initialisiert wird

        # Logger initialisieren
        self.logger = logging.getLogger("Commands")
        self.logger.setLevel(logging.INFO)
        self.globalfile = Globalfile(bot)        

        # Überprüfen, ob der Handler bereits hinzugefügt wurde
        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def cog_unload(self):
        Globalfile.unban_task.cancel()        

    @commands.slash_command()
    @RoleHierarchy.check_permissions("Test-Supporter")
    async def ping(self, inter: disnake.ApplicationCommandInteraction):
        """Get the bot's current websocket latency."""
        await inter.response.send_message(
            f"Pong! {round(self.bot.latency * 1000)}ms",
            ephemeral=True
        )

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Test-Supporter")
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
    @RoleHierarchy.check_permissions("Sr. Supporter")
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
            ban_end_time = datetime.now() + timedelta(seconds=duration_seconds)
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
    @RoleHierarchy.check_permissions("Sr. Supporter")
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
                guild = self.bot.get_guild(854698446996766730)
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
    @RoleHierarchy.check_permissions("Sr. Supporter")
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
    @RoleHierarchy.check_permissions("Moderator")
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
    @RoleHierarchy.check_permissions("Moderator")
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
    @RoleHierarchy.check_permissions("Moderator")
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
    @RoleHierarchy.check_permissions("Test-Supporter")
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
    @RoleHierarchy.check_permissions("Test-Supporter")
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
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("INSERT INTO NOTE (NOTE, USERID, IMAGEPATH, INSERTDATE) VALUES (?, ?, ?, ?)", (reason, userrecord['ID'], image_path, current_datetime))
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
        embed.set_footer(text=f"ID: {user.id} - heute um {(datetime.now() + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr")
        await inter.edit_original_response(embed=embed)

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Sr. Supporter")
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
    @RoleHierarchy.check_permissions("Test-Supporter")
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
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
            user_embed.set_footer(text=f"ID: {user.id} - heute um {(datetime.now() + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr")
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
        embed.set_footer(text=f"ID: {user.id} - heute um {(datetime.now() + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr")
        await inter.edit_original_response(embed=embed)

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Sr. Supporter")
    async def warn_delete(self, inter: disnake.ApplicationCommandInteraction, caseid: int):
        """Löscht eine Warn basierend auf der Warn ID."""
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

            cursor.execute("DELETE FROM WARN WHERE ID = ?", (caseid,))
            self.db.connection.commit()

            embed = disnake.Embed(title="Warn gelöscht", description=f"Warn mit der ID {caseid} wurde gelöscht.", color=disnake.Color.green())
            self.logger.info(f"Warn deleted: {caseid}")
            await inter.edit_original_response(embed=embed)
        except sqlite3.Error as e:
            embed = disnake.Embed(title="Fehler", description=f"Ein Fehler ist aufgetreten: {e}", color=disnake.Color.red())
            await inter.edit_original_response(embed=embed)
            self.logger.critical(f"An error occurred: {e}")

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Test-Supporter")
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
        embed.add_field(name="User ID", value=user_info[0], inline=False)        
        embed.add_field(name="Discord ID", value=user_info[1], inline=False)
        embed.add_field(name="Benutzername", value=user_info[2], inline=False)        


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
    @RoleHierarchy.check_permissions("Administrator") # Stellen Sie sicher, dass nur autorisierte Personen diesen Befehl ausführen können
    async def disconnect(self, inter: disnake.ApplicationCommandInteraction):
        """Schließt alle Verbindungen des Bots und beendet den Bot-Prozess."""
        await inter.response.send_message("Der Bot wird nun alle Verbindungen schließen und beendet werden.", ephemeral=True)
        await self.bot.close()

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Moderator")
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
    @RoleHierarchy.check_permissions("Leitung")
    async def delete_old_messages(self, inter: disnake.ApplicationCommandInteraction):
        """Löscht alle Nachrichten, die älter als sieben Tage sind, aus der Datenbank."""
        await inter.response.defer()
        cursor = self.db.connection.cursor()

        # Berechne das Datum vor sieben Tagen
        seven_days_ago = datetime.now() - timedelta(days=7)

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
    @RoleHierarchy.check_permissions("Administrator")
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
    @RoleHierarchy.check_permissions("Administrator")
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

def setup(bot: commands.Bot):
    bot.add_cog(MyCommands(bot))
