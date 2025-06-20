"""
Telegram бот для магазина Rukami
Расширенная версия с авторизацией и отображением изображений
"""

import asyncio
import logging
from typing import Optional, Dict, Any
import os
from datetime import datetime
import hashlib
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
import asyncpg
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
REGISTRATION_NAME, REGISTRATION_EMAIL, REGISTRATION_PHONE, REGISTRATION_PASSWORD = range(4)
LOGIN_EMAIL, LOGIN_PASSWORD = range(4, 6)


class RukamiBot:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        self.db_pool = None
        self.application = None

        # Настройки БД из config.py
        self.db_user = os.getenv('DB_USER', 'postgres')
        self.db_password = os.getenv('DB_PASSWORD', 'postgres')
        self.db_host = os.getenv('DB_HOST', 'localhost')
        self.db_port = os.getenv('DB_PORT', '5432')
        self.db_name = os.getenv('DB_NAME', 'rukami_db')

        # Временное хранилище данных пользователей
        self.user_sessions: Dict[int, Dict[str, Any]] = {}

        self.notification_task = None
        self.last_product_check = None

    @property
    def database_url(self) -> str:
        """URL подключения к базе данных"""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    async def init_db(self):
        """Инициализация подключения к БД"""
        try:
            self.db_pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=5,
                command_timeout=60
            )
            logger.info("✅ Подключение к БД установлено")

            # Добавляем поле telegram_id в таблицу users если его нет
            await self.add_telegram_id_field()

        except Exception as e:
            logger.error(f"❌ Ошибка подключения к БД: {e}")
            raise

    async def add_telegram_id_field(self):
        """Добавление поля telegram_id и notifications_enabled в таблицу users"""
        try:
            async with self.db_pool.acquire() as conn:
                # Проверяем, существует ли поле telegram_id
                result = await conn.fetchval("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'telegram_id'
                """)

                if not result:
                    await conn.execute("""
                        ALTER TABLE users 
                        ADD COLUMN telegram_id BIGINT UNIQUE
                    """)
                    logger.info("✅ Поле telegram_id добавлено в таблицу users")

                # Проверяем, существует ли поле notifications_enabled
                result = await conn.fetchval("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'notifications_enabled'
                """)

                if not result:
                    await conn.execute("""
                        ALTER TABLE users 
                        ADD COLUMN notifications_enabled BOOLEAN DEFAULT true
                    """)
                    logger.info("✅ Поле notifications_enabled добавлено в таблицу users")

        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении полей в таблицу users: {e}")

    async def close_db(self):
        """Закрытие подключения к БД"""
        if self.db_pool:
            await self.db_pool.close()
            logger.info("✅ Подключение к БД закрыто")

    def hash_password(self, password: str) -> str:
        """Хеширование пароля"""
        return hashlib.sha256(password.encode()).hexdigest()

    def validate_email(self, email: str) -> bool:
        """Валидация email"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def validate_phone(self, phone: str) -> bool:
        """Валидация телефона"""
        pattern = r'^(\+7|7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'
        return re.match(pattern, phone.replace(' ', '').replace('-', '')) is not None

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[dict]:
        """Получение пользователя по Telegram ID"""
        async with self.db_pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1",
                telegram_id
            )

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """Получение пользователя по email"""
        async with self.db_pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE email = $1",
                email
            )

    async def create_user(self, name: str, email: str, phone: str, password: str, telegram_id: int) -> bool:
        """Создание нового пользователя"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO users (name, email, phone, password_hash, telegram_id)
                    VALUES ($1, $2, $3, $4, $5)
                """, name, email, phone, self.hash_password(password), telegram_id)
                return True
        except Exception as e:
            logger.error(f"Ошибка создания пользователя: {e}")
            return False

    async def link_telegram_to_user(self, email: str, password: str, telegram_id: int) -> bool:
        """Привязка Telegram ID к существующему пользователю"""
        try:
            async with self.db_pool.acquire() as conn:
                user = await conn.fetchrow(
                    "SELECT * FROM users WHERE email = $1 AND password_hash = $2",
                    email, self.hash_password(password)
                )

                if user:
                    await conn.execute(
                        "UPDATE users SET telegram_id = $1 WHERE id = $2",
                        telegram_id, user['id']
                    )
                    return True
                return False
        except Exception as e:
            logger.error(f"Ошибка привязки Telegram: {e}")
            return False

    async def get_categories(self) -> list:
        """Получение всех активных категорий"""
        async with self.db_pool.acquire() as conn:
            return await conn.fetch(
                "SELECT * FROM categories WHERE is_active = true ORDER BY sort_order, name"
            )

    async def get_products_by_category(self, category_id: int, limit: int = 10) -> list:
        """Получение товаров по категории"""
        async with self.db_pool.acquire() as conn:
            return await conn.fetch("""
                SELECT p.*, c.name as category_name, u.name as seller_name 
                FROM products p 
                JOIN categories c ON p.category_id = c.id 
                JOIN users u ON p.user_id = u.id 
                WHERE p.category_id = $1 AND p.in_stock = true 
                ORDER BY p.created_at DESC 
                LIMIT $2
            """, category_id, limit)

    async def get_product_by_id(self, product_id: int) -> Optional[dict]:
        """Получение товара по ID"""
        async with self.db_pool.acquire() as conn:
            return await conn.fetchrow("""
                SELECT p.*, c.name as category_name, u.name as seller_name, u.phone as seller_phone, u.email as seller_email
                FROM products p 
                JOIN categories c ON p.category_id = c.id 
                JOIN users u ON p.user_id = u.id 
                WHERE p.id = $1
            """, product_id)

    def is_user_authenticated(self, telegram_id: int) -> bool:
        """Проверка авторизации пользователя"""
        return telegram_id in self.user_sessions and self.user_sessions[telegram_id].get('authenticated', False)

    async def require_auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Проверка авторизации с предложением войти"""
        telegram_id = update.effective_user.id

        if not self.is_user_authenticated(telegram_id):
            text = "🔒 Для использования этой функции необходимо авторизоваться."
            keyboard = [
                [InlineKeyboardButton("🔑 Войти", callback_data="login")],
                [InlineKeyboardButton("📝 Регистрация", callback_data="register")],
                [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if update.callback_query:
                await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(text, reply_markup=reply_markup)
            return False
        return True

    # Команды бота
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user = update.effective_user
        telegram_id = user.id

        # Проверяем, есть ли пользователь в БД
        db_user = await self.get_user_by_telegram_id(telegram_id)
        if db_user:
            self.user_sessions[telegram_id] = {
                'authenticated': True,
                'user_id': db_user['id'],
                'user_name': db_user['name']
            }

        welcome_text = f"""
🌟 Добро пожаловать в Rukami, {user.first_name}!

Rukami - это маркетплейс уникальных товаров ручной работы. 
Здесь вы найдете:
• Керамику и посуду
• Украшения и бижутерию  
• Текстиль и вязаные изделия
• Деревянные изделия
• Натуральное мыло и свечи
• И многое другое!

Выберите действие:
        """

        keyboard = [
            [InlineKeyboardButton("🛍️ Каталог товаров", callback_data="catalog")]
        ]

        if self.is_user_authenticated(telegram_id):
            keyboard.extend([
                [InlineKeyboardButton("❤️ Избранное", callback_data="favorites")],
                [InlineKeyboardButton("🛒 Корзина", callback_data="cart")],
                [InlineKeyboardButton("👤 Профиль", callback_data="profile")]
            ])
        else:
            keyboard.extend([
                [InlineKeyboardButton("🔑 Войти", callback_data="login")],
                [InlineKeyboardButton("📝 Регистрация", callback_data="register")]
            ])

        keyboard.append([InlineKeyboardButton("ℹ️ О проекте", callback_data="about")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    # Регистрация
    async def start_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало регистрации"""
        query = update.callback_query
        await query.answer()

        text = "📝 *Регистрация*\n\nВведите ваше полное имя:"
        await query.edit_message_text(text, parse_mode='Markdown')
        return REGISTRATION_NAME

    async def registration_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение имени при регистрации"""
        name = update.message.text.strip()

        if len(name) < 2:
            await update.message.reply_text("Имя должно содержать минимум 2 символа. Попробуйте еще раз:")
            return REGISTRATION_NAME

        context.user_data['registration_name'] = name
        await update.message.reply_text("📧 Теперь введите ваш email:")
        return REGISTRATION_EMAIL

    async def registration_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение email при регистрации"""
        email = update.message.text.strip().lower()

        if not self.validate_email(email):
            await update.message.reply_text("Неверный формат email. Попробуйте еще раз:")
            return REGISTRATION_EMAIL

        # Проверяем, не занят ли email
        existing_user = await self.get_user_by_email(email)
        if existing_user:
            await update.message.reply_text("Этот email уже зарегистрирован. Попробуйте другой:")
            return REGISTRATION_EMAIL

        context.user_data['registration_email'] = email
        await update.message.reply_text("📱 Введите ваш номер телефона:")
        return REGISTRATION_PHONE

    async def registration_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение телефона при регистрации"""
        phone = update.message.text.strip()

        if not self.validate_phone(phone):
            await update.message.reply_text("Неверный формат телефона. Попробуйте еще раз (например: +7 900 123 45 67):")
            return REGISTRATION_PHONE

        context.user_data['registration_phone'] = phone
        await update.message.reply_text("🔐 Придумайте пароль (минимум 6 символов):")
        return REGISTRATION_PASSWORD

    async def registration_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение пароля и завершение регистрации"""
        password = update.message.text.strip()

        if len(password) < 6:
            await update.message.reply_text("Пароль должен содержать минимум 6 символов. Попробуйте еще раз:")
            return REGISTRATION_PASSWORD

        # Создаем пользователя
        success = await self.create_user(
            context.user_data['registration_name'],
            context.user_data['registration_email'],
            context.user_data['registration_phone'],
            password,
            update.effective_user.id
        )

        if success:
            # Авторизуем пользователя
            self.user_sessions[update.effective_user.id] = {
                'authenticated': True,
                'user_name': context.user_data['registration_name']
            }

            await update.message.reply_text(
                "✅ Регистрация завершена!\n\nДобро пожаловать в Rukami! Используйте /start для начала работы."
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка регистрации. Попробуйте позже или обратитесь в поддержку."
            )

        # Очищаем данные
        context.user_data.clear()
        return ConversationHandler.END

    # Авторизация
    async def start_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало авторизации"""
        query = update.callback_query
        await query.answer()

        text = "🔑 *Авторизация*\n\nВведите ваш email:"
        await query.edit_message_text(text, parse_mode='Markdown')
        return LOGIN_EMAIL

    async def login_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение email при авторизации"""
        email = update.message.text.strip().lower()

        if not self.validate_email(email):
            await update.message.reply_text("Неверный формат email. Попробуйте еще раз:")
            return LOGIN_EMAIL

        context.user_data['login_email'] = email
        await update.message.reply_text("🔐 Введите ваш пароль:")
        return LOGIN_PASSWORD

    async def login_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение пароля и завершение авторизации"""
        password = update.message.text.strip()
        email = context.user_data['login_email']

        # Привязываем Telegram к аккаунту
        success = await self.link_telegram_to_user(email, password, update.effective_user.id)

        if success:
            user = await self.get_user_by_email(email)
            self.user_sessions[update.effective_user.id] = {
                'authenticated': True,
                'user_id': user['id'],
                'user_name': user['name']
            }

            await update.message.reply_text(
                f"✅ Авторизация успешна!\n\nДобро пожаловать, {user['name']}! Используйте /start для начала работы."
            )
        else:
            await update.message.reply_text(
                "❌ Неверный email или пароль. Попробуйте еще раз или зарегистрируйтесь."
            )

        # Очищаем данные
        context.user_data.clear()
        return ConversationHandler.END

    async def cancel_auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена авторизации/регистрации"""
        await update.message.reply_text("Операция отменена. Используйте /start для возврата в главное меню.")
        context.user_data.clear()
        return ConversationHandler.END

    async def catalog_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать каталог категорий"""
        try:
            categories = await self.get_categories()

            if not categories:
                await update.message.reply_text("Пока что категории не добавлены.")
                return

            text = "🛍️ *Каталог товаров*\n\nВыберите категорию:"
            keyboard = []

            for category in categories:
                callback_data = f"category_{category['id']}"
                keyboard.append([InlineKeyboardButton(
                    f"{category['name']}",
                    callback_data=callback_data
                )])

            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"Ошибка в catalog_command: {e}")
            await update.message.reply_text("Произошла ошибка при загрузке каталога.")

    # Обработчики callback запросов
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на кнопки"""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == "catalog":
            await self.show_catalog(query)
        elif data == "favorites":
            if await self.require_auth(update, context):
                await self.show_favorites(query)
        elif data == "cart":
            if await self.require_auth(update, context):
                await self.show_cart(query)
        elif data == "profile":
            if await self.require_auth(update, context):
                await self.show_profile(query)
        elif data == "about":
            await self.show_about(query)
        elif data == "main_menu":
            await self.show_main_menu(query)
        elif data == "register":
            # Перенаправляем на ConversationHandler
            await self.start_registration(update, context)
            return
        elif data == "login":
            # Перенаправляем на ConversationHandler
            await self.start_login(update, context)
            return
        elif data == "notifications_settings":
            if await self.require_auth(update, context):
                await self.show_notification_settings(query)
        elif data == "notifications_on":
            if await self.require_auth(update, context):
                await self.toggle_notifications(query, True)
                await self.show_notification_settings(query)
        elif data == "notifications_off":
            if await self.require_auth(update, context):
                await self.toggle_notifications(query, False)
                await self.show_notification_settings(query)
        elif data.startswith("category_"):
            category_id = int(data.split("_")[1])
            await self.show_category_products(query, category_id)
        elif data.startswith("product_"):
            product_id = int(data.split("_")[1])
            await self.show_product_details(query, product_id)
        elif data.startswith("add_to_cart_"):
            if await self.require_auth(update, context):
                product_id = int(data.split("_")[3])
                await self.add_to_cart(query, product_id)

    async def safe_edit_message(self, query, text: str, reply_markup=None):
        """Безопасное редактирование сообщения с обработкой ошибок"""
        try:
            await query.edit_message_text(
                text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            # Если не можем отредактировать (например, сообщение было удалено),
            # отправляем новое сообщение
            logger.warning(f"Не удалось отредактировать сообщение: {e}")
            try:
                await query.message.reply_text(
                    text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
            except Exception as e2:
                logger.error(f"Не удалось отправить новое сообщение: {e2}")

    async def show_catalog(self, query):
        """Показать каталог категорий"""
        try:
            categories = await self.get_categories()

            text = "🛍️ *Каталог товаров*\n\nВыберите категорию:"
            keyboard = []

            for category in categories:
                callback_data = f"category_{category['id']}"
                keyboard.append([InlineKeyboardButton(
                    f"{category['name']}",
                    callback_data=callback_data
                )])

            keyboard.append([InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await self.safe_edit_message(query, text, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Ошибка в show_catalog: {e}")
            await self.safe_edit_message(query, "Произошла ошибка при загрузке каталога.")

    async def show_category_products(self, query, category_id: int):
        """Показать товары категории"""
        try:
            products = await self.get_products_by_category(category_id)

            if not products:
                text = "В этой категории пока нет товаров."
                keyboard = [[InlineKeyboardButton("◀️ Назад к каталогу", callback_data="catalog")]]
            else:
                text = f"📦 *Товары в категории*\n\n"
                keyboard = []

                for product in products[:10]:  # Показываем максимум 10 товаров
                    text += f"• *{product['name']}*\n"
                    text += f"  💰 {product['price']} ₽\n"
                    text += f"  👤 {product['seller_name']}\n\n"

                    keyboard.append([InlineKeyboardButton(
                        f"👀 {product['name'][:30]}...",
                        callback_data=f"product_{product['id']}"
                    )])

            keyboard.append([InlineKeyboardButton("◀️ Назад к каталогу", callback_data="catalog")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await self.safe_edit_message(query, text, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Ошибка в show_category_products: {e}")
            await self.safe_edit_message(query, "Произошла ошибка при загрузке товаров.")

    async def show_product_details(self, query, product_id: int):
        """Показать детали товара с изображением"""
        try:
            product = await self.get_product_by_id(product_id)

            if not product:
                await self.safe_edit_message(query, "Товар не найден.")
                return

            text = f"🎨 *{product['name']}*\n\n"
            text += f"📝 {product['description']}\n\n"
            text += f"💰 *Цена:* {product['price']} ₽\n"
            text += f"📂 *Категория:* {product['category_name']}\n"
            text += f"👤 *Продавец:* {product['seller_name']}\n"

            if product['seller_phone']:
                text += f"📞 *Контакт:* {product['seller_phone']}\n"

            text += f"📅 *Добавлено:* {product['created_at'].strftime('%d.%m.%Y')}\n"

            keyboard = []

            # Кнопки в зависимости от авторизации
            telegram_id = query.from_user.id
            if self.is_user_authenticated(telegram_id):
                keyboard.extend([
                    [InlineKeyboardButton("🛒 Добавить в корзину", callback_data=f"add_to_cart_{product_id}")],
                    [InlineKeyboardButton("❤️ В избранное", callback_data=f"add_to_favorites_{product_id}")]
                ])
            else:
                keyboard.append([InlineKeyboardButton("🔑 Войти для покупки", callback_data="login")])

            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"category_{product['category_id']}")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Если есть изображение товара, отправляем его
            if product['image_url']:
                try:
                    # Отправляем изображение с подписью
                    await query.message.reply_photo(
                        photo=product['image_url'],
                        caption=text,
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                    # Удаляем предыдущее сообщение
                    await query.delete_message()
                except Exception as img_error:
                    logger.error(f"Ошибка загрузки изображения: {img_error}")
                    # Если изображение не загрузилось, показываем только текст
                    await self.safe_edit_message(
                        query,
                        text + "\n\n⚠️ Изображение временно недоступно",
                        reply_markup=reply_markup
                    )
            else:
                # Если изображения нет, показываем только текст
                await self.safe_edit_message(query, text, reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Ошибка в show_product_details: {e}")
            await self.safe_edit_message(query, "Произошла ошибка при загрузке товара.")

    async def show_profile(self, query):
        """Показать профиль пользователя"""
        telegram_id = query.from_user.id
        user = await self.get_user_by_telegram_id(telegram_id)

        if user:
            text = f"👤 *Профиль*\n\n"
            text += f"*Имя:* {user['name']}\n"
            text += f"*Email:* {user['email']}\n"
            text += f"*Телефон:* {user['phone'] or 'Не указан'}\n"
            text += f"*Дата регистрации:* {user['created_at'].strftime('%d.%m.%Y')}\n"
        else:
            text = "❌ Профиль не найден"

        keyboard = [
            [InlineKeyboardButton("🔔 Настройки уведомлений", callback_data="notifications_settings")],
            [InlineKeyboardButton("🚪 Выйти из аккаунта", callback_data="logout")],
            [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.safe_edit_message(query, text, reply_markup=reply_markup)

    async def show_favorites(self, query):
        """Показать избранное (заглушка)"""
        text = "❤️ *Избранное*\n\nФункция избранного будет добавлена в следующем обновлении."
        keyboard = [[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.safe_edit_message(query, text, reply_markup=reply_markup)

    async def show_cart(self, query):
        """Показать корзину (заглушка)"""
        text = "🛒 *Корзина*\n\nФункция корзины будет добавлена в следующем обновлении."
        keyboard = [[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.safe_edit_message(query, text, reply_markup=reply_markup)

    async def show_about(self, query):
        """Показать информацию о проекте"""
        text = """
    ℹ️ *О проекте Rukami*

    Rukami - маркетплейс уникальных товаров ручной работы.

    *Наша миссия:* 
    Поддержать мастеров и ремесленников, предоставив платформу для продажи их творений.

    *Что мы предлагаем:*
    • Широкий выбор handmade товаров
    • Прямую связь с мастерами
    • Гарантию качества и уникальности
    • Удобную покупку через Telegram

    *Версия бота:* 1.0.0
    *Сайт:* rukami.ru (в разработке)
        """

        keyboard = [[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.safe_edit_message(query, text, reply_markup=reply_markup)

    async def show_main_menu(self, query):
        """Показать главное меню"""
        user = query.from_user
        telegram_id = user.id

        text = f"🌟 Добро пожаловать в Rukami, {user.first_name}!\n\n"
        text += "Rukami - это маркетплейс уникальных товаров ручной работы.\n"
        text += "Выберите действие:"

        keyboard = [
            [InlineKeyboardButton("🛍️ Каталог товаров", callback_data="catalog")]
        ]

        if self.is_user_authenticated(telegram_id):
            keyboard.extend([
                [InlineKeyboardButton("❤️ Избранное", callback_data="favorites")],
                [InlineKeyboardButton("🛒 Корзина", callback_data="cart")],
                [InlineKeyboardButton("👤 Профиль", callback_data="profile")]
            ])
        else:
            keyboard.extend([
                [InlineKeyboardButton("🔑 Войти", callback_data="login")],
                [InlineKeyboardButton("📝 Регистрация", callback_data="register")]
            ])

        keyboard.append([InlineKeyboardButton("ℹ️ О проекте", callback_data="about")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.safe_edit_message(query, text, reply_markup=reply_markup)
    async def add_to_cart(self, query, product_id: int):
        """Добавить товар в корзину (заглушка)"""
        await query.answer("🛒 Товар добавлен в корзину! (в разработке)")

    async def logout(self, query):
        """Выход из аккаунта"""
        telegram_id = query.from_user.id
        if telegram_id in self.user_sessions:
            del self.user_sessions[telegram_id]

        await query.answer("👋 Вы вышли из аккаунта")
        await self.show_main_menu(query)

    async def get_all_telegram_users(self) -> list:
        """Получение всех пользователей с Telegram ID для рассылки (только с включенными уведомлениями)"""
        async with self.db_pool.acquire() as conn:
            return await conn.fetch("""
                SELECT telegram_id, name FROM users 
                WHERE telegram_id IS NOT NULL 
                AND (notifications_enabled IS NULL OR notifications_enabled = true)
            """)

    async def get_new_products_since(self, timestamp) -> list:
        """Получение новых товаров с определенного времени"""
        async with self.db_pool.acquire() as conn:
            query = """
                SELECT p.*, c.name as category_name, u.name as seller_name 
                FROM products p 
                JOIN categories c ON p.category_id = c.id 
                JOIN users u ON p.user_id = u.id 
                WHERE p.created_at > $1 AND p.in_stock = true 
                ORDER BY p.created_at DESC
            """
            return await conn.fetch(query, timestamp)

    async def send_new_product_notification(self, product: dict, telegram_id: int):
        """Отправка уведомления о новом товаре конкретному пользователю"""
        try:
            text = f"🆕 *Новый товар в Rukami!*\n\n"
            text += f"🎨 *{product['name']}*\n\n"
            text += f"📝 {product['description']}\n\n"
            text += f"💰 *Цена:* {product['price']} ₽\n"
            text += f"📂 *Категория:* {product['category_name']}\n"
            text += f"👤 *Продавец:* {product['seller_name']}\n"

            keyboard = [
                [InlineKeyboardButton("👀 Посмотреть", callback_data=f"product_{product['id']}")],
                [InlineKeyboardButton("🛍️ Каталог", callback_data="catalog")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Если есть изображение, отправляем с фото
            if product['image_url']:
                try:
                    await self.application.bot.send_photo(
                        chat_id=telegram_id,
                        photo=product['image_url'],
                        caption=text,
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                except Exception as img_error:
                    logger.error(f"Ошибка отправки изображения пользователю {telegram_id}: {img_error}")
                    # Если изображение не отправилось, отправляем только текст
                    await self.application.bot.send_message(
                        chat_id=telegram_id,
                        text=text + "\n\n⚠️ Изображение временно недоступно",
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
            else:
                # Отправляем только текст
                await self.application.bot.send_message(
                    chat_id=telegram_id,
                    text=text,
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {telegram_id}: {e}")

    async def broadcast_new_products(self, products: list):
        """Рассылка уведомлений о новых товарах всем пользователям"""
        if not products:
            return

        users = await self.get_all_telegram_users()
        logger.info(f"Отправка уведомлений о {len(products)} новых товарах для {len(users)} пользователей")

        for product in products:
            for user in users:
                try:
                    await self.send_new_product_notification(product, user['telegram_id'])
                    # Небольшая задержка, чтобы не спамить Telegram API
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user['telegram_id']}: {e}")

    async def check_new_products(self):
        """Периодическая проверка новых товаров"""
        try:
            current_time = datetime.now()

            # Если это первая проверка, устанавливаем время на час назад
            if self.last_product_check is None:
                self.last_product_check = current_time.replace(hour=current_time.hour - 1)

            # Получаем новые товары
            new_products = await self.get_new_products_since(self.last_product_check)

            if new_products:
                logger.info(f"Найдено {len(new_products)} новых товаров")
                await self.broadcast_new_products(new_products)

            # Обновляем время последней проверки
            self.last_product_check = current_time

        except Exception as e:
            logger.error(f"Ошибка при проверке новых товаров: {e}")

    async def start_product_monitoring(self):
        """Запуск мониторинга новых товаров"""

        async def monitoring_loop():
            while True:
                try:
                    await self.check_new_products()
                    # Проверяем каждые 5 минут
                    await asyncio.sleep(60)
                except Exception as e:
                    logger.error(f"Ошибка в цикле мониторинга: {e}")
                    # При ошибке ждем минуту и продолжаем
                    await asyncio.sleep(60)

        self.notification_task = asyncio.create_task(monitoring_loop())
        logger.info("🔔 Мониторинг новых товаров запущен")

    async def stop_product_monitoring(self):
        """Остановка мониторинга новых товаров"""
        if self.notification_task:
            self.notification_task.cancel()
            try:
                await self.notification_task
            except asyncio.CancelledError:
                pass
            logger.info("🔕 Мониторинг новых товаров остановлен")

    async def toggle_notifications(self, query, enable: bool):
        """Включение/выключение уведомлений для пользователя"""
        telegram_id = query.from_user.id

        # Добавить поле notifications_enabled в таблицу users
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE users 
                SET notifications_enabled = $1 
                WHERE telegram_id = $2
            """, enable, telegram_id)

        status = "включены" if enable else "выключены"
        await query.answer(f"🔔 Уведомления {status}")

    async def show_notification_settings(self, query):
        """Показать настройки уведомлений"""
        telegram_id = query.from_user.id

        async with self.db_pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT notifications_enabled FROM users WHERE telegram_id = $1",
                telegram_id
            )

        notifications_enabled = user['notifications_enabled'] if user else True

        text = "🔔 *Настройки уведомлений*\n\n"
        text += f"Уведомления о новых товарах: {'✅ Включены' if notifications_enabled else '❌ Выключены'}\n\n"
        text += "Вы можете включить или выключить уведомления о появлении новых товаров в магазине."

        keyboard = []
        if notifications_enabled:
            keyboard.append([InlineKeyboardButton("🔕 Выключить уведомления", callback_data="notifications_off")])
        else:
            keyboard.append([InlineKeyboardButton("🔔 Включить уведомления", callback_data="notifications_on")])

        keyboard.append([InlineKeyboardButton("◀️ Назад к профилю", callback_data="profile")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.safe_edit_message(query, text, reply_markup=reply_markup)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        help_text = """
🤖 *Команды бота Rukami:*

/start - Главное меню
/catalog - Каталог товаров  
/help - Справка

*Навигация:*
Используйте кнопки для удобной навигации по боту.

*Функции:*
• Просмотр каталога товаров с изображениями
• Регистрация и авторизация
• Добавление в корзину и избранное
• Профиль пользователя

*Поддержка:*
По вопросам работы бота обращайтесь к администратору.
        """

        await update.message.reply_text(help_text, parse_mode='Markdown')

    def run(self):
        """Запуск бота"""
        if not self.bot_token:
            logger.error("❌ Не указан BOT_TOKEN")
            return

        # Создаем приложение и сохраняем его как атрибут класса
        self.application = Application.builder().token(self.bot_token).build()

        # Обработчики для регистрации
        registration_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_registration, pattern="^register$")],
            states={
                REGISTRATION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.registration_name)],
                REGISTRATION_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.registration_email)],
                REGISTRATION_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.registration_phone)],
                REGISTRATION_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.registration_password)],
            },
            fallbacks=[MessageHandler(filters.COMMAND, self.cancel_auth)]
        )

        # Обработчики для авторизации
        login_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_login, pattern="^login$")],
            states={
                LOGIN_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.login_email)],
                LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.login_password)],
            },
            fallbacks=[MessageHandler(filters.COMMAND, self.cancel_auth)]
        )

        # Регистрируем обработчики
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("catalog", self.catalog_command))
        self.application.add_handler(CommandHandler("help", self.help_command))

        # Добавляем ConversationHandler'ы
        self.application.add_handler(registration_handler)
        self.application.add_handler(login_handler)

        # Основной обработчик callback'ов
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

        # Запускаем бота
        logger.info("🤖 Запуск Telegram бота Rukami...")

        async def startup():
            await self.init_db()
            await self.start_product_monitoring()

        async def shutdown():
            await self.stop_product_monitoring()
            await self.close_db()

        # Инициализация БД при запуске
        asyncio.get_event_loop().run_until_complete(startup())

        try:
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        except KeyboardInterrupt:
            logger.info("🛑 Остановка бота...")
        finally:
            asyncio.get_event_loop().run_until_complete(shutdown())


if __name__ == '__main__':
    bot = RukamiBot()
    bot.run()