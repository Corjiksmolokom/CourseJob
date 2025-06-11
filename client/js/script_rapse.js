// Application state
let cart = [];
let favorites = [];
let currentPage = 1;
const productsPerPage = 6;
let currentCategory = null;
let currentSearch = '';
let totalProducts = 0;

// DOM elements
const categoriesGrid = document.getElementById('categoriesGrid');
const productsGrid = document.getElementById('productsGrid');
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const loadMoreBtn = document.getElementById('loadMoreBtn');
const scrollTopBtn = document.getElementById('scrollTopBtn');
const cartBtn = document.getElementById('cartBtn');
const cartCount = document.querySelector('.cart-count');
const telegramBtn = document.getElementById('telegramBtn');
const favoritesBtn = document.getElementById('favoritesBtn');
const profileBtn = document.getElementById('profileBtn');

// Initialize the application
document.addEventListener('DOMContentLoaded', async function() {
    try {
        await renderCategories();
        await renderProducts();
        setupEventListeners();
        updateCartCount();
        loadFromLocalStorage();
    } catch (error) {
        console.error('Ошибка инициализации:', error);
        showNotification('Ошибка загрузки данных');
    }
});

// Load data from localStorage
function loadFromLocalStorage() {
    const savedCart = localStorage.getItem('rukami_cart');
    const savedFavorites = localStorage.getItem('rukami_favorites');

    if (savedCart) {
        cart = JSON.parse(savedCart);
        updateCartCount();
    }

    if (savedFavorites) {
        favorites = JSON.parse(savedFavorites);
    }
}

// Save data to localStorage
function saveToLocalStorage() {
    localStorage.setItem('rukami_cart', JSON.stringify(cart));
    localStorage.setItem('rukami_favorites', JSON.stringify(favorites));
}

// Navigation functions
function navigateToFavorites() {
    // Сохраняем текущее состояние
    saveToLocalStorage();

    // Переходим на страницу избранного
    window.location.href = '/favorites';
}

function navigateToProfile() {
    // Сохраняем текущее состояние
    saveToLocalStorage();

    // Переходим на страницу профиля
    window.location.href = '/profile';
}

function navigateToCart() {
    // Сохраняем текущее состояние
    saveToLocalStorage();

    // Переходим на страницу корзины
    window.location.href = '/cart';
}

// Получение категорий
async function fetchCategories() {
    const response = await fetch('/api/categories');
    if (!response.ok) throw new Error('Ошибка загрузки категорий');
    return await response.json();
}

// Получение товаров
async function fetchProducts(page = 1, category = null, search = '') {
    const params = new URLSearchParams({
        limit: productsPerPage,
        offset: (page - 1) * productsPerPage,
        ...(category && { category_slug: category }),
        ...(search && { search: search })
    });

    const response = await fetch(`/api/products?${params}`);
    if (!response.ok) throw new Error('Ошибка загрузки товаров');
    return await response.json();
}

// Render categories
async function renderCategories() {
    try {
        const { categories } = await fetchCategories();

        categoriesGrid.innerHTML = categories.map(category => `
            <div class="category-card fade-in" data-category="${category.slug}"
                 onclick="filterByCategory('${category.slug}')">
                <div class="category-icon">${getCategoryIcon(category.name)}</div>
                <div class="category-name">${category.name}</div>
                <div class="category-count">${category.products_count} товаров</div>
            </div>
        `).join('');

        // Добавляем "Все категории"
        const allCategoriesCard = document.createElement('div');
        allCategoriesCard.className = 'category-card fade-in';
        allCategoriesCard.innerHTML = `
            <div class="category-icon">🎯</div>
            <div class="category-name">Все категории</div>
            <div class="category-count">${totalProducts} товаров</div>
        `;
        allCategoriesCard.addEventListener('click', () => filterByCategory('all'));
        categoriesGrid.insertBefore(allCategoriesCard, categoriesGrid.firstChild);

    } catch (error) {
        console.error('Ошибка рендеринга категорий:', error);
        categoriesGrid.innerHTML = '<p class="error">Не удалось загрузить категории</p>';
    }
}

// Иконки для категорий
function getCategoryIcon(name) {
    const icons = {
        'Керамика': '🏺',
        'Украшения': '💎',
        'Текстиль': '🧶',
        'Дерево': '🪵',
        'Мыло': '🧼',
        'Свечи': '🕯️',
        'Игрушки': '🧸',
        'Картины': '🎨'
    };
    return icons[name] || '🎁';
}

