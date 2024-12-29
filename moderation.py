import disnake, time, os, dotenv
from disnake.ext import commands
from globalfile import Globalfile
import logging
from dbconnection import DatabaseConnection
import sqlite3


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message = disnake.message
        self.userid = int
        self.logger = logging.getLogger("Moderation")
        self.db = DatabaseConnection()        
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper() 
        self.logger.setLevel(logging_level)
                
        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
               

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
            print(f"Kanal mit ID {channel_id} nicht gefunden.")
            return

        async for message in channel.history(limit=None):
            if message.id == message_id:
                await message.delete()
                print(f"Nachricht mit ID {message_id} gelöscht.")
                return

        print(f"Nachricht mit ID {message_id} nicht gefunden.")    

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

def setupModeration(bot: commands.Bot):
    bot.add_cog(Moderation(bot))                
