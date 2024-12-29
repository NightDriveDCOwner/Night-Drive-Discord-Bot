import disnake, logging
from functools import wraps
import os

class rolehierarchy:
        def __init__(self):
            # Definieren Sie die Hierarchie der Rollen in der Reihenfolge von niedrigster zu höchster Hierarchie
            self.role_hierarchy = [
                "Test-Supporter",
                "Supporter",
                "Senior Supporter",
                "Moderator",
                "Senior Moderator",
                "Administrator",
                "Leitung",
                "Co. Owner",
                "Owner"
            ]
            self.logger = logging.getLogger("rolehierarchy")
            logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper() 
            self.logger.setLevel(logging_level)
                        
            if not self.logger.handlers:
                formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
                handler = logging.StreamHandler()
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)


        def has_role_or_higher(self, member: disnake.Member, role_name: str) -> bool:
            try:
                target_role_index = self.role_hierarchy.index(role_name)
            except ValueError:
                return False

            for role in member.roles:
                if role.name in self.role_hierarchy:
                    member_role_index = self.role_hierarchy.index(role.name)
                    if member_role_index >= target_role_index:
                        return True
            return False

        async def check_role(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member, role_name: str):
            """
            Überprüft, ob ein Mitglied eine bestimmte Rolle oder eine Rolle mit höherer Hierarchie hat.

            :param member: Das Mitglied, dessen Rollen überprüft werden sollen.
            :param role_name: Der Name der Rolle, die überprüft werden soll.
            """
            role_hierarchy = rolehierarchy()
            if role_hierarchy.has_role_or_higher(member, role_name):
                await inter.response.send_message(f"{member.mention} hat die Rolle {role_name} oder eine höhere.")
            else:
                await inter.response.send_message(f"{member.mention} hat nicht die Rolle {role_name} oder eine höhere.")                

        def check_permissions(role_name: str):
            def decorator(func):
                @wraps(func)
                async def wrapper(self, inter: disnake.ApplicationCommandInteraction, *args, **kwargs):
                    role_hierarchy = rolehierarchy()
                    if not role_hierarchy.has_role_or_higher(inter.author, role_name):
                        await inter.response.send_message("Du hast nicht die erforderlichen Berechtigungen, um diesen Befehl auszuführen.", ephemeral=True)
                        return
                    return await func(self, inter, *args, **kwargs)
                return wrapper
            return decorator
