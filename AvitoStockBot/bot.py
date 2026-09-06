import asyncio
import logging
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# --- НАСТРОЙКИ ---
TOKEN = "8742473118:AAGkMqeDhWltLmVt4QwTlVIGDpOHBeLe7Uc"  # ЗАМЕНИТЕ НА СВОЙ ТОКЕН
ADMIN_ID = 5212631029  # ВАШ TELEGRAM ID (узнать у @userinfobot)

# --- ИНИЦИАЛИЗАЦИЯ ---
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- ФАЙЛ ДЛЯ ХРАНЕНИЯ КАТАЛОГА ---
DATA_FILE = "catalog_data.json"

# --- ЗАГРУЗКА / СОХРАНЕНИЕ ДАННЫХ ---
def load_catalog():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_catalog(catalog):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

catalog = load_catalog()

# --- ГОТОВЫЕ КАТЕГОРИИ (кнопки) ---
CATEGORIES = ["👕 Одежда", "📱 Техника", "👟 Обувь", "💎 Аксессуары"]

# --- ПОДКАТЕГОРИИ ---
CLOTHING_SUBCATEGORIES = [
    "👕 Футболки", "👖 Брюки", "👖 Джинсы", "🧥 Кофты", "👕 Свитшоты", 
    "🧥 Худи", "🧥 Бомберы", "🧥 Куртки", "🧥 Пальто", "👔 Рубашки", 
    "🩳 Шорты", "🧦 Носки", "👙 Бельё", "🧢 Головные уборы"
]

TECH_SUBCATEGORIES = [
    "📱 iPhone", "📱 Android", "📱 Планшеты", "💻 Ноутбуки", "🎧 Наушники", "🔌 Аксессуары"
]

# --- СОСТОЯНИЯ ---
class AddItemState(StatesGroup):
    choosing_category = State()
    choosing_subcategory = State()
    entering_name = State()
    entering_size = State()
    entering_price = State()
    entering_stock = State()
    entering_photo = State()

class AddCategoryState(StatesGroup):
    name = State()

