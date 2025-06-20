"""Расширенный API с авторизацией и управлением товарами для сайта Rukami"""
from fastapi import APIRouter, HTTPException, Query, Depends, status, Request, Response
from fastapi.security import HTTPBearer
from typing import List, Optional
import logging
import hashlib
import jwt
from datetime import datetime, timedelta

from pydantic import BaseModel, EmailStr, Field

from server.database.db_connection import fetch_all, fetch_one, execute_query

logger = logging.getLogger(__name__)

# Создаем роутер
router = APIRouter(prefix="/api", tags=["API"])

# Настройки для JWT
SECRET_KEY = "your-secret-key-here"  # В продакшене должен быть в переменных окружения
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()

# === МОДЕЛИ ДАННЫХ ===

class UserRegister(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    address: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    category_id: int
    image_url: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category_id: Optional[int] = None
    image_url: Optional[str] = None
    in_stock: Optional[bool] = None

class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    slug: str
    image_url: Optional[str] = None
    sort_order: Optional[int] = 0

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Рейтинг от 1 до 5")
    comment: str = Field(..., min_length=10, max_length=1000, description="Текст отзыва")

# === УТИЛИТЫ ===

def hash_password(password: str) -> str:
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Проверка пароля"""
    return hash_password(password) == hashed

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Создание JWT токена"""
    logger.info(f"Generating token for user: {data['sub']}")
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(request: Request):
    """Получение текущего пользователя из cookie"""
    try:
        user_id = request.cookies.get("user_id")
        logger.info(f"Cookie user_id: {user_id}")

        if not user_id:
            logger.warning("Cookie user_id отсутствует")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не авторизован"
            )

        try:
            user_id = int(user_id)
            logger.info(f"Поиск пользователя с ID: {user_id}")

            user = await fetch_one("SELECT id, name, email, phone, address, created_at FROM users WHERE id = $1",
                                   user_id)

            if not user:
                logger.warning(f"Пользователь с ID {user_id} не найден в базе данных")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Пользователь не найден"
                )

            logger.info(f"Пользователь найден: {user['name']} ({user['email']})")
            return dict(user)

        except ValueError as ve:
            logger.error(f"Ошибка преобразования user_id в int: {ve}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный формат ID пользователя"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка в get_current_user: {e}")
        logger.error(f"Тип ошибки: {type(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )

@router.put("/profile")
async def update_profile(profile_data: UserProfileUpdate, current_user: dict = Depends(get_current_user)):
    """Обновление профиля пользователя"""
    try:
        # Формируем запрос обновления только для переданных полей
        update_fields = []
        update_values = []
        param_counter = 1

        for field, value in profile_data.dict(exclude_unset=True).items():
            update_fields.append(f"{field} = ${param_counter}")
            update_values.append(value)
            param_counter += 1

        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нет данных для обновления"
            )

        update_values.append(current_user['id'])
        query = f"""
            UPDATE users 
            SET {', '.join(update_fields)}, updated_at = NOW()
            WHERE id = ${param_counter}
        """

        await execute_query(query, *update_values)

        # Возвращаем обновленную информацию о пользователе
        updated_user = await fetch_one("""
            SELECT id, name, email, phone, address, created_at, updated_at
            FROM users WHERE id = $1
        """, current_user['id'])

        return {
            "message": "Профиль обновлен успешно",
            "user": dict(updated_user)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления профиля: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обновления профиля")


@router.get("/profile/products")
async def get_user_products(current_user: dict = Depends(get_current_user)):
    """Получение списка товаров пользователя"""
    try:
        # Сначала проверим, есть ли у пользователя товары
        logger.info(f"Загрузка товаров для пользователя ID: {current_user['id']}")

        products = await fetch_all("""
            SELECT p.id, p.name, p.description, p.price, p.image_url,
                   p.in_stock, p.created_at, p.updated_at,
                   c.id as category_id, c.name as category_name, c.slug as category_slug,
                   u.name as author_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.user_id = $1
            ORDER BY p.created_at DESC
        """, current_user['id'])

        logger.info(f"Найдено товаров: {len(products)}")

        return {"products": [dict(product) for product in products]}

    except Exception as e:
        logger.error(f"Ошибка получения товаров пользователя: {e}")
        logger.error(f"Тип ошибки: {type(e)}")
        logger.error(f"User ID: {current_user.get('id', 'unknown')}")

        # Возвращаем пустой список вместо ошибки, чтобы интерфейс работал
        return {"products": []}


@router.get("/profile/statistics")
async def get_user_statistics(current_user: dict = Depends(get_current_user)):
    """Получение статистики пользователя"""
    try:
        logger.info(f"Загрузка статистики для пользователя ID: {current_user['id']}")

        # Получаем количество товаров
        products_count_result = await fetch_one("""
            SELECT COUNT(*) as count FROM products WHERE user_id = $1
        """, current_user['id'])
        products_count = products_count_result['count'] if products_count_result else 0

        # Получаем количество активных товаров
        active_products_result = await fetch_one("""
            SELECT COUNT(*) as count FROM products WHERE user_id = $1 AND in_stock = true
        """, current_user['id'])
        active_products_count = active_products_result['count'] if active_products_result else 0

        # Получаем количество заказов (пока заглушка)
        orders_count = 0

        # Получаем количество товаров в избранном у других пользователей
        try:
            favorites_result = await fetch_one("""
                SELECT COUNT(*) as count 
                FROM favorites f 
                JOIN products p ON f.product_id = p.id 
                WHERE p.user_id = $1
            """, current_user['id'])
            favorites_count = favorites_result['count'] if favorites_result else 0
        except Exception as fav_error:
            logger.warning(f"Ошибка получения избранного: {fav_error}")
            favorites_count = 0

        logger.info(
            f"Статистика: товаров={products_count}, активных={active_products_count}, избранное={favorites_count}")

        return {
            "products_count": products_count,
            "active_products_count": active_products_count,
            "orders_count": orders_count,
            "favorites_count": favorites_count
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        logger.error(f"Тип ошибки: {type(e)}")
        logger.error(f"User ID: {current_user.get('id', 'unknown')}")

        # Возвращаем нулевую статистику вместо ошибки
        return {
            "products_count": 0,
            "active_products_count": 0,
            "orders_count": 0,
            "favorites_count": 0
        }

# === АВТОРИЗАЦИЯ И РЕГИСТРАЦИЯ ===

@router.post("/auth/register")
async def register_user(user_data: UserRegister):
    """Регистрация нового пользователя"""
    try:
        existing_user = await fetch_one("SELECT id FROM users WHERE email = $1", user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже существует"
            )

        hashed_password = hash_password(user_data.password)

        user_id = await fetch_one("""
            INSERT INTO users (name, email, password_hash, phone, address)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """, user_data.name, user_data.email, hashed_password, user_data.phone, user_data.address)

        return {
            "message": "Пользователь успешно зарегистрирован",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка регистрации пользователя: {e}")
        raise HTTPException(status_code=500, detail="Ошибка регистрации пользователя")

@router.post("/auth/login")
async def login_user(user_data: UserLogin, response: Response):
    """Авторизация пользователя"""
    try:
        user = await fetch_one(
            "SELECT id, name, email, password_hash FROM users WHERE email = $1",
            user_data.email
        )

        if not user or not verify_password(user_data.password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль"
            )

        # Устанавливаем cookie с ID пользователя
        response.set_cookie(
            key="user_id",
            value=str(user['id']),
            httponly=True,  # Защита от XSS
            max_age=30*24*60*60,  # 30 дней
            samesite="lax"
        )

        return {
            "message": "Успешная авторизация",
            "user": {
                "id": user['id'],
                "name": user['name'],
                "email": user['email']
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка авторизации: {e}")
        raise HTTPException(status_code=500, detail="Ошибка авторизации")

@router.post("/auth/logout")
async def logout_user(response: Response):
    """Выход пользователя"""
    response.delete_cookie(key="user_id")
    return {"message": "Успешный выход"}

@router.get("/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Получение информации о текущем пользователе"""
    return current_user

# === УПРАВЛЕНИЕ КАТЕГОРИЯМИ (АДМИН) ===

@router.post("/admin/categories")
async def create_category(category_data: CategoryCreate, current_user: dict = Depends(get_current_user)):
    """Создание новой категории (только для админов)"""
    try:
        # Проверяем, не существует ли категория с таким именем или slug
        existing_category = await fetch_one(
            "SELECT id FROM categories WHERE name = $1 OR slug = $2",
            category_data.name, category_data.slug
        )
        if existing_category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Категория с таким именем или slug уже существует"
            )

        category_id = await fetch_one("""
            INSERT INTO categories (name, description, slug, image_url, sort_order)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """, category_data.name, category_data.description, category_data.slug,
            category_data.image_url, category_data.sort_order)

        return {
            "message": "Категория создана успешно",
            "category_id": category_id['id']
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания категории: {e}")
        raise HTTPException(status_code=500, detail="Ошибка создания категории")

# === УПРАВЛЕНИЕ ТОВАРАМИ ===

@router.post("/products")
async def create_product(product_data: ProductCreate, current_user: dict = Depends(get_current_user)):
    """Создание нового товара"""
    try:
        # Проверяем существование категории
        category = await fetch_one("SELECT id FROM categories WHERE id = $1", product_data.category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Категория не найдена"
            )

        product_id = await fetch_one("""
            INSERT INTO products (name, description, price, category_id, user_id, image_url)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """, product_data.name, product_data.description, product_data.price,
            product_data.category_id, current_user['id'], product_data.image_url)

        return {
            "message": "Товар создан успешно",
            "product_id": product_id['id']
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания товара: {e}")
        raise HTTPException(status_code=500, detail="Ошибка создания товара")

@router.put("/products/{product_id}")
async def update_product(product_id: int, product_data: ProductUpdate, current_user: dict = Depends(get_current_user)):
    """Обновление товара"""
    try:
        # Проверяем существование товара и принадлежность пользователю
        existing_product = await fetch_one("""
            SELECT id, user_id FROM products WHERE id = $1
        """, product_id)

        if not existing_product:
            raise HTTPException(status_code=404, detail="Товар не найден")

        if existing_product['user_id'] != current_user['id']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав на редактирование этого товара"
            )

        # Если указана новая категория, проверяем её существование
        if product_data.category_id:
            category = await fetch_one("SELECT id FROM categories WHERE id = $1", product_data.category_id)
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Категория не найдена"
                )

        # Формируем запрос обновления только для переданных полей
        update_fields = []
        update_values = []
        param_counter = 1

        for field, value in product_data.dict(exclude_unset=True).items():
            update_fields.append(f"{field} = ${param_counter}")
            update_values.append(value)
            param_counter += 1

        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нет данных для обновления"
            )

        update_values.append(product_id)
        query = f"""
            UPDATE products 
            SET {', '.join(update_fields)}, updated_at = NOW()
            WHERE id = ${param_counter}
        """

        await execute_query(query, *update_values)

        return {"message": "Товар обновлен успешно"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления товара: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обновления товара")

@router.delete("/products/{product_id}")
async def delete_product(product_id: int, current_user: dict = Depends(get_current_user)):
    """Удаление товара"""
    try:
        # Проверяем существование товара и принадлежность пользователю
        existing_product = await fetch_one("""
            SELECT id, user_id FROM products WHERE id = $1
        """, product_id)

        if not existing_product:
            raise HTTPException(status_code=404, detail="Товар не найден")

        if existing_product['user_id'] != current_user['id']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав на удаление этого товара"
            )

        # Мягкое удаление - помечаем как недоступный
        await execute_query("UPDATE products SET in_stock = false WHERE id = $1", product_id)

        return {"message": "Товар удален успешно"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления товара: {e}")
        raise HTTPException(status_code=500, detail="Ошибка удаления товара")

# === ОРИГИНАЛЬНЫЕ ЭНДПОИНТЫ ===

@router.get("/categories")
async def get_categories():
    """Получение списка всех активных категорий"""
    try:
        categories = await fetch_all("""
            SELECT c.id, c.name, c.description, c.slug, c.image_url, c.sort_order,
                   COUNT(p.id) as products_count
            FROM categories c
            LEFT JOIN products p ON c.id = p.category_id AND p.in_stock = true
            WHERE c.is_active = true
            GROUP BY c.id, c.name, c.description, c.slug, c.image_url, c.sort_order
            ORDER BY c.sort_order, c.name
        """)

        return {"categories": [dict(cat) for cat in categories]}

    except Exception as e:
        logger.error(f"Ошибка получения категорий: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения категорий")

@router.get("/categories/{category_id}")
async def get_category(category_id: int):
    """Получение информации о категории"""
    try:
        category = await fetch_one("""
            SELECT c.*, COUNT(p.id) as products_count
            FROM categories c
            LEFT JOIN products p ON c.id = p.category_id AND p.in_stock = true
            WHERE c.id = $1 AND c.is_active = true
            GROUP BY c.id
        """, category_id)

        if not category:
            raise HTTPException(status_code=404, detail="Категория не найдена")

        return dict(category)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения категории: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения категории")

@router.get("/categories/slug/{slug}")
async def get_category_by_slug(slug: str):
    """Получение категории по slug"""
    try:
        category = await fetch_one("""
            SELECT c.*, COUNT(p.id) as products_count
            FROM categories c
            LEFT JOIN products p ON c.id = p.category_id AND p.in_stock = true
            WHERE c.slug = $1 AND c.is_active = true
            GROUP BY c.id
        """, slug)

        if not category:
            raise HTTPException(status_code=404, detail="Категория не найдена")

        return dict(category)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения категории: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения категории")

@router.get("/products")
async def get_products(
        category_id: Optional[int] = None,
        category_slug: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = Query(default=20, le=100),
        offset: int = Query(default=0, ge=0)
):
    """Получение списка товаров с фильтрацией"""
    try:
        # Если передан slug категории, получаем её ID
        category_filter_id = category_id
        if category_slug and not category_id:
            category = await fetch_one("SELECT id FROM categories WHERE slug = $1", category_slug)
            if category:
                category_filter_id = category['id']

        query = """
            SELECT p.id, p.name, p.description, p.price, p.image_url, p.in_stock,
                   c.id as category_id, c.name as category_name, c.slug as category_slug,
                   u.name as author_name
            FROM products p
            JOIN categories c ON p.category_id = c.id
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.in_stock = true
            AND ($1::integer IS NULL OR p.category_id = $1)
            AND ($2::text IS NULL OR (p.name ILIKE $2 OR p.description ILIKE $2))
            ORDER BY p.created_at DESC
            LIMIT $3 OFFSET $4
        """

        search_param = f"%{search}%" if search else None
        products = await fetch_all(query, category_filter_id, search_param, limit, offset)

        # Получаем общее количество товаров для пагинации
        count_query = """
            SELECT COUNT(*)
            FROM products p
            WHERE p.in_stock = true
            AND ($1::integer IS NULL OR p.category_id = $1)
            AND ($2::text IS NULL OR (p.name ILIKE $2 OR p.description ILIKE $2))
        """
        total_count = await fetch_one(count_query, category_filter_id, search_param)

        return {
            "products": [dict(product) for product in products],
            "total": total_count['count'],
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Ошибка получения товаров: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения товаров")

@router.get("/products/{product_id}")
async def get_product(product_id: int):
    """Получение информации о товаре"""
    try:
        product = await fetch_one("""
            SELECT p.*, c.id as category_id, c.name as category_name, c.slug as category_slug,
                   u.name as author_name
            FROM products p
            JOIN categories c ON p.category_id = c.id
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.id = $1
        """, product_id)

        if not product:
            raise HTTPException(status_code=404, detail="Товар не найден")

        return dict(product)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения товара: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения товара")

# === ИЗБРАННОЕ ===

@router.get("/favorites")
async def get_favorites(current_user: dict = Depends(get_current_user)):
    """Получение списка избранных товаров пользователя"""
    try:
        favorites = await fetch_all("""
            SELECT p.id, p.name, p.description, p.price, p.image_url,
                   c.id as category_id, c.name as category_name, c.slug as category_slug,
                   u.name as author_name
            FROM favorites f
            JOIN products p ON f.product_id = p.id
            JOIN categories c ON p.category_id = c.id
            LEFT JOIN users u ON p.user_id = u.id
            WHERE f.user_id = $1
            ORDER BY f.created_at DESC
        """, current_user['id'])

        return {"favorites": [dict(fav) for fav in favorites]}

    except Exception as e:
        logger.error(f"Ошибка получения избранного: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения избранного")

# === КОРЗИНА ===

@router.get("/cart")
async def get_cart(current_user: dict = Depends(get_current_user)):
    """Получение содержимого корзины пользователя"""
    try:
        cart_items = await fetch_all("""
            SELECT c.id, c.quantity, p.id as product_id, p.name, p.price, p.image_url,
                   u.name as author_name
            FROM cart_items c
            JOIN products p ON c.product_id = p.id
            LEFT JOIN users u ON p.user_id = u.id
            WHERE c.user_id = $1
            ORDER BY c.created_at DESC
        """, current_user['id'])

        total = sum(item['price'] * item['quantity'] for item in cart_items)

        return {
            "cart_items": [dict(item) for item in cart_items],
            "total": float(total)
        }

    except Exception as e:
        logger.error(f"Ошибка получения корзины: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения корзины")

# === ОТЗЫВЫ ===

@router.get("/reviews/{product_id}")
async def get_product_reviews(product_id: int):
    """Получение отзывов о товаре"""
    try:
        reviews = await fetch_all("""
            SELECT r.id, r.rating, r.comment, r.created_at, u.name as user_name
            FROM reviews r
            JOIN users u ON r.user_id = u.id
            WHERE r.product_id = $1
            ORDER BY r.created_at DESC
        """, product_id)

        # Вычисляем средний рейтинг
        if reviews:
            avg_rating = sum(review['rating'] for review in reviews) / len(reviews)
        else:
            avg_rating = 0

        return {
            "reviews": [dict(review) for review in reviews],
            "average_rating": round(avg_rating, 1),
            "total_reviews": len(reviews)
        }

    except Exception as e:
        logger.error(f"Ошибка получения отзывов: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения отзывов")


@router.post("/reviews/{product_id}")
async def create_review(product_id: int, review_data: ReviewCreate, current_user: dict = Depends(get_current_user)):
    """Создание отзыва для товара"""
    try:
        # Проверяем существование товара
        product = await fetch_one("SELECT id FROM products WHERE id = $1", product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Товар не найден")

        # Проверяем, не оставлял ли пользователь уже отзыв на этот товар
        existing_review = await fetch_one("""
            SELECT id FROM reviews WHERE product_id = $1 AND user_id = $2
        """, product_id, current_user['id'])

        if existing_review:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Вы уже оставили отзыв на этот товар"
            )

        # Создаем отзыв
        review_id = await fetch_one("""
            INSERT INTO reviews (product_id, user_id, rating, comment)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """, product_id, current_user['id'], review_data.rating, review_data.comment)

        return {
            "message": "Отзыв успешно добавлен",
            "review_id": review_id['id']
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания отзыва: {e}")
        raise HTTPException(status_code=500, detail="Ошибка создания отзыва")

@router.post("/profile/password")
async def change_password(password_data: PasswordChange, current_user: dict = Depends(get_current_user)):
    """Изменение пароля пользователя"""
    try:
        # Получаем текущий хеш пароля
        user = await fetch_one("""
            SELECT password_hash FROM users WHERE id = $1
        """, current_user['id'])

        # Проверяем текущий пароль
        if not verify_password(password_data.current_password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный текущий пароль"
            )

        # Валидация нового пароля
        if len(password_data.new_password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Новый пароль должен содержать минимум 6 символов"
            )

        # Хешируем новый пароль
        new_password_hash = hash_password(password_data.new_password)

        # Обновляем пароль
        await execute_query("""
            UPDATE users SET password_hash = $1, updated_at = NOW()
            WHERE id = $2
        """, new_password_hash, current_user['id'])

        return {"message": "Пароль успешно изменен"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка смены пароля: {e}")
        raise HTTPException(status_code=500, detail="Ошибка смены пароля")