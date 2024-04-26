import disnake
import disnake.audit_logs
from disnake.ext import commands, tasks
from datetime import datetime, timedelta, timedelta
from collections import namedtuple
import asyncio
import time
import re


class Globalfile(commands.Cog):
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Globalfile, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, bot: commands.Bot):
        if not hasattr(self, 'bot'):
            self.bot = bot
            self.user_data = {}
            self.TimerMustReseted = True
            self.UserRecord = namedtuple('UserRecord', ['user','username','userid'])

    def convert_duration_to_seconds(self, duration: str) -> int:
        """Konvertiere eine Zeitangabe in Sekunden."""
        seconds = 0
        matches = re.findall(r'(\d+)([smhdj])', duration)
        for match in matches:
            value, unit = match
            if unit == 's':
                seconds += int(value)
            elif unit == 'm':
                seconds += int(value) * 60
            elif unit == 'h':
                seconds += int(value) * 3600
            elif unit == 'd':
                seconds += int(value) * 86400
            elif unit == 'j':
                seconds += int(value) * 31536000 # Ein Jahr hat etwa 365 Tage
        return seconds

    async def save_image(self, attachment, user_id):
        """Speichert ein Bild als Beweis."""
        # Hier musst du deine eigene Logik implementieren, um das Bild zu speichern
        # Zum Beispiel:
        await attachment.save(f"proofs/{user_id}_proof.png")

    @tasks.loop(seconds=60) 
    async def unban_task(self):
        """Entbanne Benutzer, deren Bannzeit abgelaufen ist."""
        current_time = time.time()
        with open('bans.txt', 'r', encoding='utf-8') as file:
            bans = file.readlines()
        to_unban = [ban.strip().split(',') for ban in bans if float(ban.strip().split(',')[1]) <= current_time]
        for member_id, _ in to_unban:
            member = await self.bot.fetch_user(int(member_id))
            guild = self.bot.get_guild(854698446996766730) # Ersetze dies durch die ID deines Servers
            await guild.unban(member)
            # Entferne den Benutzer aus der Datei
            with open('bans.txt', 'w', encoding='utf-8') as file:
                for ban in bans:
                    if ban.strip().split(',')[0] != member_id:
                        file.write(ban)

    def reset_timer(self):
        asyncio.create_task(self.clear_user_data_after_6_minutes())

    async def clear_user_data_after_6_minutes(self):
        await asyncio.sleep(6 * 60)
        self.user_data.clear()
        self.TimerMustReseted = True   

    async def admin_did_something(self, action: disnake.AuditLogAction, handleduser: disnake.user):
        DeletedbyAdmin = False
        guild = self.bot.get_guild(854698446996766730)
        async for entry in guild.audit_logs(limit=5, action=action, after=datetime.now() - timedelta(minutes=5)):                                            
            if entry.extra.count is not None:
                if self.TimerMustReseted:
                    self.reset_timer()
                    self.TimerMustReseted = False
                if entry.user.id in self.user_data:
                    if entry.extra.count > self.user_data[entry.user.id]:
                        self.user_data[entry.user.id] = entry.extra.count
                        DeletedbyAdmin = True
                        break
                    else: 
                        DeletedbyAdmin = False                        
                        break
                else:
                    self.user_data[entry.user.id] = entry.extra.count
                    DeletedbyAdmin = True
                    break  
            else:
                DeletedbyAdmin = False                                
                break

        if action == disnake.AuditLogAction.message_delete:
            if DeletedbyAdmin:
                user = entry.user
                username = user.name
                userid = user.id
            else:
                user = handleduser.author.name
                userid = handleduser.author.id     
        return self.UserRecord(user,username,userid)  

def setupGlobal(bot):
    bot.add_cog(Globalfile(bot))
