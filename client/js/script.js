// Mock data for categories
const categories = [
    {
        id: 1,
        name: 'Керамика',
        count: 124,
        icon: '🏺'
    },
    {
        id: 2,
        name: 'Украшения',
        count: 89,
        icon: '💎'
    },
    {
        id: 3,
        name: 'Текстиль',
        count: 156,
        icon: '🧶'
    },
    {
        id: 4,
        name: 'Дерево',
        count: 73,
        icon: '🪵'
    },
    {
        id: 5,
        name: 'Мыло',
        count: 45,
        icon: '🧼'
    },
    {
        id: 6,
        name: 'Свечи',
        count: 62,
        icon: '🕯️'
    },
    {
        id: 7,
        name: 'Игрушки',
        count: 38,
        icon: '🧸'
    },
    {
        id: 8,
        name: 'Картины',
        count: 91,
        icon: '🎨'
    }
];

// Mock data for products
const products = [
    {
        id: 1,
        name: 'Керамическая ваза "Закат"',
        description: 'Уникальная ваза ручной работы с градиентом заката. Идеально подходит для живых цветов.',
        price: 3500,
        image: 'ceramic-vase.jpg',
        category: 'Керамика',
        author: 'Мария Петрова',
        inStock: true
    },
    {
        id: 2,
        name: 'Серебряное кольцо с аметистом',
        description: 'Элегантное кольцо из серебра 925 пробы с натуральным аметистом.',
        price: 4200,
        image: 'silver-ring.jpg',
        category: 'Украшения',
        author: 'Анна Смирнова',
        inStock: true
    },
    {
        id: 3,
        name: 'Вязаный плед "Облака"',
        description: 'Мягкий плед из натуральной шерсти, связанный вручную. Размер 150x200 см.',
        price: 5800,
        image: 'knitted-blanket.jpg',
        category: 'Текстиль',
        author: 'Елена Козлова',
        inStock: true
    },
    {
        id: 4,
        name: 'Деревянная шкатулка',
        description: 'Резная шкатулка из массива дуба с инкрустацией. Ручная работа.',
        price: 2900,
        image: 'wooden-box.jpg',
        category: 'Дерево',
        author: 'Игорь Волков',
        inStock: true
    },
    {
        id: 5,
        name: 'Натуральное мыло "Лаванда"',
        description: 'Мыло ручной варки с эфирным маслом лаванды и сушеными цветами.',
        price: 450,
        image: 'lavender-soap.jpg',
        category: 'Мыло',
        author: 'Ольга Новикова',
        inStock: true
    },
    {
        id: 6,
        name: 'Соевая свеча "Уют"',
        description: 'Ароматическая свеча из соевого воска с запахом ванили и корицы.',
        price: 890,
        image: 'soy-candle.jpg',
        category: 'Свечи',
        author: 'Дарья Белова',
        inStock: true
    },
    {
        id: 7,
        name: 'Мягкая игрушка "Мишка Тедди"',
        description: 'Классический мишка Тедди ручной работы из натурального плюша.',
        price: 1850,
        image: 'teddy-bear.jpg',
        category: 'Игрушки',
        author: 'Светлана Орлова',
        inStock: true
    },
    {
        id: 8,
        name: 'Акварель "Весенний сад"',
        description: 'Оригинальная акварельная картина с изображением цветущего сада.',
        price: 7500,
        image: 'watercolor-garden.jpg',
        category: 'Картины',
        author: 'Александр Васильев',
        inStock: true
    },
    {
        id: 9,
        name: 'Керамическая тарелка',
        description: 'Декоративная тарелка с ручной росписью в этническом стиле.',
        price: 1200,
        image: 'ceramic-plate.jpg',
        category: 'Керамика',
        author: 'Мария Петрова',
        inStock: true
    }
];

// Application state
let cart = [];
let favorites = [];
let displayedProducts = 6;
let filteredProducts = [...products];

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

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    renderCategories();
    renderProducts();
    setupEventListeners();
    updateCartCount();
});

// Render categories
function renderCategories() {
    categoriesGrid.innerHTML = categories.map(category => `
        <div class="category-card fade-in" data-category="${category.name}" onclick="filterByCategory('${category.name}')">
            <div class="category-icon">${category.icon}</div>
            <div class="category-name">${category.name}</div>
            <div class="category-count">${category.count} товаров</div>
        </div>
    `).join('');
}