// Render products
async function renderProducts() {
    try {
        // Показываем индикатор загрузки
        productsGrid.innerHTML = '<div class="loader">Загрузка товаров...</div>';

        const data = await fetchProducts(currentPage, currentCategory, currentSearch);
        totalProducts = data.total;
        const products = data.products;

        if (products.length === 0) {
            productsGrid.innerHTML = '<p class="no-results">Товары не найдены</p>';
            loadMoreBtn.style.display = 'none';
            return;
        }

        productsGrid.innerHTML = products.map(product => `
            <div class="product-card bounce-in">
                <div class="product-image" style="background-image: url('static/${product.image_url}')"></div>
                <div class="product-info">
                    <div class="product-price">${formatPrice(product.price)} ₽</div>
                    <div class="product-name">${product.name}</div>
                    <div class="product-description">${product.description}</div>
                    <div class="product-actions">
                        <button class="add-to-cart-btn" onclick="addToCart(${product.id}, '${product.name}', ${product.price}, '${product.image_url}')">
                            В корзину
                        </button>
                        <button class="favorite-btn ${favorites.includes(product.id) ? 'active' : ''}"
                                onclick="toggleFavorite(${product.id}, '${product.name}', ${product.price}, '${product.image_url}', '${product.description}')">
                            ♡
                        </button>
                    </div>
                </div>
            </div>
        `).join('');

        // Обновляем кнопку "Показать больше"
        const remainingProducts = totalProducts - (currentPage * productsPerPage);
        if (remainingProducts > 0) {
            loadMoreBtn.style.display = 'block';
            loadMoreBtn.textContent = `Показать еще (${remainingProducts})`;
        } else {
            loadMoreBtn.style.display = 'none';
        }

        // Обновляем счетчик "Все категории"
        const allCategoriesCount = document.querySelector('.category-card:first-child .category-count');
        if (allCategoriesCount) {
            allCategoriesCount.textContent = `${totalProducts} товаров`;
        }

    } catch (error) {
        console.error('Ошибка рендеринга товаров:', error);
        productsGrid.innerHTML = '<p class="error">Не удалось загрузить товары</p>';
    }
}

