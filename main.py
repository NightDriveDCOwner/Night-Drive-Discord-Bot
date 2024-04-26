import disnake
from disnake.ext import commands
from reaction import setupReaction
from join import setupJoin
from voice import setupVoice
from globalfile import setupGlobal
from moderation import setupModeration

intents = disnake.Intents.all()
bot = commands.Bot(intents=intents)

@bot.event
async def on_ready():
    print("The bot is ready!")  
   
bot.load_extension("commands")
setupReaction(bot)
setupJoin(bot)
setupVoice(bot)
setupGlobal(bot)

bot.run("MTIwODE3NTc0ODk4MDkzNjc2NA.GGk_8k.IUe5KR-MSpolnO_I7rGtx5qsE1Tr0M9fyk7gfw")