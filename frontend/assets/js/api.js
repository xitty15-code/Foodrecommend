const API_BASE_URL = '/api';

let currentUser = null;

async function request(url, options = {}) {
    const config = {
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        ...options
    };

    try {
        const response = await fetch(`${API_BASE_URL}${url}`, config);
        return await response.json();
    } catch (error) {
        console.error('请求失败:', error);
        return { success: false, msg: '网络服务连接错误' };
    }
}

function buildQuery(params) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') query.set(key, value);
    });
    const text = query.toString();
    return text ? `?${text}` : '';
}

async function register(username, password, taste, foodType, avoid) {
    return request('/register', {
        method: 'POST',
        body: JSON.stringify({ username, password, taste, food_type: foodType, avoid })
    });
}

async function login(username, password) {
    const result = await request('/login', {
        method: 'POST',
        body: JSON.stringify({ username, password })
    });
    if (result.success) {
        currentUser = result.user;
        localStorage.setItem('currentUser', JSON.stringify(currentUser));
    }
    return result;
}

async function logout() {
    const result = await request('/logout', { method: 'POST' });
    currentUser = null;
    localStorage.removeItem('currentUser');
    return result;
}

function getUser() {
    if (currentUser) return currentUser;
    const stored = localStorage.getItem('currentUser');
    if (!stored) return null;
    try {
        currentUser = JSON.parse(stored);
        return currentUser;
    } catch (error) {
        localStorage.removeItem('currentUser');
        return null;
    }
}

async function getUserProfile(userId) {
    return request(`/user/${userId}`);
}

async function updatePreference(userId, taste, foodType, avoid) {
    return request('/user/preference', {
        method: 'PUT',
        body: JSON.stringify({ user_id: userId, taste, food_type: foodType, avoid })
    });
}

async function getFoods(category = '', search = '', page = 1, pageSize = 12, taste = '') {
    return request(`/foods${buildQuery({ category, search, page, page_size: pageSize, taste })}`);
}

async function getFoodDetail(foodId) {
    return request(`/food/${foodId}`);
}

async function getRecommendations(userId = null, limit = 12) {
    const user = getUser();
    const activeUserId = userId || (user && user.id) || null;
    let taste = user ? user.taste || '' : '';
    let foodType = user ? user.food_type || '' : '';
    let avoid = user ? user.avoid || '' : '';

    if (activeUserId) {
        try {
            const profile = await request(`/user/${activeUserId}`);
            if (profile.success && profile.user) {
                taste = profile.user.taste || taste;
                foodType = profile.user.food_type || foodType;
                avoid = profile.user.avoid || avoid;
            }
        } catch (error) {
            /* keep local fallback */
        }
    }

    return request('/recommend', {
        method: 'POST',
        body: JSON.stringify({
            user_id: activeUserId,
            taste,
            food_type: foodType,
            avoid,
            limit
        })
    });
}

async function getHotFoods() {
    return request('/hot-foods');
}

async function addHistory(userId, foodId) {
    return request(`/user/${userId}/history`, {
        method: 'POST',
        body: JSON.stringify({ food_id: foodId })
    });
}

async function getHistory(userId) {
    return request(`/user/${userId}/history`);
}

async function addFavorite(userId, foodId) {
    return request(`/user/${userId}/favorites`, {
        method: 'POST',
        body: JSON.stringify({ food_id: foodId })
    });
}

async function removeFavorite(userId, foodId) {
    return request(`/user/${userId}/favorites`, {
        method: 'DELETE',
        body: JSON.stringify({ food_id: foodId })
    });
}

async function getFavorites(userId) {
    return request(`/user/${userId}/favorites`);
}

async function checkFavorite(userId, foodId) {
    return request(`/user/${userId}/favorite/check/${foodId}`);
}

async function getReviews(foodId) {
    return request(`/reviews?food_id=${encodeURIComponent(foodId)}`);
}

async function addReview(userId, foodId, rating, content) {
    return request('/reviews', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, food_id: foodId, rating, content })
    });
}

async function testAPIConnection() {
    const result = await getFoods('', '', 1, 1);
    return Boolean(result && result.success);
}

async function getFood(foodId) {
    const result = await getFoodDetail(foodId);
    return result.success ? result.data : null;
}

async function getComments(foodId) {
    const result = await getReviews(foodId);
    return result.success ? result.data : [];
}

async function postComment(payload) {
    const user = getUser();
    return addReview(
        payload.user_id || (user && user.id),
        payload.food_id,
        payload.rating || 5,
        payload.content || ''
    );
}

Object.assign(window, {
    API_BASE_URL,
    request,
    register,
    login,
    logout,
    getUser,
    getCurrentUser: getUser,
    getUserProfile,
    updatePreference,
    getFoods,
    getFoodDetail,
    getFood,
    getRecommendations,
    getHotFoods,
    addHistory,
    getHistory,
    addFavorite,
    removeFavorite,
    getFavorites,
    checkFavorite,
    getReviews,
    addReview,
    postComment,
    getComments,
    testAPIConnection
});
