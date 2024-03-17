import discord
from discord.ext import commands
from join import Join
from reaction import Reaction

class Main(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.dm_messages = True        
        intents.guilds = True        
        intents.guild_messages = True
        intents.moderation = True        
        intents.message_content = True
        intents.webhooks = True
        intents.guild_reactions = True
        intents.emojis_and_stickers = True
        
        super().__init__(command_prefix='/', intents=intents)
        self.token = 'MTIwODE3NTc0ODk4MDkzNjc2NA.GQ_h32.sARzEmzKbn5K0r_wmSdY0cXTyZEBXCkyzmS8ro'
        self.status = discord.Status.online
        self.activity = discord.Game(name='test')        

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        await self.change_presence(status=self.status, activity=self.activity)
        await self.add_cogs()

    async def add_cogs(self):
        await self.add_cog(Reaction(self))
        await self.add_cog(Join(self))


    async def on_connect(self):
        print('Bot is connected.')

    async def on_disconnect(self):
        print('Bot is disconnected.')

    async def on_error(self, event, *args, **kwargs):
        print('An error occurred:', event)

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send('Unknown command.')

    async def on_message(self, message):
        if message.author == self.user:
            return
        await self.process_commands(message)

    async def on_message_delete(self, message):
        pass

    async def on_message_edit(self, before, after):
        pass

if __name__ == "__main__":
    bot = Main()
    bot.run(bot.token)
