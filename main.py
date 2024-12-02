import logging
import asyncio
from operation.emoji import EmojiManager
from config import settings

logging.basicConfig(  
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

async def main():
    if not settings.BOT_TOKEN or not settings.APPLICATION_ID:
        logging.error("Ошибка: Необходимо указать BOT_TOKEN и APPLICATION_ID.")
        return
    
    emoji_manager = EmojiManager(settings.BOT_TOKEN, settings.APPLICATION_ID, settings.IMAGE_DIRECTORY)
    await emoji_manager.process_images_in_directory()

if __name__ == "__main__":
    asyncio.run(main())
