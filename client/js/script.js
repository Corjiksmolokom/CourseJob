// Глобальные переменные
let cart = [];
let favorites = [];
let currentPage = 1;
const productsPerPage = 6;
let currentCategory = null;
let currentSearch = '';
let totalProducts = 0;
let allProducts = []; // Кэш всех товаров

// Инициализация приложения
document.addEventListener('DOMContentLoaded', async function() {
    try {
        await loadProductsFromDatabase();
        setupEventListeners();
        updateCartCount();
    } catch (error) {
        console.error('Ошибка инициализации:', error);
        showNotification('Ошибка загрузки данных');
    }
});

// Загрузка товаров из базы данных через API
async function loadProductsFromDatabase() {
    try {
        const productsContainer = document.getElementById('productsContainer');
        const loadMoreBtn = document.getElementById('loadMoreBtn');
        
        // Показываем индикатор загрузки
        productsContainer.innerHTML = '<div style="text-align: center; padding: 20px;">Загрузка товаров...</div>';
        
        // Делаем запрос к API
        const response = await fetch(`/api/products?limit=${productsPerPage}&offset=${(currentPage - 1) * productsPerPage}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        totalProducts = data.total;
        allProducts = currentPage === 1 ? data.products : [...allProducts, ...data.products];
        
        renderProducts(data.products);
        
        // Показываем кнопку "Загрузить еще", если есть еще товары
        const remainingProducts = totalProducts - (currentPage * productsPerPage);
        if (remainingProducts > 0) {
            loadMoreBtn.style.display = 'block';
            loadMoreBtn.textContent = `Загрузить еще (${remainingProducts})`;
        } else {
            loadMoreBtn.style.display = 'none';
        }
        
    } catch (error) {
        console.error('Ошибка загрузки товаров:', error);
        document.getElementById('productsContainer').innerHTML = 
            '<div style="text-align: center; padding: 20px; color: red;">Ошибка загрузки товаров</div>';
    }
}

// Рендеринг товаров в стиле оригинального дизайна
function renderProducts(products) {
    const productsContainer = document.getElementById('productsContainer');
    
    if (products.length === 0) {
        productsContainer.innerHTML = '<div style="text-align: center; padding: 20px;">Товары не найдены</div>';
        return;
    }
    
    let productsHTML = '';
    
    // Создаем товары по 3 в ряд (как в оригинальном дизайне)
    for (let i = 0; i < products.length; i += 3) {
        const row = products.slice(i, i + 3);
        productsHTML += createProductRow(row, i);
    }
    
    if (currentPage === 1) {
        productsContainer.innerHTML = productsHTML;
    } else {
        productsContainer.innerHTML += productsHTML;
    }
}

// Создание ряда товаров (3 товара в ряд)
function createProductRow(products, startIndex) {
    const baseTop = 334 + Math.floor(startIndex / 3) * 695; // 695px между рядами
    
    let rowHTML = `<div class="product-row" style="position: absolute; width: 1168px; height: 530px; top: ${baseTop}px; left: 140px;">`;
    
    products.forEach((product, index) => {
        const leftPosition = index * 414; // 414px между товарами
        rowHTML += createProductCard(product, leftPosition);
    });
    
    rowHTML += '</div>';
    return rowHTML;
}

// Создание карточки товара
function createProductCard(product, leftPosition) {
    const isFavorite = favorites.includes(product.id);
    const buttonTop = 417; // Позиция кнопки "В корзину"
    
    return `
        <!-- Основная карточка товара -->
        <div class="product-main-card" style="position: absolute; width: 340px; height: 400px; top: 0; left: ${leftPosition}px; background-color: #d9d9d9; border-radius: 20px; background-image: url('${product.image_url || ''}'); background-size: cover; background-position: center;">
        </div>
        
        <!-- Цена товара (слева вверху) -->
        <div class="product-price" style="position: absolute; top: 15px; left: ${leftPosition + 15}px; background-color: rgba(255,255,255,0.9); padding: 8px 12px; border-radius: 15px; font-family: 'Unbounded', Helvetica; font-weight: 600; color: #000; font-size: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            ${formatPrice(product.price)} ₽
        </div>

        <!-- Кнопка избранного (справа вверху) -->
        <div class="favorite-btn ${isFavorite ? 'active' : ''}" style="position: absolute; top: 15px; left: ${leftPosition + 285}px; width: 40px; height: 40px; background-color: rgba(255,255,255,0.9); border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 18px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); transition: all 0.2s ease;" onclick="toggleFavorite(${product.id})">
            ${isFavorite ? '❤️' : '🤍'}
        </div>

        <!-- Название товара -->
        <div class="product-name" style="position: absolute; width: 214px; height: 49px; top: ${buttonTop}px; left: ${leftPosition}px; background-color: #d9d9d9; display: flex; align-items: center; justify-content: center; font-family: 'Inter', Helvetica; font-size: 14px; color: #373737;">
            ${product.name}
        </div>

        <!-- Автор товара -->
        <div class="product-author" style="position: absolute; width: 340px; height: 49px; top: ${buttonTop + 64}px; left: ${leftPosition}px; background-color: #d9d9d9; display: flex; align-items: center; justify-content: center; font-family: 'Inter', Helvetica; font-size: 12px; color: #666;">
            ${product.description || 'Описание не указано'}
        </div>

        <!-- Кнопка "В корзину" -->
        <div class="add-to-cart-wrapper" style="position: absolute; width: 340px; height: 65px; top: ${buttonTop + 128}px; left: ${leftPosition}px; background-color: #fddbe9; border-radius: 30px; cursor: pointer; transition: all 0.2s ease;" onclick="addToCart(${product.id})" onmouseover="this.style.backgroundColor='#fcb8d4'" onmouseout="this.style.backgroundColor='#fddbe9'">
            <div class="cart-btn-text" style="position: absolute; top: 18px; left: 95px; font-family: 'Unbounded', Helvetica; font-weight: 400; color: #000000; font-size: 24px; letter-spacing: 0; line-height: normal;">
                В корзину
            </div>
        </div>
    `;
}

// Форматирование цены
function formatPrice(price) {
    return price.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

// Добавление товара в корзину
async function addToCart(productId) {
    try {
        const product = allProducts.find(p => p.id === productId);
        if (!product) {
            showNotification('Товар не найден');
            return;
        }

        const existingItem = cart.find(item => item.id === productId);
        if (existingItem) {
            existingItem.quantity += 1;
        } else {
            cart.push({ ...product, quantity: 1 });
        }
        
        updateCartCount();
        showNotification(`${product.name} добавлен в корзину`);
        
        // Анимация кнопки
        const button = event.target.closest('.add-to-cart-wrapper');
        if (button) {
            button.style.transform = 'scale(0.95)';
            setTimeout(() => {
                button.style.transform = 'scale(1)';
            }, 150);
        }
        
    } catch (error) {
        console.error('Ошибка добавления в корзину:', error);
        showNotification('Ошибка добавления товара');
    }
}

// Переключение избранного
async function toggleFavorite(productId) {
    try {
        const product = allProducts.find(p => p.id === productId);
        if (!product) {
            showNotification('Товар не найден');
            return;
        }

        const index = favorites.indexOf(productId);
        if (index > -1) {
            favorites.splice(index, 1);
        } else {
            favorites.push(productId);
        }
        
        // Обновляем иконку избранного
        const favoriteBtn = event.target;
        if (favoriteBtn) {
            if (favorites.includes(productId)) {
                favoriteBtn.textContent = '❤️';
                favoriteBtn.classList.add('active');
            } else {
                favoriteBtn.textContent = '🤍';
                favoriteBtn.classList.remove('active');
            }
        }
        
        const action = favorites.includes(productId) ? 'добавлен в избранное' : 'удален из избранного';
        showNotification(`${product.name} ${action}`);
        
    } catch (error) {
        console.error('Ошибка изменения избранного:', error);
        showNotification('Ошибка изменения избранного');
    }
}

// Обновление счетчика корзины
function updateCartCount() {
    const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
    // Если есть элемент счетчика корзины в шапке
    const cartCount = document.querySelector('.cart-count');
    if (cartCount) {
        cartCount.textContent = totalItems;
    }
}

// Загрузка дополнительных товаров
async function loadMoreProducts() {
    try {
        currentPage++;
        await loadProductsFromDatabase();
    } catch (error) {
        console.error('Ошибка загрузки дополнительных товаров:', error);
        showNotification('Ошибка загрузки товаров');
    }
}

// Показ уведомления
function showNotification(message) {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        background: linear-gradient(135deg, #ff6b9d, #ff8cc8);
        color: white;
        padding: 16px 24px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(255, 107, 157, 0.3);
        z-index: 10000;
        font-weight: 500;
        transform: translateX(100%);
        transition: transform 0.3s ease;
    `;
    notification.textContent = message;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 100);

    setTimeout(() => {
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (document.body.contains(notification)) {
                document.body.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

// Настройка обработчиков событий
function setupEventListeners() {
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', loadMoreProducts);
    }
    
    // Обработчик клика по логотипу для перезагрузки товаров
    const logo = document.querySelector('.text-wrapper');
    if (logo) {
        logo.addEventListener('click', function() {
             window.location.href = '/';
        });
    }
    
    // Клавиатурные сочетания
    document.addEventListener('keydown', function(e) {
        if (e.key === 'F5' || (e.ctrlKey && e.key === 'r')) {
            e.preventDefault();
            currentPage = 1;
            loadProductsFromDatabase();
        }
    });
}

// Поиск товаров (базовая реализация)
async function searchProducts(query) {
    try {
        const response = await fetch(`/api/products?search=${encodeURIComponent(query)}&limit=${productsPerPage}`);
        if (!response.ok) throw new Error('Ошибка поиска');
        
        const data = await response.json();
        allProducts = data.products;
        totalProducts = data.total;
        currentPage = 1;
        
        renderProducts(data.products);
        showNotification(`Найдено ${totalProducts} товаров`);
        
    } catch (error) {
        console.error('Ошибка поиска:', error);
        showNotification('Ошибка выполнения поиска');
    }
}

// Фильтрация по категории
async function filterByCategory(categorySlug) {
    try {
        const url = categorySlug ? `/api/products?category_slug=${categorySlug}&limit=${productsPerPage}` : `/api/products?limit=${productsPerPage}`;
        const response = await fetch(url);
        
        if (!response.ok) throw new Error('Ошибка фильтрации');
        
        const data = await response.json();
        allProducts = data.products;
        totalProducts = data.total;
        currentPage = 1;
        currentCategory = categorySlug;
        
        renderProducts(data.products);
        showNotification(`Найдено ${totalProducts} товаров в категории`);
        
    } catch (error) {
        console.error('Ошибка фильтрации:', error);
        showNotification('Ошибка фильтрации товаров');
    }
}