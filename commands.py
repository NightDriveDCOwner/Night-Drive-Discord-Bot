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



class MyCommands(commands.Cog):
    """This will be for a ping command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        Globalfile.unban_task.start(self)
        load_dotenv()
        self.logger = logging.getLogger("Commands")
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
        await inter.response.send_message(f"Pong! {round(self.bot.latency * 1000)}ms")

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Test-Supporter")
    async def server(inter):
        await inter.response.send_message(
            f"Server name: {inter.guild.name}\nTotal members: {inter.guild.member_count}"
        )    

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Test-Supporter")
    async def user(inter):
        await inter.response.send_message(f"Your tag: {inter.author}\nYour ID: {inter.author.id}")                                    
                       
    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Sr. Supporter")   
    async def ban(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member, reason: str = "No reason provided", duration: str = "0s", delete_days: int = 0, proof: disnake.Attachment = None):
        """Banne einen Benutzer und speichere ein Bild als Beweis."""
        caseid = int(os.getenv("caseid"))
        # Überprüfe, ob ein Attachment in der Nachricht vorhanden ist
        if proof:
            image_path = await Globalfile.save_image(proof, f"{member.id}_{caseid}")
                
        duration_seconds = Globalfile.convert_duration_to_seconds(duration)
        ban_entry = f"{caseid}, User ID:{member.id}, Grund:{reason}, Bildpfad:{image_path}, Deleted Days:{delete_days}, DateTime Unbaned:{datetime.time() + duration_seconds}, Show:True\n"
        with open('bans.txt', 'a', encoding='utf-8') as file:
            file.write(ban_entry)
        caseid += 1
        Globalfile.update_ids(caseid)            

        await member.ban(reason=reason, delete_message_days=delete_days)        
        embed = disnake.Embed(title="Benutzer gebannt", description=f"{member.mention} wurde erfolgreich gebannt!", color=disnake.Color.red())
        avatar_url = member.avatar.url
        if avatar_url is None:
            avatar_url = member.default_avatar.url  

        embed.set_author(name=member.name, icon_url=avatar_url)
        embed.set_footer(text=f"User ID: {member.id}")
        embed.add_field(name="Grund", value=reason, inline=False)
        embed.add_field(name="Dauer", value=duration, inline=True)
        embed.add_field(name="Gelöschte Nachrichten (Tage)", value=str(delete_days), inline=True)
        if proof:
            embed.set_image(url=proof.url) # Setze das Bild des Beweises, falls vorhanden

        await inter.response.send_message(embed=embed)

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Moderator")
    async def unban(self, inter: disnake.ApplicationCommandInteraction, user_id: int, show: bool):
        """Entbanne einen Benutzer von diesem Server."""
        try:
            user = await self.bot.fetch_user(user_id)
            # Überprüfen, ob ein offener Ban existiert
            with open('bans.txt', 'r', encoding='utf-8') as file:
                bans = file.readlines()
            updated_bans = []
            ban_found = False
            for ban in bans:
                components = ban.strip().split(',')
                if components[1].startswith(f"User ID:{user_id}") and "DateTime Unbaned: " not in ban:
                    # Aktualisiere den Ban-Eintrag
                    updated_ban = re.sub(r"DateTime Unbaned: .*?,", f"DateTime Unbaned: now, Show:{show},", ban)
                    updated_bans.append(updated_ban)
                    ban_found = True
                else:
                    updated_bans.append(ban)

            # Aktualisiere die bans.txt-Datei
            with open('bans.txt', 'w', encoding='utf-8') as file:
                file.writelines(updated_bans)

            if ban_found:
                await inter.guild.unban(user)
                await inter.response.send_message(f"{user.mention} wurde erfolgreich entbannt!")
                self.logger.info(f"User {user.id} unbanned")
            else:
                embed = disnake.Embed(title="Fehler beim Entbannen", description=f"{user.mention} hat keinen offenen Ban.", color=disnake.Color.red())

            await inter.response.send_message(embed=embed)
        except Exception as e:
            self.logger.critical(f"An error occurred: {e}")
            await inter.response.send_message(f"Ein Fehler ist aufgetreten: {e}")

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Sr. Supporter")
    async def list_banned_users(self, inter: disnake.ApplicationCommandInteraction):
        """Listet alle gebannten Benutzer auf und zeigt den Entbannzeitpunkt an, falls vorhanden."""
        try:
            with open('bans.txt', 'r', encoding='utf-8') as file:
                bans = file.readlines()
        except FileNotFoundError:
            await inter.response.send_message("Die Bans-Datei existiert nicht.")
            return

        if not bans:
            await inter.response.send_message("Es gibt keine gebannten Benutzer.")
            return

        # Formatierung der Ausgabe
        banned_users = []
        for ban in bans:
            user_id, unban_time = ban.strip().split(',')
            unban_time = float(unban_time)
            if unban_time > 0:
                # Konvertiere Unix-Zeitstempel in ein lesbares Datum
                unban_date = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(unban_time))
                banned_users.append(f"User ID: {user_id}, Entbannzeitpunkt: {unban_date}")
            else:
                banned_users.append(f"User ID: {user_id}, Entbannzeitpunkt: Nicht festgelegt")

        # Sende die Liste der gebannten Benutzer
        await inter.response.send_message("\n".join(banned_users))

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Moderator")
    async def badword_add(self, inter: disnake.ApplicationCommandInteraction, word: str):
        """Füge ein Wort zur Badword-Liste hinzu, wenn es noch nicht existiert."""
        word = word.strip() # Entferne führende und abschließende Leerzeichen
        try:
            with open('badwords.txt', 'r', encoding='utf-8') as file:
                badwords = file.readlines()
            if word not in [line.strip() for line in badwords]:
                with open('badwords.txt', 'a', encoding='utf-8') as file:
                    file.write(f"{word}\n")
                await inter.response.send_message(f"{word} wurde zur Badword-Liste hinzugefügt.")
            else:
                await inter.response.send_message(f"{word} existiert bereits in der Badword-Liste.")
        except FileNotFoundError:
            with open('badwords.txt', 'w', encoding='utf-8') as file:
                file.write(f"{word}\n")
            await inter.response.send_message(f"{word} wurde zur Badword-Liste hinzugefügt.")

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Moderator")
    async def badword_remove(self, inter: disnake.ApplicationCommandInteraction, word: str):
        """Entferne ein Wort von der Badword-Liste."""
        try:
            with open('badwords.txt', 'r', encoding='utf-8') as file:
                lines = file.readlines()
            with open('badwords.txt', 'w', encoding='utf-8') as file:
                for line in lines:
                    if line.strip() != word:
                        file.write(line)
            await inter.response.send_message(f"{word} wurde von der Badword-Liste entfernt.")
        except FileNotFoundError:
            await inter.response.send_message("Die Badword-Liste existiert nicht.")

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Moderator")
    async def badwords_list(self, inter: disnake.ApplicationCommandInteraction):
        """Zeige die aktuelle Badword-Liste."""
        if os.path.exists('badwords.txt'):
            with open('badwords.txt', 'r', encoding='utf-8') as file:
                badwords = file.read()
            await inter.response.send_message(f"Aktuelle Badwords:\n{badwords}")
        else:
            await inter.response.send_message("Die Badword-Liste ist leer.")  

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Test-Supporter")
    async def add_user_to_ticket(self, inter: disnake.ApplicationCommandInteraction, ticket_id: int, user: disnake.User):
        """Fügt einen Benutzer zu einem Ticket-Channel hinzu."""
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
            await inter.response.send_message(f"{user.mention} wurde zum Ticket-Channel hinzugefügt.")
        except Exception as e:
            await inter.response.send_message(f"Fehler beim Hinzufügen des Benutzers: {e}") 

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Test-Supporter")
    async def note_add(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, reason: str, warn: bool = False, proof: disnake.Attachment = None, show: str = "True"):
        """Erstellt eine Notiz für einen Benutzer mit der Möglichkeit, diese als Warnung zu markieren."""
        # Überprüfe, ob ein Attachment in der Nachricht vorhanden ist
        image_path = None
        caseid = int(os.getenv("caseid"))

        avatar_url = user.avatar.url
        if avatar_url is None:
            avatar_url = user.default_avatar.url

        if proof:
            image_path = await Globalfile.save_image(proof, f"{user.id}_{caseid}")
            
        note_entry = f"{caseid}, User ID:{user.id}, Grund:{reason}"
        if image_path:
            note_entry += f", Bildpfad:{image_path}"
        if warn:
            note_entry += ", Warnung:Ja"
        else:
            note_entry += ", Warnung:Nein"
        
        note_entry += f", Show={show}"        
        
        with open("note.txt", "a", encoding="utf-8") as file:
            file.write(note_entry + "\n")
        self.logger.info(f"Note added: {note_entry}")
        
        caseid += 1
        Globalfile.update_ids(caseid)
        # Sende eine Warn-Nachricht, wenn die Note als Warnung markiert ist
        if warn:
            try:
                await user.send(f"Du hast eine Warnung erhalten: {reason}")
            except Exception as e:
                await inter.response.send_message(f"Fehler beim Senden der Warn-Nachricht: {e}")
        
        current_datetime = datetime.now()
        # Sende eine Bestätigungsnachricht
        
        embed = disnake.Embed(title=f"Notiz erstellt [{caseid-1}]", description=f"Für {user.mention} wurde eine Notiz erstellt.", color=disnake.Color.green())
        embed.set_author(name=user.name, icon_url=avatar_url)
        embed.add_field(name="Grund", value=reason, inline=False)
        if image_path:
            embed.add_field(name="Bildpfad", value=image_path, inline=False)
        if warn:
            embed.add_field(name="Warnung", value="Ja", inline=False)
        else:
            embed.add_field(name="Warnung", value="Nein", inline=False)
        embed.set_footer(text=f"ID: {user.id} - heute um {(current_datetime + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr")
        await inter.response.send_message(embed=embed)

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Test-Supporter")
    async def user_profile(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User):
        """Ruft das Profil eines Benutzers ab, einschließlich aller Notes und angehängter Bilder."""
        embed = disnake.Embed(title=f"Profil von {user.name}", description="Alle Notizen, angehängten Bilder und Banninformationen:", color=disnake.Color.blue())
        notes = []
        bans = []
        
        avatar_url = user.avatar.url
        if avatar_url is None:
            avatar_url = user.default_avatar.url  

        embed.set_author(name=user.name, icon_url=avatar_url)
        embed.set_footer(text=f"User ID: {user.id}")

        if os.path.exists("note.txt"):
            with open("note.txt", "r", encoding="utf-8") as file:
                for line in file.readlines():
                    components = line.split(", ")
                    if components[1].startswith(f"User ID:{user.id}"):
                        notes.append(line.strip())

        if os.path.exists("bans.txt"):
            with open("bans.txt", "r", encoding="utf-8") as file:
                for line in file.readlines():
                    components = line.split(", ")
                    if components[1].startswith(f"User ID:{user.id}"):
                        bans.append(line.strip())    

        if notes:
            for note in notes:
                components = note.split(", ")
                caseid = components[0]
                reason = [comp for comp in components if comp.startswith("Grund:")][0].replace("Grund:", "").strip()
                image_path = [comp for comp in components if comp.startswith("Bildpfad:")][0].replace("Bildpfad:", "").strip() if "Bildpfad:" in note else None
                warn = [comp for comp in components if comp.startswith("Warnung:")][0].replace("Warnung:", "").strip()
                show = [comp for comp in components if comp.startswith("Show:")][0].replace("Show:", "").strip() if " Show:" in note else "False"
                note_text = f"Grund: {reason}\nWarnung: {warn}"

                if components[1].startswith(f"User ID:{user.id}"):
                    if show == "True":
                        if image_path:
                            # Überprüfe, ob das Bildpfad-Format UserID_NoteID entspricht
                            if os.path.exists(f"{image_path}"):
                                # Teile den Pfad in UserID und NoteID auf
                                path, file_name = os.path.split(image_path)
                                # Füge den Dateinamen hinzu, falls vorhanden
                                note_text += f"\nBildpfad: {image_path}\nDateiname: {file_name}"
                                embed.add_field(name=f"Note [Id: {caseid}]", value=note_text, inline=False)    
                                embed.set_image(file=disnake.File(image_path))
                            else:
                                note_text += f"\nBildpfad: {image_path}\nDateiname: {file_name}\nBildpath zwar vorhanden aber kein Bild gefunden."
                                embed.add_field(name=f"Note [Id: {caseid}]", value=note_text, inline=False)

        if bans:
            for ban in bans:
                components = ban.split(", ")
                caseid = components[0]
                reason = [comp for comp in components if comp.startswith("Grund:")][0].replace("Grund:", "").strip()
                image_path = [comp for comp in components if comp.startswith("Bildpfad:")][0].replace("Bildpfad:", "").strip() if "Bildpfad:" in ban else None
                deleted_days = [comp for comp in components if comp.startswith("Deleted Days:")][0].replace("Deleted Days:", "").strip()
                datetime_unbaned = [comp for comp in components if comp.startswith("DateTime Unbaned:")][0].replace("DateTime Unbaned: ", "").strip()
                show = [comp for comp in components if comp.startswith("Show: ")][0].replace("Show:", "").strip() if "Show:" in ban else "False"
                if components[1].startswith(f"User ID:{user.id}"):
                    if show == "True":
                        ban_text = f"Grund: {reason}\nDeleted Days: {deleted_days}\nDateTime Unbaned: {datetime_unbaned}"
                        if image_path:
                            # Überprüfe, ob das Bildpfad-Format UserID_NoteID entspricht
                            if os.path.exists(f"{image_path}"):
                                # Teile den Pfad in UserID und NoteID auf
                                path, file_name = os.path.split(image_path)
                                # Füge den Dateinamen hinzu, falls vorhanden
                                ban_text += f"\nBildpfad: {image_path}\nDateiname: {file_name}"
                                embed.add_field(name=f"Bann [Id: {caseid}]", value=ban_text, inline=False)
                                embed.set_image(file=disnake.File(image_path))
                            else:
                                ban_text += f"\nBildpfad: {image_path}\nDateiname: {file_name}\nBildpath zwar vorhanden aber kein Bild gefunden."
                                embed.add_field(name=f"Bann [Id: {caseid}]", value=ban_text, inline=False)

        note_exists = any(field.name.startswith("Note") for field in embed.fields)
        if not note_exists:
            embed.add_field(name="Note", value="Keine Notes vorhanden.", inline=False)

        ban_exists = any(field.name.startswith("Bann") for field in embed.fields)
        if not ban_exists:
            embed.add_field(name="Bans", value="Keine Banns vorhanden.", inline=False)

        await inter.response.send_message(embed=embed)

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Sr. Supporter")
    async def delete_note(self, inter: disnake.ApplicationCommandInteraction, caseid: int):
        """Löscht eine Note basierend auf der Note ID."""
        try:
            with open("note.txt", "r", encoding="utf-8") as file:
                lines = file.readlines()
            with open("note.txt", "w", encoding="utf-8") as file:
                for line in lines:
                    if not line.startswith(f"{caseid},"):
                        file.write(line)
                    else:
                        # Füge "Show=False" hinzu, wenn die Note entfernt wird
                        if "Show=" not in line:
                            file.write(line.strip() + ", Show=False\n")
            await inter.response.send_message(f"Note mit der ID {caseid} wurde gelöscht.")
        except FileNotFoundError:
            await inter.response.send_message("Die Note.txt Datei existiert nicht.")
        except Exception as e:
            self.logger.critical(f"An error occurred: {e}")
            await inter.response.send_message(f"Ein Fehler ist aufgetreten: {e}")

    @commands.slash_command(guild_ids=[854698446996766730])
    @RoleHierarchy.check_permissions("Administrator") # Stellen Sie sicher, dass nur autorisierte Personen diesen Befehl ausführen können
    async def disconnect(self, inter: disnake.ApplicationCommandInteraction):
        """Schließt alle Verbindungen des Bots und beendet den Bot-Prozess."""
        await self.bot.close()
        await inter.response.send_message("Der Bot wird nun alle Verbindungen schließen und beendet werden.", ephemeral=True)

def setup(bot: commands.Bot):
    bot.add_cog(MyCommands(bot))
