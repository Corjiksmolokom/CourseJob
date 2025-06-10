import logging
import os
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from server.database.db_connection import init_database, close_database_pool
from server.api.api_implementation import router as api_router
from server.config import settings


logging.basicConfig(
    level=getattr(logging, "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("rukami.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info("🚀 Запуск Rukami API...")

    # Инициализация базы данных при запуске
    try:
        await init_database()
        logger.info("✅ База данных успешно инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации базы данных: {e}")
        raise

    yield

    # Закрытие соединений при остановке
    logger.info("🛑 Остановка Rukami API...")
    try:
        await close_database_pool()
        logger.info("✅ Соединения с базой данных закрыты")
    except Exception as e:
        logger.error(f"❌ Ошибка при закрытии соединений: {e}")


# Создание FastAPI приложения
app = FastAPI(
    title="Rukami API",
    description="API для проекта Rukami - Творчество в твоих руках",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
    lifespan=lifespan
)

# Статические файлы для клиента (CSS, JS, изображения)
if os.path.exists("client"):
    app.mount("/styles", StaticFiles(directory="client/styles"), name="styles")
    app.mount("/img", StaticFiles(directory="client/img"), name="images")
    app.mount("/js", StaticFiles(directory="client/js   "), name="scripts")

# Статические файлы для загрузок
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене лучше указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение API роутов
app.include_router(api_router)

# Статические файлы (для изображений, CSS, JS)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# Корневой эндпоинт
@app.get("/", response_class=HTMLResponse)
async def root():
    """Главная страница"""
    try:
        # Получаем абсолютный путь к файлу index.html
        current_dir = os.path.dirname(__file__)
        html_path = os.path.join(current_dir, "..", "client", "index.html")

        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            return HTMLResponse(content=html_content)
        else:
            # Если файл не найден, возвращаем простую HTML страницу
            return HTMLResponse(content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Rukami - Творчество в твоих руках</title>
                <meta charset="utf-8">
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; text-align: center; }
                    h1 { color: #333; }
                    .links { margin-top: 30px; }
                    .links a { margin: 0 10px; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }
                    .links a:hover { background: #0056b3; }
                </style>
            </head>
            <body>
                <h1>🎨 Rukami API</h1>
                <p>Добро пожаловать в API магазина творческих работ ручной работы!</p>
                <div class="links">
                    <a href="/docs">📚 API Документация</a>
                    <a href="/status">⚡ Статус сервера</a>
                    <a href="/api/categories">📂 Категории товаров</a>
                </div>
            </body>
            </html>
            """)

    except Exception as e:
        logger.error(f"Ошибка загрузки главной страницы: {e}")
        return HTMLResponse(content=f"<h1>Ошибка загрузки: {e}</h1>", status_code=500)


# Эндпоинт для проверки статуса
@app.get("/status")
async def get_status():
    """Проверка статуса сервера"""
    return {
        "status": "running",
        "service": "Rukami API",
        "version": "1.0.0",
        "database": "PostgreSQL",
        "description": "API для магазина творческих работ ручной работы"
    }


# Эндпоинт для информации о API
@app.get("/info")
async def get_info():
    """Информация о доступных эндпоинтах"""
    return {
        "service": "Rukami API",
        "version": "1.0.0",
        "endpoints": {
            "documentation": {
                "/docs": "Swagger UI документация",
                "/redoc": "ReDoc документация"
            },
            "products": {
                "GET /api/products": "Список товаров с фильтрацией",
                "GET /api/products/{id}": "Информация о товаре",
                "GET /api/categories": "Список категорий"
            },
            "favorites": {
                "GET /api/favorites/{user_id}": "Избранные товары пользователя",
                "POST /api/favorites/{user_id}/{product_id}": "Добавить в избранное",
                "DELETE /api/favorites/{user_id}/{product_id}": "Удалить из избранного"
            },
            "cart": {
                "GET /api/cart/{user_id}": "Корзина пользователя",
                "POST /api/cart/{user_id}/{product_id}": "Добавить в корзину",
                "PUT /api/cart/{user_id}/{product_id}": "Обновить количество",
                "DELETE /api/cart/{user_id}/{product_id}": "Удалить из корзины",
                "DELETE /api/cart/{user_id}": "Очистить корзину"
            },
            "reviews": {
                "GET /api/reviews/{product_id}": "Отзывы о товаре",
                "POST /api/reviews/{user_id}/{product_id}": "Добавить отзыв"
            },
            "users": {
                "GET /api/users/{user_id}": "Информация о пользователе"
            }
        }
    }


# Обработчик ошибок 404
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Эндпоинт не найден",
            "message": "Проверьте правильность URL",
            "available_endpoints": [
                "/",
                "/status",
                "/info",
                "/api/products",
                "/api/categories",
                "/docs",
                "/redoc"
            ]
        }
    )


# Обработчик общих ошибок сервера
@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Внутренняя ошибка сервера: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Внутренняя ошибка сервера",
            "message": "Попробуйте позже или обратитесь к администратору"
        }
    )


if __name__ == '__main__':
    # Логируем информацию о запуске
    logger.info(f"🌐 Запуск сервера на http://{settings.host}:{settings.port}")
    logger.info(f"📊 Режим отладки: {settings.debug}")
    logger.info(f"🗃️  База данных: {settings.db_host}:{settings.db_port}/{settings.db_name}")

    # Создаём папку для загрузок если её нет
    if not os.path.exists(settings.upload_folder):
        os.makedirs(settings.upload_folder)
        logger.info(f"📁 Создана папка для загрузок: {settings.upload_folder}")

    # Создаём папку для статических файлов если её нет
    if not os.path.exists("static"):
        os.makedirs("static")
        logger.info("📁 Создана папка для статических файлов: static")

    uvicorn.run(
        "server:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )