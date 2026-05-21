function showMessage(msg, type) {
    type = type || 'success';
    var existingMsg = document.querySelector('.toast-message');
    if (existingMsg) existingMsg.remove();

    var toast = document.createElement('div');
    toast.className = 'toast-message ' + type;
    toast.textContent = msg;
    toast.style.cssText = 'position:fixed;top:80px;left:50%;transform:translateX(-50%);' +
        'background:' + (type === 'success' ? '#10B981' : '#EF4444') + ';' +
        'color:#fff;padding:12px 24px;border-radius:40px;font-size:14px;z-index:10000;' +
        'box-shadow:0 4px 12px rgba(0,0,0,0.15);';

    document.body.appendChild(toast);
    setTimeout(function () { toast.remove(); }, 2200);
}

function formatPrice(price) {
    var value = Number(price);
    if (!isFinite(value) || value <= 0) return '';
    return '¥' + value.toFixed(1);
}

function isSoupFood(food) {
    food = food || {};
    return String(food.category || '').trim() === '汤类';
}

function getMissingRatingText(food) {
    return isSoupFood(food) ? '暂无评分' : 'N/A';
}

function getMissingReviewText(food) {
    return isSoupFood(food) ? '暂无评价' : '';
}

function getFoodRatingText(food, digits) {
    food = food || {};
    var value = Number(food.rating) || 0;
    if (value <= 0) return getMissingRatingText(food);
    return digits === undefined ? String(food.rating) : value.toFixed(digits);
}

function renderStars(rating, missingText) {
    var value = Number(rating) || 0;
    if (value <= 0) return '<span class="rating-value">' + (missingText || 'N/A') + '</span>';
    var fullStars = Math.max(0, Math.min(5, Math.round(value)));
    var stars = '\u2605'.repeat(fullStars) + '\u2606'.repeat(5 - fullStars);
    return stars + ' <span class="rating-value">' + value.toFixed(1) + '</span>';
}

function normalizeImageUrl(url, fallback) {
    if (!url) return fallback;
    var cleaned = String(url).trim();
    if (cleaned.indexOf('//') === 0) return 'https:' + cleaned;
    return cleaned;
}

var renderedFoodImages = {};

function resetFoodImageCache() {
    renderedFoodImages = {};
}

function hashText(text) {
    var value = String(text || '');
    var hash = 0;
    for (var i = 0; i < value.length; i++) {
        hash = ((hash << 5) - hash) + value.charCodeAt(i);
        hash |= 0;
    }
    return Math.abs(hash);
}

function buildFoodImageText(food) {
    food = food || {};
    return String(food.food_name || '') + ' ' + String(food.category || '') + ' ' + String(food.original_taste || '') + ' ' + String(food.review || '');
}

function getFoodImageTheme(food) {
    var text = buildFoodImageText(food);
    if (/(汤|粥|羹|胡辣汤|酸辣汤|soup|broth|stew)/i.test(text)) return 'soup';
    if (/(虾|鱼|蟹|贝|海鲜|龙虾|虾锅|虾丸|fish|shrimp|crab|seafood)/i.test(text)) return 'seafood';
    if (/(牛肉|羊肉|猪肉|五花肉|瘦肉|卤肉|回锅肉|锅包肉|烤肉|烧烤|鸡心|鸡翅|鸡肉|鸭|烤鸭|猪皮|培根|掌中宝|排骨|肉夹馍|beef|lamb|pork|chicken|duck|meat|steak|roast)/i.test(text)) return 'meat';
    if (/(小笼|包子|煎包|煎饺|馄饨|饺子|烧麦|烧饼|煎饼|油条|麻球|早餐|豆浆|鸡蛋|水煮蛋|面包|bread|toast|sandwich|breakfast|pancake|waffle)/i.test(text)) return 'breakfast';
    if (/(面条|拌面|手工面|拉面|米粉|粉丝|米线|炒饭|米饭|盖浇饭|凉皮|面筋|noodle|rice|pasta|bowl)/i.test(text)) return 'staple';
    if (/(素菜|豆腐|蘑菇|金针菇|韭菜|茄子|黄瓜|土豆|四季豆|藕|生菜|沙拉|vegetable|salad|tofu|mushroom)/i.test(text)) return 'vegetable';
    if (/(甜品|蛋糕|冰激凌|巧克力|布丁|糕|dessert|cake|ice cream|cookie|pudding)/i.test(text)) return 'dessert';
    return 'general';
}

