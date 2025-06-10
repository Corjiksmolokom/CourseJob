"""Обновленная конфигурация базы данных с отдельной сущностью категорий"""
import logging
from typing import Optional
import asyncpg
from asyncpg import Pool

from server.config import settings

logger = logging.getLogger(__name__)

# Глобальный пул соединений
db_pool: Optional[Pool] = None


async def init_database():
    """Инициализация базы данных"""
    global db_pool

    try:
        db_pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=10,
            command_timeout=60
        )

        # Создаем таблицы
        async with db_pool.acquire() as connection:
            await create_tables(connection)

        logger.info("✅ База данных успешно инициализирована")

    except Exception as e:
        logger.error(f"❌ Ошибка инициализации базы данных: {e}")
        raise


async def create_tables(connection: asyncpg.Connection):
    """Создание всех необходимых таблиц"""

    # 1. Таблица категорий (создаем первой, так как на неё ссылаются другие таблицы)
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            slug VARCHAR(100) UNIQUE NOT NULL,
            image_url VARCHAR(500),
            is_active BOOLEAN DEFAULT true,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    # 2. Таблица пользователей
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            phone VARCHAR(20),
            password_hash VARCHAR(255) NOT NULL,
            address TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    # 3. Таблица товаров (изменяем category на category_id)
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name VARCHAR(500) NOT NULL,
            description TEXT NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
            author VARCHAR(255) NOT NULL,
            image_url VARCHAR(500),
            in_stock BOOLEAN DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    # 4. Таблица избранного
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(user_id, product_id)
        );
    """)

    # 5. Таблица корзины
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            quantity INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(user_id, product_id)
        );
    """)

    # 6. Таблица отзывов
    await connection.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    # Создание индексов
    await connection.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);")
    await connection.execute("CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorites(user_id);")
    await connection.execute("CREATE INDEX IF NOT EXISTS idx_cart_user ON cart_items(user_id);")
    await connection.execute("CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id);")
    await connection.execute("CREATE INDEX IF NOT EXISTS idx_categories_slug ON categories(slug);")

    # Добавляем тестовые данные, если таблицы пустые
    categories_count = await connection.fetchval("SELECT COUNT(*) FROM categories")
    if categories_count == 0:
        await add_sample_categories(connection)

    products_count = await connection.fetchval("SELECT COUNT(*) FROM products")
    if products_count == 0:
        await add_sample_products(connection)

    logger.info("✅ Таблицы созданы успешно")


async def add_sample_categories(connection: asyncpg.Connection):
    """Добавление тестовых категорий"""
    sample_categories = [
        ("Керамика", "Изделия из глины и керамики ручной работы", "ceramics", "category-ceramics.jpg"),
        ("Украшения", "Ювелирные изделия и бижутерия ручной работы", "jewelry", "category-jewelry.jpg"),
        ("Текстиль", "Вязаные изделия, пледы, подушки", "textiles", "category-textiles.jpg"),
        ("Дерево", "Изделия из дерева: шкатулки, декор, мебель", "wood", "category-wood.jpg"),
        ("Мыло", "Натуральное мыло ручной варки", "soap", "category-soap.jpg"),
        ("Свечи", "Ароматические и декоративные свечи", "candles", "category-candles.jpg"),
        ("Игрушки", "Мягкие игрушки и куклы ручной работы", "toys", "category-toys.jpg"),
        ("Картины", "Живопись и графика", "paintings", "category-paintings.jpg"),
        ("Сумки", "Кожаные и текстильные сумки", "bags", "category-bags.jpg"),
        ("Декор", "Предметы интерьера и декор", "decor", "category-decor.jpg")
    ]

    for i, (name, description, slug, image_url) in enumerate(sample_categories, 1):
        await connection.execute("""
            INSERT INTO categories (name, description, slug, image_url, sort_order)
            VALUES ($1, $2, $3, $4, $5)
        """, name, description, slug, image_url, i * 10)


async def add_sample_products(connection: asyncpg.Connection):
    """Добавление тестовых товаров"""
    sample_products = [
        ("Керамическая ваза 'Закат'",
         "Уникальная ваза ручной работы с градиентом заката. Идеально подходит для живых цветов.",
         3500, 1, "Мария Петрова", "ceramic-vase.jpg"),
        ("Серебряное кольцо с аметистом",
         "Элегантное кольцо из серебра 925 пробы с натуральным аметистом.",
         4200, 2, "Анна Смирнова", "silver-ring.jpg"),
        ("Вязаный плед 'Облака'",
         "Мягкий плед из натуральной шерсти, связанный вручную. Размер 150x200 см.",
         5800, 3, "Елена Козлова", "knitted-blanket.jpg"),
        ("Деревянная шкатулка",
         "Резная шкатулка из массива дуба с инкрустацией. Ручная работа.",
         2900, 4, "Игорь Волков", "wooden-box.jpg"),
        ("Натуральное мыло 'Лаванда'",
         "Мыло ручной варки с эфирным маслом лаванды и сушеными цветами.",
         450, 5, "Ольга Новикова", "lavender-soap.jpg"),
        ("Соевая свеча 'Уют'",
         "Ароматическая свеча из соевого воска с запахом ванили и корицы.",
         890, 6, "Дарья Белова", "soy-candle.jpg"),
        ("Мягкая игрушка 'Мишка Тедди'",
         "Классический мишка Тедди ручной работы из натурального плюша.",
         1850, 7, "Светлана Орлова", "teddy-bear.jpg"),
        ("Акварель 'Весенний сад'",
         "Оригинальная акварельная картина с изображением цветущего сада.",
         7500, 8, "Александр Васильев", "watercolor-garden.jpg"),
        ("Керамическая тарелка",
         "Декоративная тарелка с ручной росписью в этническом стиле.",
         1200, 1, "Мария Петрова", "ceramic-plate.jpg"),
        ("Кожаная сумка",
         "Стильная сумка из натуральной кожи ручной работы.",
         6500, 9, "Михаил Кузнецов", "leather-bag.jpg")
    ]

    for product in sample_products:
        await connection.execute("""
            INSERT INTO products (name, description, price, category_id, author, image_url)
            VALUES ($1, $2, $3, $4, $5, $6)
        """, *product)


async def close_database_pool():
    """Закрытие пула соединений"""
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None
        logger.info("✅ Соединения с базой данных закрыты")


async def get_db_connection():
    """Получение соединения с базой данных"""
    global db_pool
    if db_pool is None:
        raise Exception("Пул соединений не инициализирован")
    return db_pool.acquire()


# Утилиты для работы с БД
async def fetch_all(query: str, *args):
    """Выполнение SELECT запроса с получением всех результатов"""
    global db_pool
    async with db_pool.acquire() as connection:
        return await connection.fetch(query, *args)


async def fetch_one(query: str, *args):
    """Выполнение SELECT запроса с получением одного результата"""
    global db_pool
    async with db_pool.acquire() as connection:
        return await connection.fetchrow(query, *args)


async def execute_query(query: str, *args):
    """Выполнение INSERT/UPDATE/DELETE запроса"""
    global db_pool
    async with db_pool.acquire() as connection:
        return await connection.execute(query, *args)