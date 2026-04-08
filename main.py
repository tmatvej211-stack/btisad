import logging
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import FSInputFile, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram import F
from aiogram.utils.markdown import hbold, hcode
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
from collections import defaultdict
from pathlib import Path

API_TOKEN = '8664269263:AAGBj1U7zfKgyslXNmgJOTVuMbpnh-o_AJE'
DATA_FILE = 'bot_data.json'
LINKS = {
    "android": "https://t.me/GidBaseBot",
    "ios": "https://t.me/GidBaseBot",
    "news": "https://t.me/nfthom"
}

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Инициализация диспетчера
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Классы состояний
class AddGarantState(StatesGroup):
    waiting_for_garant_info = State()

class AddScammerState(StatesGroup):
    waiting_for_scammer_info = State()

class ReportState(StatesGroup):
    waiting_for_report_text = State()
    waiting_for_report_proof = State()

# Загрузка данных из файла
def load_data():
    try:
        if Path(DATA_FILE).exists():
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Добавляем обязательные ключи, если их нет
                if "admins" not in data:
                    data["admins"] = [123456789, 7674627532]
                if "garants" not in data:
                    data["garants"] = {}
                if "scammers" not in data:
                    data["scammers"] = {}
                if "user_searches" not in data:
                    data["user_searches"] = {}
                if "reports" not in data:
                    data["reports"] = []
                return data
    except Exception as e:
        logging.error(f"Ошибка загрузки данных: {e}")
    
    return {
        "admins": [123456789, 7674627532],
        "garants": {},
        "scammers": {},
        "user_searches": {},
        "reports": []
    }

# Сохранение данных в файл
def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения данных: {e}")

# Инициализация данных
bot_data = load_data()
ADMINS = bot_data["admins"]
garants = defaultdict(dict, bot_data["garants"])
scammers = defaultdict(int, bot_data["scammers"])
user_searches = defaultdict(int, bot_data["user_searches"])
reports = bot_data["reports"]

async def send_photo_or_text(message: types.Message, photo_path: str, caption: str):
    try:
        photo = FSInputFile(photo_path)
        await message.answer_photo(photo=photo, caption=caption)
    except FileNotFoundError:
        await message.answer(caption)
    except Exception as e:
        logging.error(f"Ошибка отправки фото: {e}")
        await message.answer(caption)

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    welcome_text = (
        "🛡 Анти-скам база гарантов\n\n"
        "🔍 <b>Проверенный список гарантов</b> 🔍\n"
        "Все гаранты проходят многоэтапную проверку:\n"
        "1. Верификация личности\n"
        "2. Проверка истории сделок\n"
        "3. Депозит безопасности\n"
        "4. Отзывы клиентов\n\n"
        "⚠️ <b>Внимание!</b> Любые другие гаранты могут быть мошенниками!\n\n"
        "Для проверки пользователя отправьте его @username или ID"
    )
    await send_photo_or_text(message, "picturee.jpeg", welcome_text)

@dp.message(Command("report"))
async def start_report(message: types.Message, state: FSMContext):
    await message.answer(
        "📝 Опишите вашу жалобу (укажите @username или ID нарушителя и суть проблемы):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(ReportState.waiting_for_report_text)

@dp.message(ReportState.waiting_for_report_text)
async def process_report_text(message: types.Message, state: FSMContext):
    await state.update_data(report_text=message.text)
    await message.answer(
        "📎 Прикрепите доказательства (скриншот, фото или документ), "
        "или нажмите /skip если доказательств нет",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="/skip")]],
            resize_keyboard=True
        )
    )
    await state.set_state(ReportState.waiting_for_report_proof)

@dp.message(Command("skip"), ReportState.waiting_for_report_proof)
async def skip_report_proof(message: types.Message, state: FSMContext):
    report_data = await state.get_data()
    await process_report(message, report_data, None)
    await state.clear()

@dp.message(ReportState.waiting_for_report_proof, F.photo | F.document)
async def process_report_with_proof(message: types.Message, state: FSMContext):
    report_data = await state.get_data()
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    await process_report(message, report_data, file_id)
    await state.clear()