function getImagePoolByTheme(theme) {
    var pools = {
        soup: [
            'https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1476718406336-bb5a9690ee2a?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1547592180-7d93b7f5f8f0?auto=format&fit=crop&w=900&q=80'
        ],
        breakfast: [
            'https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1482049016688-2d3e1b311543?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1509722747041-616f39b57569?auto=format&fit=crop&w=900&q=80'
        ],
        staple: [
            'https://images.unsplash.com/photo-1512058564366-18510be2db19?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=900&q=80'
        ],
        seafood: [
            'https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1529692236671-f1f6cf9683ba?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1546964124-0cce460f38ef?auto=format&fit=crop&w=900&q=80'
        ],
        vegetable: [
            'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1529042410759-befb1204b468?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1482049016688-2d3e1b311543?auto=format&fit=crop&w=900&q=80'
        ],
        meat: [
            'https://images.unsplash.com/photo-1529692236671-f1f6cf9683ba?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1546833999-b9f581a1996d?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1558030006-450675393462?auto=format&fit=crop&w=900&q=80'
        ],
        dessert: [
            'https://images.unsplash.com/photo-1499636136210-6f4ee915583e?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1488477181946-6428a0291777?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1464349095431-e9a21285b5f3?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=900&q=80'
        ],
        general: [
            'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1559847844-5315695dadae?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=900&q=80'
        ]
    };
    return pools[theme] || pools.general;
}

function getFoodDisplayImage(food) {
    food = food || {};
    var imageUrl = normalizeImageUrl(food.image_url, '');
    if (imageUrl && !renderedFoodImages[imageUrl]) {
        renderedFoodImages[imageUrl] = 1;
        return imageUrl;
    }

    if (imageUrl) renderedFoodImages[imageUrl] = (renderedFoodImages[imageUrl] || 0) + 1;
    var theme = getFoodImageTheme(food);
    var pool = getImagePoolByTheme(theme);
    var signature = buildFoodImageText(food) + '|' + String(food.id || '') + '|' + String(renderedFoodImages[imageUrl] || 0);
    return pool[hashText(signature) % pool.length];
}

function getFoodFallbackImage(food) {
    var theme = getFoodImageTheme(food);
    var pool = getImagePoolByTheme(theme);
    return pool[0];
}

function translateMenuName(text) {
    return String(text || '').trim() || 'Campus Food';
}

function translateMenuText(text) {
    return String(text || '').trim();
}

function getDisplayFoodName(food) {
    return translateMenuName(food && food.food_name);
}

function updateNavbarUser() {
    var user = getCurrentUser();
    var navRight = document.querySelector('.nav-right');
    if (!navRight) return;

    if (user) {
        navRight.innerHTML =
            '<div class="user-info">' +
            '<span onclick="window.location.href=\'profile.html\'">' + user.username + '</span>' +
            '<button class="btn-logout" onclick="handleLogout()">Exit</button>' +
            '</div>';
    } else {
        navRight.innerHTML =
            '<button class="btn-outline" onclick="window.location.href=\'login.html\'">Login</button>' +
            '<button class="btn-primary" onclick="window.location.href=\'register.html\'">Register</button>';
    }
}

async function handleLogout() {
    await logout();
    showMessage('Logged out');
    setTimeout(function () {
        window.location.href = 'index.html';
    }, 800);
}

function createFoodCard(food) {
    var imageUrl = getFoodDisplayImage(food);
    var displayName = getDisplayFoodName(food);
    var displayTaste = translateMenuText(food.original_taste || 'No taste description');
    var displayReview = translateMenuText(food.review || getMissingReviewText(food));
    var hasDetail = food.id !== undefined && food.id !== null && food.id !== '';
    var html = '';
    html += '<div class="food-card"' + (hasDetail ? ' onclick="window.location.href=\'detail.html?id=' + food.id + '\'"' : '') + '>';
    html += '<img class="food-image" src="' + imageUrl + '" alt="' + displayName + '" onerror="this.src=\'' + getFoodFallbackImage(food) + '\'">';
    var priceText = formatPrice(food.price);
    html += '<div class="food-info">';
    html += '<div class="food-name"><span>' + displayName + '</span>' + (priceText ? '<span class="food-price">' + priceText + '</span>' : '') + '</div>';
    html += '<div class="food-taste">' + (displayTaste || 'No taste description') + '</div>';
    html += '<div class="food-rating">' + renderStars(food.rating, getMissingRatingText(food)) + '</div>';
    html += '<div class="food-review">' + displayReview.substring(0, 50) + (displayReview.length > 50 ? '...' : '') + '</div>';
    html += '</div></div>';
    return html;
}

document.addEventListener('DOMContentLoaded', updateNavbarUser);

window.showMessage = showMessage;
window.formatPrice = formatPrice;
window.isSoupFood = isSoupFood;
window.getMissingRatingText = getMissingRatingText;
window.getMissingReviewText = getMissingReviewText;
window.getFoodRatingText = getFoodRatingText;
window.renderStars = renderStars;
window.normalizeImageUrl = normalizeImageUrl;
window.resetFoodImageCache = resetFoodImageCache;
window.getFoodDisplayImage = getFoodDisplayImage;
window.getFoodFallbackImage = getFoodFallbackImage;
window.translateMenuName = translateMenuName;
window.translateMenuText = translateMenuText;
window.getDisplayFoodName = getDisplayFoodName;
window.updateNavbarUser = updateNavbarUser;
window.handleLogout = handleLogout;
window.createFoodCard = createFoodCard;
