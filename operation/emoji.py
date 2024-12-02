import os
import aiohttp
import base64
import asyncio
import hashlib
import json
from tqdm import tqdm
from termcolor import colored

class EmojiManager:
    def __init__(self, bot_token, application_id, image_directory, cache_file="emoji_cache.json", log_file="emoji_errors.log"):
        self.bot_token = bot_token
        self.application_id = application_id
        self.image_directory = image_directory
        self.base_url = "https://discord.com/api/v10"
        self.cache_file = cache_file
        self.log_file = log_file
        self.emojis_cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r") as file:
                return json.load(file)
        return {}

    def _save_cache(self):
        with open(self.cache_file, "w") as file:
            json.dump(self.emojis_cache, file, indent=4)

    def _generate_emoji_key(self, image_path):
        try:
            with open(image_path, "rb") as image_file:
                image_hash = hashlib.md5(image_file.read()).hexdigest()
                return image_hash
        except Exception as e:
            self._log_error(f"Ошибка при генерации ключа для изображения {image_path}: {e}")
            return None

    async def _image_to_base64(self, image_path):
        if not os.path.exists(image_path):
            self._log_error(f"Ошибка: Файл {image_path} не существует.")
            return None
        try:
            with open(image_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded_image
        except Exception as e:
            self._log_error(f"Ошибка при чтении файла {image_path}: {e}")
            return None

    async def _get_application_emojis(self, session):
        url = f"{self.base_url}/applications/{self.application_id}/emojis"
        headers = {"Authorization": f"Bot {self.bot_token}"}
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                emojis = await response.json()
                return emojis if isinstance(emojis, list) else emojis.get("items", [])
            else:
                self._log_error(f"Ошибка при получении эмодзи: {response.status}, {await response.text()}")
                return []

    async def _create_application_emoji(self, session, image_path, emoji_name):
        url = f"{self.base_url}/applications/{self.application_id}/emojis"
        headers = {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json"
        }
        image_base64 = await self._image_to_base64(image_path)
        if not image_base64:
            return None

        data = {
            "name": emoji_name,
            "image": f"data:image/png;base64,{image_base64}"
        }

        async with session.post(url, headers=headers, json=data) as response:
            if response.status == 201:
                emoji_data = await response.json()
                emoji_key = self._generate_emoji_key(image_path)
                if emoji_key:
                    self.emojis_cache[emoji_name] = {'id': emoji_data['id'], 'key': emoji_key}
                print(colored(f"Эмодзи {emoji_name} успешно создано. ID: {emoji_data['id']}", 'green'))
                self._save_cache()
                return emoji_data
            else:
                error_message = await response.text()
                if "name" in error_message and "STRING_TYPE_REGEX" in error_message:
                    print(colored(f"Ошибка: Неверное имя эмодзи '{emoji_name}' (не соответствует формату): {response.status}, {error_message}", 'red'))
                else:
                    print(colored(f"Ошибка при создании эмодзи {emoji_name}: {response.status}, {error_message}", 'red'))
                return None

    async def _delete_emoji(self, session, emoji_id):
        url = f"{self.base_url}/applications/{self.application_id}/emojis/{emoji_id}"
        headers = {"Authorization": f"Bot {self.bot_token}"}
        async with session.delete(url, headers=headers) as response:
            if response.status == 204:
                print(colored(f"Эмодзи с ID {emoji_id} успешно удалено.", 'green'))
            else:
                error_text = await response.text()
                self._log_error(f"Ошибка при удалении эмодзи с ID {emoji_id}: {response.status}, {error_text}")

    def _log_error(self, message):
        """Логирование ошибок в файл."""
        print(colored(f"Ошибка: {message}", 'red'))
        with open(self.log_file, "a") as log:
            log.write(message + "\n")

    async def process_images_in_directory(self):
        print(colored(f"Начинаем обработку изображений из директории {self.image_directory}.", 'yellow'))

        async with aiohttp.ClientSession() as session:
            existing_emojis = await self._get_application_emojis(session)

            image_files = [f for f in os.listdir(self.image_directory) if f.endswith((".png", ".jpg", ".jpeg", ".gif"))]
            image_names_in_directory = set(os.path.splitext(f)[0] for f in image_files)

            emojis_to_delete = [emoji_name for emoji_name in self.emojis_cache if emoji_name not in image_names_in_directory]

            for emoji_name in emojis_to_delete:
                emoji_id = self.emojis_cache[emoji_name]['id']
                print(colored(f"Эмодзи {emoji_name} больше нет в директории, удаляем...", 'red'))
                await self._delete_emoji(session, emoji_id)
                del self.emojis_cache[emoji_name]

            self._save_cache()

            for filename in tqdm(image_files, desc=colored("Обработка изображений", 'white'), unit="файл"):
                image_path = os.path.join(self.image_directory, filename)
                emoji_name = os.path.splitext(filename)[0]

                emoji_exists = any(emoji["name"] == emoji_name for emoji in existing_emojis)
                if emoji_exists:
                    existing_emoji = next((emoji for emoji in existing_emojis if emoji["name"] == emoji_name), None)
                    existing_emoji_key = self.emojis_cache.get(emoji_name, {}).get('key')
                    new_emoji_key = self._generate_emoji_key(image_path)
                    
                    if existing_emoji and existing_emoji_key != new_emoji_key:
                        print(colored(f"Эмодзи с именем {emoji_name} отличается, заменяем...", 'yellow'))
                        await self._delete_emoji(session, existing_emoji["id"])
                        await self._create_application_emoji(session, image_path, emoji_name)
                    else:
                        print(colored(f"Эмодзи с именем {emoji_name} уже существует и актуально, не заменяем.", 'green'))
                else:
                    await self._create_application_emoji(session, image_path, emoji_name)