// Render products
function renderProducts() {
    const productsToShow = filteredProducts.slice(0, displayedProducts);

    productsGrid.innerHTML = productsToShow.map(product => `
        <div class="product-card bounce-in">
            <div class="product-image"></div>
            <div class="product-info">
                <div class="product-price">${formatPrice(product.price)} ₽</div>
                <div class="product-name">${product.name}</div>
                <div class="product-description">${product.description}</div>
                <div class="product-actions">
                    <button class="add-to-cart-btn" onclick="addToCart(${product.id})">
                        В корзину
                    </button>
                    <button class="favorite-btn ${favorites.includes(product.id) ? 'active' : ''}"
                            onclick="toggleFavorite(${product.id})">
                        ♡
                    </button>
                </div>
            </div>
        </div>
    `).join('');

    // Update load more button visibility
    if (displayedProducts >= filteredProducts.length) {
        loadMoreBtn.style.display = 'none';
    } else {
        loadMoreBtn.style.display = 'block';
    }
}

// Format price with spaces
function formatPrice(price) {
    return price.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

// Add to cart functionality
function addToCart(productId) {
    const product = products.find(p => p.id === productId);
    if (product) {
        const existingItem = cart.find(item => item.id === productId);
        if (existingItem) {
            existingItem.quantity += 1;
        } else {
            cart.push({ ...product, quantity: 1 });
        }
        updateCartCount();
        showNotification(`${product.name} добавлен в корзину`);
    }
}

// Toggle favorite
function toggleFavorite(productId) {
    const index = favorites.indexOf(productId);
    if (index > -1) {
        favorites.splice(index, 1);
    } else {
        favorites.push(productId);
    }
    renderProducts();

    const product = products.find(p => p.id === productId);
    const action = favorites.includes(productId) ? 'добавлен в избранное' : 'удален из избранного';
    showNotification(`${product.name} ${action}`);
}

// Update cart count
function updateCartCount() {
    const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
    cartCount.textContent = totalItems;
}

// Filter by category
function filterByCategory(categoryName) {
    if (categoryName === 'Все') {
        filteredProducts = [...products];
    } else {
        filteredProducts = products.filter(product => product.category === categoryName);
    }
    displayedProducts = 6;
    renderProducts();

    // Scroll to products section
    document.querySelector('.products-section').scrollIntoView({
        behavior: 'smooth'
    });
}

// Search functionality
function performSearch() {
    const query = searchInput.value.toLowerCase().trim();

    if (query === '') {
        filteredProducts = [...products];
    } else {
        filteredProducts = products.filter(product =>
            product.name.toLowerCase().includes(query) ||
            product.description.toLowerCase().includes(query) ||
            product.category.toLowerCase().includes(query) ||
            product.author.toLowerCase().includes(query)
        );
    }

    displayedProducts = 6;
    renderProducts();

    if (query !== '') {
        showNotification(`Найдено ${filteredProducts.length} товаров по запросу "${query}"`);
    }
}

// Load more products
function loadMoreProducts() {
    displayedProducts += 6;
    renderProducts();
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

    // Cart button
    cartBtn.addEventListener('click', function() {
        if (cart.length === 0) {
            showNotification('Корзина пуста');
        } else {
            showNotification(`В корзине ${cart.length} товаров`);
        }
    });

    // Profile and favorites buttons
    document.getElementById('profileBtn').addEventListener('click', function() {
        showNotification('Личный кабинет в разработке');
    });

    document.getElementById('favoritesBtn').addEventListener('click', function() {
        if (favorites.length === 0) {
            showNotification('Список избранного пуст');
        } else {
            showNotification(`В избранном ${favorites.length} товаров`);
        }
    });

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

    // Add "All categories" option
    const allCategoriesCard = document.createElement('div');
    allCategoriesCard.className = 'category-card fade-in';
    allCategoriesCard.innerHTML = `
        <div class="category-icon">🎯</div>
        <div class="category-name">Все категории</div>
        <div class="category-count">${products.length} товаров</div>
    `;
    allCategoriesCard.addEventListener('click', () => filterByCategory('Все'));
    categoriesGrid.insertBefore(allCategoriesCard, categoriesGrid.firstChild);
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