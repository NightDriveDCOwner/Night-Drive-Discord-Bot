import discord
from discord.ext import commands

class Main(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='/')
        self.token = 'MTIwODE3NTc0ODk4MDkzNjc2NA.GQ_h32.sARzEmzKbn5K0r_wmSdY0cXTyZEBXCkyzmS8ro'
        self.status = 'test'

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        await self.change_presence(activity=discord.Game(name=self.status))
        bot.load_extension('reaction')
        bot.load_extension('join')

        # Du kannst hier deinen Code für das Hinzufügen von Event-Listenern einfügen
        # z.B. self.add_listener(DeinListener())

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

if __name__ == "__main__":
    bot = Main()
    bot.run(bot.token)