"""API эндпоинты для сайта Rukami"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging

from server.database.db_connection import fetch_all, fetch_one, execute_query

logger = logging.getLogger(__name__)

# Создаем роутер
router = APIRouter(prefix="/api", tags=["API"])


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


# === ТОВАРЫ ===

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
            SELECT p.id, p.name, p.description, p.price, p.author, p.image_url, p.in_stock,
                   c.id as category_id, c.name as category_name, c.slug as category_slug
            FROM products p
            JOIN categories c ON p.category_id = c.id
            WHERE p.in_stock = true
            AND ($1::integer IS NULL OR p.category_id = $1)
            AND ($2::text IS NULL OR (p.name ILIKE $2 OR p.description ILIKE $2 OR p.author ILIKE $2))
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
            AND ($2::text IS NULL OR (p.name ILIKE $2 OR p.description ILIKE $2 OR p.author ILIKE $2))
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
            SELECT p.*, c.id as category_id, c.name as category_name, c.slug as category_slug
            FROM products p
            JOIN categories c ON p.category_id = c.id
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


@router.get("/products/category/{category_id}")
async def get_products_by_category(
        category_id: int,
        limit: int = Query(default=20, le=100),
        offset: int = Query(default=0, ge=0)
):
    """Получение товаров определенной категории"""
    try:
        # Проверяем существование категории
        category = await fetch_one("SELECT id, name FROM categories WHERE id = $1", category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Категория не найдена")

        products = await fetch_all("""
            SELECT p.id, p.name, p.description, p.price, p.author, p.image_url, p.in_stock,
                   c.name as category_name, c.slug as category_slug
            FROM products p
            JOIN categories c ON p.category_id = c.id
            WHERE p.category_id = $1 AND p.in_stock = true
            ORDER BY p.created_at DESC
            LIMIT $2 OFFSET $3
        """, category_id, limit, offset)

        total_count = await fetch_one(
            "SELECT COUNT(*) FROM products WHERE category_id = $1 AND in_stock = true",
            category_id
        )

        return {
            "category": dict(category),
            "products": [dict(product) for product in products],
            "total": total_count['count'],
            "limit": limit,
            "offset": offset
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения товаров категории: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения товаров категории")


# === ИЗБРАННОЕ ===

@router.get("/favorites/{user_id}")
async def get_favorites(user_id: int):
    """Получение списка избранных товаров пользователя"""
    try:
        favorites = await fetch_all("""
            SELECT p.id, p.name, p.description, p.price, p.category, p.author, p.image_url
            FROM favorites f
            JOIN products p ON f.product_id = p.id
            WHERE f.user_id = $1
            ORDER BY f.created_at DESC
        """, user_id)

        return {"favorites": [dict(fav) for fav in favorites]}

    except Exception as e:
        logger.error(f"Ошибка получения избранного: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения избранного")


@router.post("/favorites/{user_id}/{product_id}")
async def add_to_favorites(user_id: int, product_id: int):
    """Добавление товара в избранное"""
    try:
        # Проверяем существование товара
        product = await fetch_one("SELECT id FROM products WHERE id = $1", product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Товар не найден")

        await execute_query("""
            INSERT INTO favorites (user_id, product_id)
            VALUES ($1, $2)
            ON CONFLICT (user_id, product_id) DO NOTHING
        """, user_id, product_id)

        return {"message": "Товар добавлен в избранное"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка добавления в избранное: {e}")
        raise HTTPException(status_code=500, detail="Ошибка добавления в избранное")


@router.delete("/favorites/{user_id}/{product_id}")
async def remove_from_favorites(user_id: int, product_id: int):
    """Удаление товара из избранного"""
    try:
        await execute_query("""
            DELETE FROM favorites
            WHERE user_id = $1 AND product_id = $2
        """, user_id, product_id)

        return {"message": "Товар удален из избранного"}

    except Exception as e:
        logger.error(f"Ошибка удаления из избранного: {e}")
        raise HTTPException(status_code=500, detail="Ошибка удаления из избранного")


# === КОРЗИНА ===

@router.get("/cart/{user_id}")
async def get_cart(user_id: int):
    """Получение содержимого корзины пользователя"""
    try:
        cart_items = await fetch_all("""
            SELECT c.id, c.quantity, p.id as product_id, p.name, p.price, p.image_url
            FROM cart_items c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = $1
            ORDER BY c.created_at DESC
        """, user_id)

        total = sum(item['price'] * item['quantity'] for item in cart_items)

        return {
            "cart_items": [dict(item) for item in cart_items],
            "total": float(total)
        }

    except Exception as e:
        logger.error(f"Ошибка получения корзины: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения корзины")


@router.post("/cart/{user_id}/{product_id}")
async def add_to_cart(user_id: int, product_id: int, quantity: int = 1):
    """Добавление товара в корзину"""
    try:
        # Проверяем существование товара
        product = await fetch_one("SELECT id FROM products WHERE id = $1", product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Товар не найден")

        await execute_query("""
            INSERT INTO cart_items (user_id, product_id, quantity)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, product_id)
            DO UPDATE SET quantity = cart_items.quantity + $3, updated_at = NOW()
        """, user_id, product_id, quantity)

        return {"message": "Товар добавлен в корзину"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка добавления в корзину: {e}")
        raise HTTPException(status_code=500, detail="Ошибка добавления в корзину")


@router.put("/cart/{user_id}/{product_id}")
async def update_cart_quantity(user_id: int, product_id: int, quantity: int):
    """Обновление количества товара в корзине"""
    try:
        if quantity <= 0:
            # Удаляем товар из корзины если количество 0 или меньше
            await execute_query("""
                DELETE FROM cart_items
                WHERE user_id = $1 AND product_id = $2
            """, user_id, product_id)
        else:
            await execute_query("""
                UPDATE cart_items
                SET quantity = $3, updated_at = NOW()
                WHERE user_id = $1 AND product_id = $2
            """, user_id, product_id, quantity)

        return {"message": "Количество обновлено"}

    except Exception as e:
        logger.error(f"Ошибка обновления корзины: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обновления корзины")


@router.delete("/cart/{user_id}/{product_id}")
async def remove_from_cart(user_id: int, product_id: int):
    """Удаление товара из корзины"""
    try:
        await execute_query("""
            DELETE FROM cart_items
            WHERE user_id = $1 AND product_id = $2
        """, user_id, product_id)

        return {"message": "Товар удален из корзины"}

    except Exception as e:
        logger.error(f"Ошибка удаления из корзины: {e}")
        raise HTTPException(status_code=500, detail="Ошибка удаления из корзины")


@router.delete("/cart/{user_id}")
async def clear_cart(user_id: int):
    """Очистка корзины пользователя"""
    try:
        await execute_query("DELETE FROM cart_items WHERE user_id = $1", user_id)
        return {"message": "Корзина очищена"}

    except Exception as e:
        logger.error(f"Ошибка очистки корзины: {e}")
        raise HTTPException(status_code=500, detail="Ошибка очистки корзины")


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


@router.post("/reviews/{user_id}/{product_id}")
async def add_review(user_id: int, product_id: int, rating: int, comment: str = ""):
    """Добавление отзыва о товаре"""
    try:
        if rating < 1 or rating > 5:
            raise HTTPException(status_code=400, detail="Рейтинг должен быть от 1 до 5")

        # Проверяем существование товара
        product = await fetch_one("SELECT id FROM products WHERE id = $1", product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Товар не найден")

        await execute_query("""
            INSERT INTO reviews (user_id, product_id, rating, comment)
            VALUES ($1, $2, $3, $4)
        """, user_id, product_id, rating, comment)

        return {"message": "Отзыв добавлен"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка добавления отзыва: {e}")
        raise HTTPException(status_code=500, detail="Ошибка добавления отзыва")


# === ПОЛЬЗОВАТЕЛИ (базовые эндпоинты) ===

@router.get("/users/{user_id}")
async def get_user(user_id: int):
    """Получение информации о пользователе"""
    try:
        user = await fetch_one("""
            SELECT id, name, email, phone, address, created_at
            FROM users WHERE id = $1
        """, user_id)

        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        return dict(user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения пользователя: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения пользователя")