from asyncio import get_event_loop, sleep as asleep, gather
from traceback import format_exc

from aiohttp import web
from pyrogram import idle

from bot import __version__, LOGGER
from bot.config import Telegram
from bot.server import web_server
from bot.telegram import StreamBot, UserBot
from bot.telegram.clients import initialize_clients

loop = get_event_loop()

async def start_services():
    LOGGER.info(f'Initializing Surf-TG v-{__version__}')
    await asleep(1.2)

    await StreamBot.start()
    StreamBot.username = StreamBot.me.username
    LOGGER.info(f"Bot Client : [@{StreamBot.username}]")
    
    # Try to start UserBot, but continue if it fails
    if len(Telegram.SESSION_STRING) != 0:
        try:
            await UserBot.start()
            UserBot.username = UserBot.me.username or UserBot.me.first_name or UserBot.me.id
            LOGGER.info(f"User Client : {UserBot.username}")
        except Exception as e:
            LOGGER.error(f"Failed to start UserBot: {e}")
            LOGGER.warning("Continuing without UserBot. Some features may be limited.")
            LOGGER.info("Note: Use /index command in your channel to manually index files.")
    
    await asleep(1.2)
    LOGGER.info("Initializing Multi Clients")
    await initialize_clients()

    await asleep(2)
    LOGGER.info('Initalizing Surf Web Server..')
    server = web.AppRunner(await web_server())
    LOGGER.info("Server CleanUp!")
    await server.cleanup()

    await asleep(2)
    LOGGER.info("Server Setup Started !")

    await server.setup()
    await web.TCPSite(server, '0.0.0.0', Telegram.PORT).start()

    LOGGER.info("Surf-TG Started Revolving !")
    LOGGER.info(f"TMDB Integration: {'Enabled' if Telegram.TMDB_API_KEY else 'Disabled (set TMDB_API_KEY to enable)'}")
    await idle()

async def stop_clients():
    await StreamBot.stop()
    if len(Telegram.SESSION_STRING) != 0:
        try:
            await UserBot.stop()
        except Exception:
            pass  # Ignore errors if UserBot failed to start

if __name__ == '__main__':
    try:
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        LOGGER.info('Service Stopping...')
    except Exception:
        LOGGER.error(format_exc())
    finally:
        loop.run_until_complete(stop_clients())
        loop.stop()