// Format price with spaces
function formatPrice(price) {
    return price.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

// Add to cart functionality
function addToCart(productId, productName, productPrice, productImage) {
    const existingItem = cart.find(item => item.id === productId);
    if (existingItem) {
        existingItem.quantity += 1;
    } else {
        cart.push({
            id: productId,
            name: productName,
            price: productPrice,
            image_url: productImage,
            quantity: 1
        });
    }
    updateCartCount();
    saveToLocalStorage();
    showNotification(`${productName} добавлен в корзину`);
}

// Toggle favorite
function toggleFavorite(productId, productName, productPrice, productImage, productDescription) {
    const index = favorites.findIndex(item => item.id === productId);
    let action;

    if (index > -1) {
        favorites.splice(index, 1);
        action = 'удален из избранного';
    } else {
        favorites.push({
            id: productId,
            name: productName,
            price: productPrice,
            image_url: productImage,
            description: productDescription
        });
        action = 'добавлен в избранное';
    }

    saveToLocalStorage();
    renderProducts();
    showNotification(`${productName} ${action}`);
}

// Update cart count
function updateCartCount() {
    const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
    cartCount.textContent = totalItems;
}

// Фильтрация по категории
async function filterByCategory(categorySlug) {
    try {
        currentCategory = categorySlug === 'all' ? null : categorySlug;
        currentPage = 1;
        currentSearch = '';
        searchInput.value = '';

        await renderProducts();

        document.querySelector('.products-section').scrollIntoView({
            behavior: 'smooth'
        });

    } catch (error) {
        console.error('Ошибка фильтрации:', error);
        showNotification('Ошибка фильтрации товаров');
    }
}

// Поиск товаров
async function performSearch() {
    try {
        const query = searchInput.value.trim();
        currentSearch = query;
        currentPage = 1;
        currentCategory = null;

        await renderProducts();

        if (query) {
            showNotification(`Найдено ${totalProducts} товаров по запросу "${query}"`);
        }

    } catch (error) {
        console.error('Ошибка поиска:', error);
        showNotification('Ошибка выполнения поиска');
    }
}

// Загрузка дополнительных товаров
async function loadMoreProducts() {
    try {
        currentPage++;
        const data = await fetchProducts(currentPage, currentCategory, currentSearch);
        const newProducts = data.products;

        if (newProducts.length === 0) {
            loadMoreBtn.style.display = 'none';
            return;
        }

        const newProductsHTML = newProducts.map(product => `
            <div class="product-card bounce-in">
                <div class="product-image" style="background-image: url('${product.image_url}')"></div>
                <div class="product-info">
                    <div class="product-price">${formatPrice(product.price)} ₽</div>
                    <div class="product-name">${product.name}</div>
                    <div class="product-description">${product.description}</div>
                    <div class="product-actions">
                        <button class="add-to-cart-btn" onclick="addToCart(${product.id}, '${product.name}', ${product.price}, '${product.image_url}')">
                            В корзину
                        </button>
                        <button class="favorite-btn ${favorites.some(fav => fav.id === product.id) ? 'active' : ''}"
                                onclick="toggleFavorite(${product.id}, '${product.name}', ${product.price}, '${product.image_url}', '${product.description}')">
                            ♡
                        </button>
                    </div>
                </div>
            </div>
        `).join('');

        productsGrid.innerHTML += newProductsHTML;

        // Обновляем кнопку
        const remainingProducts = totalProducts - (currentPage * productsPerPage);
        if (remainingProducts > 0) {
            loadMoreBtn.textContent = `Показать еще (${remainingProducts})`;
        } else {
            loadMoreBtn.style.display = 'none';
        }

    } catch (error) {
        console.error('Ошибка загрузки товаров:', error);
        showNotification('Ошибка загрузки дополнительных товаров');
    }
}

// Scroll to top
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// Show notification
function showNotification(message) {
    // Create notification element
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

    // Animate in
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 100);

    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// Setup event listeners
function setupEventListeners() {
    // Search functionality
    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            performSearch();
        }
    });

    // Load more button
    loadMoreBtn.addEventListener('click', loadMoreProducts);

    // Scroll to top button
    scrollTopBtn.addEventListener('click', scrollToTop);

    // Telegram bot button
    telegramBtn.addEventListener('click', function() {
        showNotification('Телеграм бот скоро будет доступен!');
    });

    // Navigation buttons with page transitions
    cartBtn.addEventListener('click', function() {
        if (cart.length === 0) {
            showNotification('Корзина пуста');
        } else {
            navigateToCart();
        }
    });

    // Profile button
    if (profileBtn) {
        profileBtn.addEventListener('click', function() {
            navigateToProfile();
        });
    }

    // Favorites button - главное изменение!
    if (favoritesBtn) {
        favoritesBtn.addEventListener('click', function() {
            if (favorites.length === 0) {
                showNotification('Список избранного пуст');
                // Все равно переходим на страницу избранного, даже если список пуст
                setTimeout(() => {
                    navigateToFavorites();
                }, 1000);
            } else {
                navigateToFavorites();
            }
        });
    }

    // Header scroll effect
    let lastScrollTop = 0;
    window.addEventListener('scroll', function() {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const header = document.querySelector('.header');

        if (scrollTop > lastScrollTop && scrollTop > 100) {
            // Scrolling down
            header.style.transform = 'translateY(-100%)';
        } else {
            // Scrolling up
            header.style.transform = 'translateY(0)';
        }

        lastScrollTop = scrollTop;

        // Show/hide scroll to top button
        if (scrollTop > 300) {
            scrollTopBtn.style.display = 'flex';
        } else {
            scrollTopBtn.style.display = 'none';
        }
    });
}

// Add some interactive features
document.addEventListener('mousemove', function(e) {
    const heroGradient = document.querySelector('.hero-gradient');
    if (heroGradient) {
        const x = (e.clientX / window.innerWidth) * 100;
        const y = (e.clientY / window.innerHeight) * 100;
        heroGradient.style.background = `radial-gradient(circle at ${x}% ${y}%, rgba(255, 107, 157, 0.3) 0%, rgba(255, 140, 200, 0.2) 50%, transparent 100%)`;
    }
});

// Add keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + K for search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        searchInput.focus();
    }

    // Escape to clear search
    if (e.key === 'Escape' && document.activeElement === searchInput) {
        searchInput.value = '';
        performSearch();
        searchInput.blur();
    }
});

// Add some fun easter eggs
let clickCount = 0;
document.querySelector('.logo h1').addEventListener('click', function() {
    clickCount++;
    if (clickCount === 5) {
        showNotification('🎉 Секретный режим активирован! 🎉');
        document.body.style.animation = 'rainbow 2s infinite';
        setTimeout(() => {
            document.body.style.animation = '';
            clickCount = 0;
        }, 2000);
    }
});

// Add CSS for rainbow animation
const style = document.createElement('style');
style.textContent = `
    @keyframes rainbow {
        0% { filter: hue-rotate(0deg); }
        100% { filter: hue-rotate(360deg); }
    }
`;
document.head.appendChild(style);