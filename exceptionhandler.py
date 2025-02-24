import logging
import os
import inspect
from functools import wraps
import disnake
import traceback

def exception_handler(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Dynamisch den Logger basierend auf dem Namen der aufrufenden Funktion setzen
        caller_class = inspect.getmodule(func).__name__
        method_name = func.__name__
        logger = logging.getLogger(caller_class)
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        logger.setLevel(logging_level)
        
        if not logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"An error occurred in {method_name}: {e}")
            logger.error(traceback.format_exc())  # Logge den vollständigen Traceback
            # Optional: Sende eine Nachricht an den Benutzer, falls 'inter' vorhanden ist
            if len(args) > 1 and hasattr(args[1], 'edit_original_response'):
                inter = args[1]
                await inter.edit_original_response(content="Ein Fehler ist aufgetreten. Bitte versuche es später erneut oder öffne ein Ticket. Über dieses erfährst du wenn der Fehler behoben wurde.")
            
            # Sende eine Nachricht an einen bestimmten Benutzer auf dem Discord-Server
            bot = args[0].bot
            user_id = int(461969832074543105)  # Setze die User-ID in der .env-Datei
            user = await bot.fetch_user(user_id)
            if user:
                await user.send(f"An error occurred in {caller_class}.{method_name}: {e}")
    return wrapper