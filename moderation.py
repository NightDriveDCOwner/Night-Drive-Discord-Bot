import disnake
from disnake.ext import commands

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def check_message_for_badwords(self, message: disnake.Message):
        try:
            with open('badwords.txt', 'r', encoding='utf-8') as file:
                badwords = [line.strip().lower() for line in file.readlines()] # Badwords in Kleinbuchstaben
        except FileNotFoundError:
            badwords = []

        if any(badword in message.content.lower() for badword in badwords):
            notification_channel_id = 854698447113027594 # Ersetzen Sie dies durch die tatsächliche ID Ihres Kanals
            notification_message = f"Ein Benutzer hat ein Badword verwendet: {message.content}\n" \
                                   f"Von: {message.author.name} (ID: {message.author.id})\n" \
                                   f"In: {message.channel.name} (ID: {message.channel.id})"
            notification_channel = self.bot.get_channel(notification_channel_id)
            if notification_channel:
                await notification_channel.send(notification_message)

def setupModeration(bot: commands.Bot):
    bot.add_cog(Moderation(bot))                