# --- КЛАВИАТУРЫ ---
def get_main_keyboard():
    buttons = [
        [KeyboardButton(text="📋 Мой каталог")],
        [KeyboardButton(text="➕ Добавить товар")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="❓ Помощь")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_start_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🛍️ Смотреть каталог", callback_data="view_catalog")],
        [InlineKeyboardButton(text="📞 Связаться с продавцом", url="https://t.me/ваш_ник")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_categories_keyboard():
    keyboard = []
    for cat in CATEGORIES:
        keyboard.append([InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")])
    keyboard.append([InlineKeyboardButton(text="➕ Своя категория", callback_data="new_category")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_subcategories_keyboard(category):
    keyboard = []
    
    if category == "👕 Одежда":
        subcats = CLOTHING_SUBCATEGORIES
    elif category == "📱 Техника":
        subcats = TECH_SUBCATEGORIES
    else:
        subcats = list(catalog.get(category, {}).keys()) if category in catalog else []
    
    for subcat in subcats:
        keyboard.append([InlineKeyboardButton(text=subcat, callback_data=f"sub_{category}_{subcat}")])
    
    if category in catalog:
        for subcat in catalog[category].keys():
            if subcat not in subcats:
                keyboard.append([InlineKeyboardButton(text=subcat, callback_data=f"sub_{category}_{subcat}")])
    
    keyboard.append([InlineKeyboardButton(text="➕ Своя подкатегория", callback_data=f"new_sub_{category}")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_categories")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_items_keyboard(category, subcategory):
    keyboard = []
    items = catalog[category][subcategory]
    for item_name, data in items.items():
        status = f"✅ {data['stock']} шт" if data['stock'] > 0 else "❌ Нет"
        keyboard.append([InlineKeyboardButton(
            text=f"{item_name} ({data['size']}) - {data['price']}₽ {status}",
            callback_data=f"item_{category}_{subcategory}_{item_name}"
        )])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_sub_{category}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_skip_photo_keyboard():
    keyboard = [[InlineKeyboardButton(text="⏭️ Пропустить фото", callback_data="skip_photo")]]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def count_items():
    total = 0
    for category in catalog.values():
        for subcat in category.values():
            total += len(subcat)
    return total

def get_catalog_stats():
    stats = []
    for category, subcats in catalog.items():
        count = sum(len(items) for items in subcats.values())
        stats.append(f"📁 {category}: {count} товаров")
    return "\n".join(stats) if stats else "📭 Каталог пуст"

# --- КОМАНДА /start (УЛУЧШЕННАЯ) ---
@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID:
        # --- ДЛЯ ПОКУПАТЕЛЯ ---
        if not catalog:
            await message.answer(
                "🛍️ **Добро пожаловать в магазин!**\n\n"
                "К сожалению, каталог пока пуст.\n"
                "Загляните позже — скоро появятся новинки! ✨"
            )
            return
        
        # Красивое приветствие для покупателя
        welcome_text = (
            "🛍️ **Добро пожаловать в магазин AvitoStockBot!**\n\n"
            "Здесь вы можете посмотреть каталог товаров, "
            "узнать цены, размеры и наличие.\n\n"
            f"📦 **В каталоге:**\n{get_catalog_stats()}\n\n"
            "Выберите действие ниже 👇"
        )
        
        await message.answer(
            welcome_text,
            reply_markup=get_start_keyboard()
        )
        return
    
    # --- ДЛЯ ПРОДАВЦА (АДМИНИСТРАТОРА) ---
    await state.clear()
    welcome_text = (
        "👋 **Здравствуйте, продавец!**\n\n"
        "Я **AvitoStockBot** — ваш помощник для учёта товаров на Авито.\n\n"
        "📋 **Что я умею:**\n"
        "✅ Создавать каталог с категориями\n"
        "✅ Добавлять товары с фото, размерами, ценами\n"
        "✅ Показывать покупателям наличие\n"
        "✅ Давать готовые ответы\n\n"
        f"📦 **Товаров в каталоге:** {count_items()}\n\n"
        "Используйте кнопки ниже 👇"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard()
    )

# --- КНОПКА "СМОТРЕТЬ КАТАЛОГ" ---
@dp.callback_query(lambda c: c.data == "view_catalog")
async def view_catalog(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer(
        "🛍️ **Каталог товаров**\n\nВыберите категорию:",
        reply_markup=get_categories_keyboard()
    )
    await callback.answer()

# --- ОБРАБОТКА ГЛАВНЫХ КНОПОК (ПРОДАВЕЦ) ---
@dp.message(lambda message: message.text == "📋 Мой каталог")
async def show_my_catalog(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    if not catalog:
        await message.answer("📭 Каталог пуст. Нажмите «➕ Добавить товар».")
        return
    
    text = "📋 **ВАШ КАТАЛОГ:**\n\n"
    for category, subcats in catalog.items():
        text += f"📁 {category}:\n"
        total_items = 0
        for subcat, items in subcats.items():
            count = len(items)
            total_items += count
            text += f"  └─ {subcat}: {count} товаров\n"
        text += f"  Всего: {total_items} товаров\n\n"
    
    await message.answer(text)

@dp.message(lambda message: message.text == "➕ Добавить товар")
async def add_item_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    await state.set_state(AddItemState.choosing_category)
    await message.answer(
        "📁 **Выберите категорию** для добавления товара:",
        reply_markup=get_categories_keyboard()
    )

@dp.message(lambda message: message.text == "📊 Статистика")
async def show_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    total_items = 0
    total_stock = 0
    
    for category, subcats in catalog.items():
        for subcat, items in subcats.items():
            total_items += len(items)
            for item_data in items.values():
                total_stock += item_data.get("stock", 0)
    
    text = (
        f"📊 **СТАТИСТИКА КАТАЛОГА**\n\n"
        f"📁 Категорий: {len(catalog)}\n"
        f"📦 Всего товаров: {total_items}\n"
        f"📦 Общее количество: {total_stock} шт\n\n"
        f"📋 **Детали:**\n{get_catalog_stats()}"
    )
    await message.answer(text)

@dp.message(lambda message: message.text == "❓ Помощь")
async def show_help(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    await message.answer(
        "❓ **ПОМОЩЬ ПО БОТУ**\n\n"
        "📋 **Кнопки:**\n"
        "• «Мой каталог» — просмотр всех товаров\n"
        "• «Добавить товар» — создать категорию и товар\n"
        "• «Статистика» — общая информация\n\n"
        "🛠️ **Как добавить товар:**\n"
        "1️⃣ Нажмите «Добавить товар»\n"
        "2️⃣ Выберите категорию из кнопок\n"
        "3️⃣ Выберите подкатегорию\n"
        "4️⃣ Введите название товара\n"
        "5️⃣ Введите размер (S, M, L, XL, 42, 44, или «—»)\n"
        "6️⃣ Введите цену (только число)\n"
        "7️⃣ Введите количество (только число)\n"
        "8️⃣ Загрузите фото (можно пропустить)\n\n"
        "📌 **Важно:** все данные сохраняются автоматически!"
    )

# --- СОЗДАНИЕ НОВОЙ КАТЕГОРИИ ---
@dp.callback_query(lambda c: c.data == "new_category")
async def new_category_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddCategoryState.name)
    await callback.message.edit_text("✏️ **Напишите название новой категории:**\n(например: «Обувь» или «Аксессуары»)")
    await callback.answer()

@dp.message(AddCategoryState.name)
async def process_new_category(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    category_name = message.text.strip()
    
    if category_name in catalog:
        await message.answer(f"⚠️ Категория «{category_name}» уже существует.")
        return
    
    if category_name in CATEGORIES:
        await message.answer(f"⚠️ Категория «{category_name}» уже есть в списке.")
        return
    
    catalog[category_name] = {}
    save_catalog(catalog)
    CATEGORIES.append(category_name)
    
    await state.clear()
    await message.answer(
        f"✅ **Категория «{category_name}» создана!**\n\n"
        f"Теперь нажмите «➕ Добавить товар» и выберите её.",
        reply_markup=get_main_keyboard()
    )

# --- ВЫБОР КАТЕГОРИИ ---
@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def select_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.replace("cat_", "")
    
    if callback.from_user.id == ADMIN_ID:
        await state.update_data(category=category)
        await state.set_state(AddItemState.choosing_subcategory)
        await callback.message.edit_text(
            f"📁 **Категория:** {category}\n\n"
            f"**Выберите подкатегорию:**",
            reply_markup=get_subcategories_keyboard(category)
        )
    else:
        if category in catalog:
            await callback.message.edit_text(
                f"📁 **Категория:** {category}\n\n"
                f"**Выберите подкатегорию:**",
                reply_markup=get_subcategories_keyboard(category)
            )
    await callback.answer()

# --- ВЫБОР ПОДКАТЕГОРИИ ---
@dp.callback_query(lambda c: c.data.startswith("sub_"))
async def select_subcategory(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.replace("sub_", "").split("_", 1)
    category = parts[0]
    subcategory = parts[1] if len(parts) > 1 else ""
    
    if callback.from_user.id == ADMIN_ID:
        if subcategory not in catalog[category]:
            catalog[category][subcategory] = {}
            save_catalog(catalog)
        
        await state.update_data(category=category, subcategory=subcategory)
        await state.set_state(AddItemState.entering_name)
        await callback.message.edit_text(
            f"📁 **Категория:** {category}\n"
            f"📂 **Подкатегория:** {subcategory}\n\n"
            f"**Введите НАЗВАНИЕ товара:**\n"
            f"(например: «Футболка белая S»)"
        )
    else:
        if category in catalog and subcategory in catalog[category]:
            items = catalog[category][subcategory]
            if not items:
                await callback.message.edit_text(
                    f"📂 **{subcategory}**\n\n"
                    f"В этой подкатегории пока нет товаров."
                )
            else:
                await callback.message.edit_text(
                    f"📂 **{subcategory}**\n\n"
                    f"**Список товаров:**",
                    reply_markup=get_items_keyboard(category, subcategory)
                )
    await callback.answer()

# --- СОЗДАНИЕ СВОЕЙ ПОДКАТЕГОРИИ ---
@dp.callback_query(lambda c: c.data.startswith("new_sub_"))
async def new_subcategory_callback(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.replace("new_sub_", "")
    await state.update_data(category=category)
    await state.set_state(AddItemState.choosing_subcategory)
    await callback.message.edit_text(f"✏️ **Напишите название новой подкатегории** для «{category}»:")
    await callback.answer()

@dp.message(AddItemState.choosing_subcategory)
async def process_new_subcategory(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    data = await state.get_data()
    category = data.get("category")
    
    if not category or category not in catalog:
        await message.answer("❌ Ошибка! Категория не найдена.")
        await state.clear()
        return
    
    subcategory_name = message.text.strip()
    
    if subcategory_name in catalog[category]:
        await message.answer(f"⚠️ Подкатегория «{subcategory_name}» уже существует.")
        return
    
    catalog[category][subcategory_name] = {}
    save_catalog(catalog)
    
    await state.update_data(subcategory=subcategory_name)
    await state.set_state(AddItemState.entering_name)
    await message.answer(
        f"✅ **Подкатегория «{subcategory_name}» создана!**\n\n"
        f"**Введите НАЗВАНИЕ товара:**"
    )

# --- ВВОД НАЗВАНИЯ ---
@dp.message(AddItemState.entering_name)
async def process_item_name(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    item_name = message.text.strip()
    await state.update_data(item_name=item_name)
    await state.set_state(AddItemState.entering_size)
    await message.answer(
        f"📦 **Товар:** {item_name}\n\n"
        f"**Введите РАЗМЕР:**\n"
        f"(S, M, L, XL, 42, 44, или «—» если не применимо)"
    )

# --- ВВОД РАЗМЕРА ---
@dp.message(AddItemState.entering_size)
async def process_item_size(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    size = message.text.strip() or "—"
    await state.update_data(size=size)
    await state.set_state(AddItemState.entering_price)
    await message.answer(
        f"📏 **Размер:** {size}\n\n"
        f"**Введите ЦЕНУ:**\n"
        f"(только число, например: 500)"
    )

# --- ВВОД ЦЕНЫ ---
@dp.message(AddItemState.entering_price)
async def process_item_price(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        price = int(message.text.strip())
        await state.update_data(price=price)
        await state.set_state(AddItemState.entering_stock)
        await message.answer(
            f"💰 **Цена:** {price} ₽\n\n"
            f"**Введите КОЛИЧЕСТВО:**\n"
            f"(только число, например: 10)"
        )
    except ValueError:
        await message.answer("❌ Ошибка! Введите число. Пример: 500")

# --- ВВОД КОЛИЧЕСТВА ---
@dp.message(AddItemState.entering_stock)
async def process_item_stock(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        stock = int(message.text.strip())
        await state.update_data(stock=stock)
        await state.set_state(AddItemState.entering_photo)
        await message.answer(
            f"📦 **В наличии:** {stock} шт\n\n"
            f"📸 **Загрузите ФОТО товара**\n"
            f"(или нажмите «Пропустить»):",
            reply_markup=get_skip_photo_keyboard()
        )
    except ValueError:
        await message.answer("❌ Ошибка! Введите число. Пример: 10")

# --- ФОТО ИЛИ ПРОПУСК ---
@dp.message(AddItemState.entering_photo)
async def process_item_photo(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    if message.photo:
        photo = message.photo[-1].file_id
        await state.update_data(photo=photo)
        await save_item(message, state)
    else:
        await message.answer("❌ Пожалуйста, отправьте фото или нажмите кнопку «Пропустить».")

@dp.callback_query(lambda c: c.data == "skip_photo")
async def skip_photo(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(photo=None)
    await callback.message.delete()
    await save_item(callback.message, state)
    await callback.answer()

async def save_item(message, state):
    data = await state.get_data()
    
    category = data.get("category")
    subcategory = data.get("subcategory")
    item_name = data.get("item_name")
    size = data.get("size")
    price = data.get("price")
    stock = data.get("stock")
    photo = data.get("photo")
    
    if category not in catalog:
        catalog[category] = {}
    if subcategory not in catalog[category]:
        catalog[category][subcategory] = {}
    
    catalog[category][subcategory][item_name] = {
        "size": size,
        "price": price,
        "stock": stock,
        "photo": photo
    }
    save_catalog(catalog)
    
    await state.clear()
    
    # Красивое сообщение о добавлении товара
    result_text = (
        f"✅ **ТОВАР ДОБАВЛЕН!**\n\n"
        f"📁 {category} → {subcategory}\n"
        f"📦 {item_name}\n"
        f"📏 Размер: {size}\n"
        f"💰 Цена: {price} ₽\n"
        f"📦 В наличии: {stock} шт\n"
        f"📸 Фото: {'✅ есть' if photo else '❌ нет'}\n\n"
        f"Нажмите «➕ Добавить товар» для следующего."
    )
    
    await message.answer(result_text, reply_markup=get_main_keyboard())

# --- ПРОСМОТР ТОВАРА ПОКУПАТЕЛЕМ (КАРТОЧКА) ---
@dp.callback_query(lambda c: c.data.startswith("item_"))
async def view_item(callback: types.CallbackQuery):
    parts = callback.data.replace("item_", "").split("_", 2)
    if len(parts) < 3:
        await callback.answer("Ошибка!")
        return
    
    category = parts[0]
    subcategory = parts[1]
    item_name = parts[2]
    
    if category not in catalog or subcategory not in catalog[category] or item_name not in catalog[category][subcategory]:
        await callback.message.edit_text("❌ Товар не найден.")
        await callback.answer()
        return
    
    data = catalog[category][subcategory][item_name]
    
    # Создаём красивую карточку товара
    if data["stock"] > 0:
        text = (
            f"🛍️ **{item_name}**\n\n"
            f"📏 **Размер:** {data['size']}\n"
            f"💰 **Цена:** {data['price']} ₽\n"
            f"✅ **В наличии:** {data['stock']} шт\n\n"
            f"📝 **Готовый вопрос продавцу:**\n"
            f"«Здравствуйте! {item_name} (размер {data['size']}) есть в наличии? Хочу купить!»"
        )
    else:
        text = (
            f"🛍️ **{item_name}**\n\n"
            f"📏 **Размер:** {data['size']}\n"
            f"💰 **Цена:** {data['price']} ₽\n"
            f"❌ **Нет в наличии**\n\n"
            f"📝 **Готовый вопрос продавцу:**\n"
            f"«Здравствуйте! Когда ожидается {item_name} (размер {data['size']})?»"
        )
    
    # Отправляем карточку с фото или без
    if data.get("photo"):
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=data["photo"],
            caption=text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_items_{category}_{subcategory}")]
            ])
        )
    else:
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_items_{category}_{subcategory}")]
            ])
        )
    
    await callback.answer()

# --- НАВИГАЦИЯ ---
@dp.callback_query(lambda c: c.data == "back_categories")
async def back_to_categories(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📁 **Выберите категорию:**",
        reply_markup=get_categories_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("back_sub_"))
async def back_to_subcategories(callback: types.CallbackQuery):
    category = callback.data.replace("back_sub_", "")
    await callback.message.edit_text(
        f"📁 **Категория:** {category}\n\n"
        f"**Выберите подкатегорию:**",
        reply_markup=get_subcategories_keyboard(category)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("back_items_"))
async def back_to_items(callback: types.CallbackQuery):
    parts = callback.data.replace("back_items_", "").split("_", 1)
    category = parts[0]
    subcategory = parts[1] if len(parts) > 1 else ""
    
    await callback.message.edit_text(
        f"📂 **{subcategory}**\n\n"
        f"**Список товаров:**",
        reply_markup=get_items_keyboard(category, subcategory)
    )
    await callback.answer()

# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO)
    print("🤖 AvitoStockBot запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())