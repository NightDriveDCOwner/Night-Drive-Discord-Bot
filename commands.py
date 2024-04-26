import disnake, os
from disnake.ext import commands, tasks
import time
import re
from globalfile import Globalfile


class MyCommands(commands.Cog):
    """This will be for a ping command."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        Globalfile.unban_task.start(self)

    def cog_unload(self):
        Globalfile.unban_task.cancel()        

    @commands.slash_command()
    async def ping(self, inter: disnake.ApplicationCommandInteraction):
        """Get the bot's current websocket latency."""
        await inter.response.send_message(f"Pong! {round(self.bot.latency * 1000)}ms")

    @commands.slash_command(guild_ids=[854698446996766730])
    async def server(inter):
        await inter.response.send_message(
            f"Server name: {inter.guild.name}\nTotal members: {inter.guild.member_count}"
        )    
            
    @commands.slash_command(guild_ids=[854698446996766730])
    @commands.has_permissions(ban_members=True)    
    async def ban(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member, reason: str = "No reason provided", duration: str = "0s", delete_days: int = 0):
        """Banne einen Benutzer und speichere ein Bild als Beweis."""
        # Überprüfe, ob ein Attachment in der Nachricht vorhanden ist
        if inter.message.attachments:
            # Speichere das Bild
            for attachment in inter.message.attachments:
                await Globalfile.save_image(attachment, member.id)
                
        duration_seconds = Globalfile.convert_duration_to_seconds(duration)
        with open('bans.txt', 'a', encoding='utf-8') as file:
            file.write(f"{member.id},{time.time() + duration_seconds}\n")

        # Banne den Benutzer
        await member.ban(reason=reason, delete_message_days=delete_days)
        
        # Sende eine Nachricht, um den Benutzer zu informieren
        await inter.response.send_message(f"{member.mention} wurde erfolgreich gebannt!")

    @commands.slash_command(guild_ids=[854698446996766730])
    @commands.has_permissions(ban_members=True)
    async def unban(self, inter: disnake.ApplicationCommandInteraction, user_id: int):
        """Entbanne einen Benutzer von diesem Server."""
        try:
            user = await self.bot.fetch_user(user_id)
            await inter.guild.unban(user)
            await inter.response.send_message(f"{user.mention} wurde erfolgreich entbannt!")
        except Exception as e:
            await inter.response.send_message(f"Ein Fehler ist aufgetreten: {e}")
   
    @commands.slash_command(guild_ids=[854698446996766730])
    @commands.has_permissions(manage_messages=True)
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
    @commands.has_permissions(manage_messages=True)
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
    @commands.has_permissions(manage_messages=True)
    async def badwords_list(self, inter: disnake.ApplicationCommandInteraction):
        """Zeige die aktuelle Badword-Liste."""
        if os.path.exists('badwords.txt'):
            with open('badwords.txt', 'r', encoding='utf-8') as file:
                badwords = file.read()
            await inter.response.send_message(f"Aktuelle Badwords:\n{badwords}")
        else:
            await inter.response.send_message("Die Badword-Liste ist leer.")  

    @commands.slash_command(guild_ids=[854698446996766730])
    async def user(inter):
        await inter.response.send_message(f"Your tag: {inter.author}\nYour ID: {inter.author.id}")    

    @commands.slash_command(guild_ids=[854698446996766730])
    async def user(inter):
        await inter.response.send_message(f"Your tag: {inter.author}\nYour ID: {inter.author.id}")                                    


def setup(bot: commands.Bot):
    bot.add_cog(MyCommands(bot))