async def process_report(message: types.Message, report_data: dict, proof_file_id: str = None):
    try:
        report_text = report_data.get("report_text", "")
        reporter = message.from_user
        report = {
            "text": report_text,
            "reporter_id": reporter.id,
            "reporter_name": reporter.full_name,
            "proof": proof_file_id,
            "status": "new"
        }
        
        reports.append(report)
        bot_data["reports"] = reports
        save_data(bot_data)
        
        # Отправка уведомления админам
        for admin_id in ADMINS:
            try:
                admin_message = (
                    f"🚨 <b>Новая жалоба</b>\n\n"
                    f"👤 От: {reporter.full_name} (@{reporter.username if reporter.username else 'нет'})\n"
                    f"🆔 ID: {reporter.id}\n\n"
                    f"📝 Текст жалобы:\n<code>{report_text}</code>\n\n"
                    f"Статус: 🆕 Новая"
                )
                
                if proof_file_id:
                    if proof_file_id.startswith("AgAC"):  # Это фото
                        await bot.send_photo(
                            chat_id=admin_id,
                            photo=proof_file_id,
                            caption=admin_message
                        )
                    else:  # Это документ
                        await bot.send_document(
                            chat_id=admin_id,
                            document=proof_file_id,
                            caption=admin_message
                        )
                else:
                    await bot.send_message(chat_id=admin_id, text=admin_message)
            except Exception as e:
                logging.error(f"Не удалось отправить жалобу админу {admin_id}: {e}")
        
        await message.answer(
            "✅ Ваша жалоба отправлена администраторам. Спасибо за бдительность!",
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        logging.error(f"Ошибка обработки жалобы: {e}")
        await message.answer("❌ Произошла ошибка при обработке вашей жалобы")

@dp.message(Command("addgar"), F.from_user.id.in_(ADMINS))
async def add_garant_command(message: types.Message, state: FSMContext):
    await message.answer("Отправьте username гаранта (например, @username) или его ID:")
    await state.set_state(AddGarantState.waiting_for_garant_info)

@dp.message(AddGarantState.waiting_for_garant_info)
async def process_garant_info(message: types.Message, state: FSMContext):
    try:
        garant_info = message.text.strip()
        
        if garant_info.startswith('@'):
            username = garant_info[1:]
            garants[username] = {"id": username, "searches": 0}
            await message.answer(f"Гарант @{username} добавлен в базу!")
        elif garant_info.isdigit():
            garants[f"id_{garant_info}"] = {"id": int(garant_info), "searches": 0}
            await message.answer(f"Гарант с ID {garant_info} добавлен в базу!")
        else:
            await message.answer("Некорректный формат. Отправьте username (@username) или ID (только цифры)")
        
        bot_data["garants"] = dict(garants)
        save_data(bot_data)
    except Exception as e:
        logging.error(f"Ошибка добавления гаранта: {e}")
        await message.answer("❌ Произошла ошибка при добавлении гаранта")
    finally:
        await state.clear()

@dp.message(Command("del"), F.from_user.id.in_(ADMINS))
async def add_scammer_command(message: types.Message, state: FSMContext):
    await message.answer("Отправьте username мошенника (например, @username) или его ID:")
    await state.set_state(AddScammerState.waiting_for_scammer_info)

@dp.message(AddScammerState.waiting_for_scammer_info)
async def process_scammer_info(message: types.Message, state: FSMContext):
    try:
        scammer_info = message.text.strip()
        
        if scammer_info.startswith('@'):
            username = scammer_info[1:]
            scammers[username] = 0
            await message.answer(f"Мошенник @{username} добавлен в базу!")
        elif scammer_info.isdigit():
            scammers[f"id_{scammer_info}"] = 0
            await message.answer(f"Мошенник с ID {scammer_info} добавлен в базу!")
        else:
            await message.answer("Некорректный формат. Отправьте username (@username) или ID (только цифры)")
        
        bot_data["scammers"] = dict(scammers)
        save_data(bot_data)
    except Exception as e:
        logging.error(f"Ошибка добавления мошенника: {e}")
        await message.answer("❌ Произошла ошибка при добавлении мошенника")
    finally:
        await state.clear()

@dp.message()
async def check_user(message: types.Message):
    try:
        text = message.text.strip()
        search_key = text.lower()
        user_searches[search_key] += 1
        bot_data["user_searches"] = dict(user_searches)
        save_data(bot_data)

        # Форматирование ссылок
        android_link = f'<a href="{LINKS["android"]}">📱 Android</a>'
        ios_link = f'<a href="{LINKS["ios"]}">🍎 Apple</a>'
        news_link = f'<a href="{LINKS["news"]}">❇️ NFT Подарки | Новости</a>'

        # Проверка на гаранта
        if text.startswith('@'):
            username = text[1:]
            if username in garants:
                garants[username]["searches"] += 1
                response = (
                    f"🛡 ТОП Гарант @{username} | ID: {hcode(garants[username]['id'])}\n"
                    f"👀 Искали: {garants[username]['searches']} раз\n\n"
                    f"Надежный гарант ✅\n"
                    f"Комиссия: 2% | 100₽ мин.\n"
                    f"Все ресурсы: @GidBaseBot\n\n"
                    f"🔻 Вечные Ссылки 🔻\n"
                    f"┌ {android_link}\n"
                    f"└ {ios_link}\n\n"
                    f"Самые актуальные новости нфт:\n"
                    f"{news_link}"
                )
                await send_photo_or_text(message, "picturee.jpeg", response)
                return
        
        # Проверка на мошенника
        if text.startswith('@'):
            username = text[1:]
            if username in scammers:
                scammers[username] += 1
                response = (
                    f"🔴 МОШЕННИК: @{username} | ID: {hcode(scammers.get(f'id_{username}', 'N/A'))}\n"
                    f"👀 Искали: {scammers[username]} раз\n\n"
                    f"❌ Пользователь мошенник! Найден в базе @GidBaseBot\n"
                    f"Был замечен в скаме. Добавьте его в чс, чтобы не тратить свое время.\n\n"
                    f"🔻 Вечные Ссылки 🔻\n"
                    f"┌ {android_link}\n"
                    f"└ {ios_link}\n\n"
                    f"Самые актуальные новости нфт:\n"
                    f"{news_link}"
                )
                await send_photo_or_text(message, "pic.jpg", response)
                return
        
        # Обычный пользователь
        if text.startswith('@') or text.isdigit():
            username = text[1:] if text.startswith('@') else text
            response = (
                f"🟠 @{username} | ID: {hcode(username)}\n"
                f"👀 Искали: {user_searches[search_key]} раз\n\n"
                f"❓ Пользователь не найден в базе мошенников. Рекомендуем проводить все сделки с надежным гарантом.\n\n"
                f"🔻 Вечные Ссылки 🔻\n"
                f"┌ {android_link}\n"
                f"└ {ios_link}\n\n"
                f"Самые актуальные новости нфт:\n"
                f"{news_link}"
            )
            await send_photo_or_text(message, "pic2.jpg", response)
        else:
            await message.answer("Отправьте @username пользователя или его ID для проверки")
    except Exception as e:
        logging.error(f"Ошибка проверки пользователя: {e}")
        await message.answer("❌ Произошла ошибка при проверке пользователя")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
