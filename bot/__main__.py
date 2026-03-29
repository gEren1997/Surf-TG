from asyncio import get_event_loop, sleep as asleep
from traceback import format_exc

from aiohttp import web
from pyrogram import idle
from pyrogram.errors import FloodWait

from bot import __version__, LOGGER
from bot.config import Telegram
from bot.server import web_server
from bot.telegram import StreamBot, UserBot
from bot.telegram.clients import initialize_clients

loop = get_event_loop()

async def start_services():
    LOGGER.info(f'Initializing Surf-TG v-{__version__}')
    await asleep(1.2)

    # Start StreamBot with flood wait handling
    try:
        await StreamBot.start()
        StreamBot.username = StreamBot.me.username
        LOGGER.info(f"Bot Client : [@{StreamBot.username}]")
    except FloodWait as e:
        LOGGER.error(f"TELEGRAM FLOOD WAIT: Must wait {e.value} seconds ({e.value//60} minutes)")
        LOGGER.error("STOP THE SERVICE NOW and redeploy after the wait time!")
        return False  # Return False to signal we shouldn't continue
    except Exception as e:
        LOGGER.error(f"Failed to start Bot: {e}")
        return False

    # Try UserBot if session string exists and looks valid
    if Telegram.SESSION_STRING and len(str(Telegram.SESSION_STRING)) > 50:
        try:
            await UserBot.start()
            UserBot.username = UserBot.me.username or UserBot.me.first_name or UserBot.me.id
            LOGGER.info(f"User Client : {UserBot.username}")
        except FloodWait as e:
            LOGGER.warning(f"UserBot FloodWait: {e.value}s - continuing without UserBot")
        except Exception as e:
            LOGGER.error(f"UserBot failed: {e} - continuing without it")
    else:
        LOGGER.info("No SESSION_STRING - running in manual mode (use /index command)")

    await asleep(1.2)
    LOGGER.info("Initializing Multi Clients")
    try:
        await initialize_clients()
    except Exception as e:
        LOGGER.error(f"Multi-client init warning: {e}")

    await asleep(2)
    LOGGER.info('Initializing Web Server..')
    
    try:
        server = web.AppRunner(await web_server())
        await server.cleanup()
        await asleep(2)
        await server.setup()
        await web.TCPSite(server, '0.0.0.0', Telegram.PORT).start()

        LOGGER.info("=" * 50)
        LOGGER.info("✅ Surf-TG Started Successfully!")
        LOGGER.info(f"TMDB: {'✅' if Telegram.TMDB_API_KEY else '❌'} | UserBot: {'✅' if Telegram.SESSION_STRING else '❌'}")
        LOGGER.info("=" * 50)
        
        await idle()
        return True
        
    except Exception as e:
        LOGGER.error(f"Web server error: {e}")
        return False

async def stop_clients():
    """Safely stop clients - ignore errors if they weren't started"""
    try:
        await StreamBot.stop()
    except Exception:
        pass  # Already stopped or never started
    
    if Telegram.SESSION_STRING:
        try:
            await UserBot.stop()
        except Exception:
            pass  # Already stopped or never started

if __name__ == '__main__':
    success = False
    try:
        success = loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        LOGGER.info('Service Stopping...')
    except Exception:
        LOGGER.error(format_exc())
    finally:
        # Always try to cleanup, but don't crash if it fails
        try:
            loop.run_until_complete(stop_clients())
        except Exception:
            pass
        
        if not success:
            # Exit with error code so Koyeb knows it failed
            # But use sys.exit to prevent automatic restart spam
            import sys
            sys.exit(1)
        
        loop.stop()
