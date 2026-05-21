from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import hashlib
import json
import os
import pymysql
from urllib.parse import unquote, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'frontend'))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='/static')
app.secret_key = os.getenv('SECRET_KEY', 'food_recommend_secret_key_2024')
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE', '').lower() in ('1', 'true', 'yes')
)
CORS(app, supports_credentials=True)


def build_db_config():
    database_url = os.getenv('MYSQL_URL') or os.getenv('DATABASE_URL')
    if database_url:
        parsed = urlparse(database_url)
        return {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 3306,
            'user': unquote(parsed.username or 'root'),
            'password': unquote(parsed.password or ''),
            'database': (parsed.path or '/food_db').lstrip('/') or 'food_db',
            'charset': os.getenv('DB_CHARSET', 'utf8mb4')
        }

    return {
        'host': os.getenv('DB_HOST') or os.getenv('MYSQLHOST', 'localhost'),
        'port': int(os.getenv('DB_PORT') or os.getenv('MYSQLPORT', '3306')),
        'user': os.getenv('DB_USER') or os.getenv('MYSQLUSER', 'root'),
        'password': os.getenv('DB_PASSWORD') or os.getenv('MYSQLPASSWORD', '123456'),
        'database': os.getenv('DB_NAME') or os.getenv('MYSQLDATABASE', 'food_db'),
        'charset': os.getenv('DB_CHARSET', 'utf8mb4')
    }


DB_CONFIG = build_db_config()

XIASHA_ENRICHMENT_PATH = os.path.join(BASE_DIR, 'data', 'xiasha_enrichment.json')
XIASHA_SOURCE_URL_MAP = {}


def normalize_food_key(text):
    return ''.join(str(text or '').strip().split()).replace('（', '(').replace('）', ')')


def load_xiasha_source_url_map():
    global XIASHA_SOURCE_URL_MAP
    if XIASHA_SOURCE_URL_MAP:
        return XIASHA_SOURCE_URL_MAP

    mapping = {}
    try:
        with open(XIASHA_ENRICHMENT_PATH, 'r', encoding='utf-8') as file:
            records = json.load(file)
        for record in records:
            restaurant = str(record.get('restaurant') or '').strip()
            source_url = str(record.get('source_url') or '').strip()
            for item in record.get('items', []):
                item_name = str(item.get('name') or '').strip()
                if not item_name or not source_url:
                    continue
                full_name = f'{item_name}（{restaurant}）' if restaurant else item_name
                mapping[normalize_food_key(full_name)] = source_url
    except Exception:
        mapping = {}

    XIASHA_SOURCE_URL_MAP = mapping
    return XIASHA_SOURCE_URL_MAP


def resolve_source_url(food_name, stored_url=''):
    source_url = str(stored_url or '').strip()
    if source_url:
        return source_url
    return load_xiasha_source_url_map().get(normalize_food_key(food_name), '')


def get_db_connection():
    try:
        return pymysql.connect(**DB_CONFIG)
    except pymysql.err.OperationalError as error:
        if error.args and error.args[0] == 1049:
            bootstrap_config = DB_CONFIG.copy()
            database = bootstrap_config.pop('database')
            conn = pymysql.connect(**bootstrap_config)
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{database}` "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                conn.commit()
            finally:
                cursor.close()
                conn.close()
            return pymysql.connect(**DB_CONFIG)
        raise


def food_to_dict(food):
    return {
        'id': food[0],
        'food_name': food[1],
        'category': food[2],
        'price': float(food[3]),
        'review': food[4] or '',
        'rating': float(food[5]) if food[5] else 0,
        'original_taste': food[6] or '',
        'image_url': food[7] or ''
    }


def detail_food_to_dict(food):
    return {
        'id': food[0],
        'food_name': food[1],
        'category': food[2],
        'price': float(food[3]),
        'review': food[4] or '',
        'rating': float(food[5]) if food[5] else 0,
        'original_taste': food[6] or '',
        'taste_reform_scheme': food[7] or '',
        'image_url': food[8] or '',
        'source_url': food[9] if len(food) > 9 and food[9] else resolve_source_url(food[1])
    }


def split_keywords(value):
    return [item.strip() for item in (value or '').split(',') if item.strip()]


def expand_preference_keywords(value):
    keywords = []
    for item in split_keywords(value):
        keywords.append(item)
        if item in ('饮品', '饮料'):
            keywords.append('汤类')
        elif item == '汤类':
            keywords.extend(['汤', '粥'])
    seen = set()
    result = []
    for item in keywords:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def food_text_blob(food):
    return " ".join([
        str(food[1] or ''),
        str(food[2] or ''),
        str(food[4] or ''),
        str(food[6] or ''),
    ])


def should_avoid_food(food, avoid):
    text = food_text_blob(food)
    if not avoid:
        return False
    if '不吃辣' in avoid and '辣' in text:
        return True
    if '不吃甜' in avoid and '甜' in text:
        return True
    if '素食' in avoid and any(word in text for word in ('肉', '鸡', '鸭', '牛', '羊', '虾', '鱼', '排骨', '肠', '蹄')):
        return True
    if '忌油腻' in avoid and any(word in text for word in ('炸', '油', '酥', '肥')):
        return True
    return False


def score_food_for_recommendation(food, taste_keywords, food_type_keywords):
    score = 0
    text = food_text_blob(food)
    category = str(food[2] or '')
    price = float(food[3] or 0)
    rating = float(food[5] or 0)
    image_url = str(food[7] or '')

    if price > 0:
        score += 8
    if rating > 0:
        score += min(int(rating * 10), 50)
    if image_url:
        score += 5

    lower_text = text.lower()
    for kw in taste_keywords:
        if kw and kw in text:
            score += 24
        elif kw and kw.lower() in lower_text:
            score += 16

    for kw in food_type_keywords:
        if kw and kw in text:
            score += 20
        elif kw and kw in category:
            score += 24

    if any(word in text for word in ('早餐', '早饭')) and '早餐' in food_type_keywords:
        score += 8
    if any(word in text for word in ('饮料', '饮品', '汤')) and ('汤类' in food_type_keywords or '饮料' in food_type_keywords or '饮品' in food_type_keywords):
        score += 8

    return score


def apply_category_filter(sql, params, category):
    if not category:
        return sql, params

    category_map = {
        '早餐': ['早餐', '早饭', '小笼', '包子', '馄饨', '豆浆', '粥', '烧麦', '煎饼', '油条'],
        '中餐': ['中餐', '午餐', '快餐', '家常', '江浙', '东北', '西北', '米饭', '炒饭', '盖浇饭', '面', '粉', '小炒'],
        '晚餐': ['晚餐', '中餐', '火锅', '烤肉', '烧烤', '江浙', '东北', '家常', '小炒', '虾', '鸭', '牛肉', '羊肉'],
        '小吃': ['小吃', '点心', '包', '饺', '煎', '炸', '酥', '饼', '串', '凉皮', '肉夹馍'],
        '汤类': ['汤'],

    }
    keywords = category_map.get(category, [category])
    conditions = []
    for keyword in keywords:
        conditions.append("(category LIKE %s OR food_name LIKE %s OR original_taste LIKE %s)")
        params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
    sql += " AND (" + " OR ".join(conditions) + ")"
    return sql, params


def apply_avoid_filter(sql, avoid):
    if not avoid:
        return sql
    if '不吃辣' in avoid:
        sql += " AND food_name NOT LIKE '%辣%' AND original_taste NOT LIKE '%辣%' AND review NOT LIKE '%辣%'"
    if '不吃甜' in avoid:
        sql += " AND food_name NOT LIKE '%甜%' AND original_taste NOT LIKE '%甜%' AND review NOT LIKE '%甜%'"
    if '素食' in avoid:
        sql += " AND food_name NOT LIKE '%肉%' AND food_name NOT LIKE '%鸡%' AND food_name NOT LIKE '%鸭%' AND food_name NOT LIKE '%牛%' AND food_name NOT LIKE '%羊%' AND food_name NOT LIKE '%虾%' AND food_name NOT LIKE '%鱼%'"
    if '忌油腻' in avoid:
        sql += " AND food_name NOT LIKE '%炸%' AND food_name NOT LIKE '%油%' AND original_taste NOT LIKE '%油%'"
    return sql


@app.route('/')
@app.route('/index.html')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/login.html')
def login_page():
    return send_from_directory(FRONTEND_DIR, 'login.html')


@app.route('/register.html')
def register_page():
    return send_from_directory(FRONTEND_DIR, 'register.html')


@app.route('/detail.html')
def detail_page():
    return send_from_directory(FRONTEND_DIR, 'detail.html')


@app.route('/profile.html')
def profile_page():
    return send_from_directory(FRONTEND_DIR, 'profile.html')


@app.route('/assets/<path:filename>')
def serve_assets(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'assets'), filename)


@app.route('/api/health')
def health():
    return jsonify({'success': True, 'service': 'food-project'})


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    taste = data.get('taste', '')
    food_type = data.get('food_type', '')
    avoid = data.get('avoid', '')

    if not username or not password:
        return jsonify({'success': False, 'msg': '用户名和密码不能为空'})

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM user WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify({'success': False, 'msg': '用户名已存在'})

        encrypted_pwd = hashlib.md5(password.encode()).hexdigest()
        cursor.execute(
            "INSERT INTO user (username, password, taste, food_type, avoid) VALUES (%s, %s, %s, %s, %s)",
            (username, encrypted_pwd, taste, food_type, avoid)
        )
        conn.commit()
        return jsonify({'success': True, 'msg': '注册成功'})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'success': False, 'msg': '用户名和密码不能为空'})

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        encrypted_pwd = hashlib.md5(password.encode()).hexdigest()
        cursor.execute(
            "SELECT id, username, taste, food_type, avoid FROM user WHERE username = %s AND password = %s",
            (username, encrypted_pwd)
        )
        user = cursor.fetchone()
        if not user:
            return jsonify({'success': False, 'msg': '用户名或密码错误'})

        session['user_id'] = user[0]
        session['username'] = user[1]
        return jsonify({
            'success': True,
            'msg': '登录成功',
            'user': {
                'id': user[0],
                'username': user[1],
                'taste': user[2] or '',
                'food_type': user[3] or '',
                'avoid': user[4] or ''
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'msg': '已退出登录'})


@app.route('/api/user/preference', methods=['PUT'])
def update_preference():
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    taste = data.get('taste', '')
    food_type = data.get('food_type', '')
    avoid = data.get('avoid', '')

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE user SET taste = %s, food_type = %s, avoid = %s WHERE id = %s",
            (taste, food_type, avoid, user_id)
        )
        conn.commit()
        return jsonify({
            'success': True,
            'msg': '偏好设置已更新',
            'user': {
                'id': user_id,
                'taste': taste,
                'food_type': food_type,
                'avoid': avoid
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/api/user/<int:user_id>', methods=['GET'])
def get_user_profile(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, username, taste, food_type, avoid FROM user WHERE id = %s",
            (user_id,)
        )
        user = cursor.fetchone()
        if not user:
            return jsonify({'success': False, 'msg': '用户不存在'})
        return jsonify({
            'success': True,
            'user': {
                'id': user[0],
                'username': user[1],
                'taste': user[2] or '',
                'food_type': user[3] or '',
                'avoid': user[4] or ''
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/api/foods', methods=['GET'])
def get_foods():
    category = request.args.get('category', '')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')
    taste_filter = request.args.get('taste', '')
    search = request.args.get('search', '')
    offset = (page - 1) * page_size

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = """
            SELECT id, food_name, category, price, review, rating, original_taste, image_url
            FROM food
            WHERE 1=1
        """
        params = []

        sql, params = apply_category_filter(sql, params, category)
        if min_price:
            sql += " AND price >= %s"
            params.append(float(min_price))
        if max_price and max_price != '999':
            sql += " AND price <= %s"
            params.append(float(max_price))
        if taste_filter:
            sql += " AND (original_taste LIKE %s OR food_name LIKE %s OR review LIKE %s)"
            params.extend([f'%{taste_filter}%', f'%{taste_filter}%', f'%{taste_filter}%'])
        if search:
            sql += " AND (food_name LIKE %s OR original_taste LIKE %s OR review LIKE %s)"
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

        cursor.execute(f"SELECT COUNT(*) FROM ({sql}) AS t", params)
        total = cursor.fetchone()[0]

        sql += " ORDER BY CASE WHEN price > 0 THEN 0 ELSE 1 END, CASE WHEN image_url <> '' THEN 0 ELSE 1 END, rating DESC, id LIMIT %s OFFSET %s"
        cursor.execute(sql, params + [page_size, offset])
        foods = cursor.fetchall()

        return jsonify({
            'success': True,
            'data': [food_to_dict(food) for food in foods],
            'total': total,
            'page': page,
            'total_pages': (total + page_size - 1) // page_size if total > 0 else 1
        })
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e), 'data': []})
    finally:
        cursor.close()
        conn.close()


@app.route('/api/food/<int:food_id>', methods=['GET'])
def get_food_detail(food_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, food_name, category, price, review, rating, original_taste, taste_reform_scheme, image_url, source_url FROM food WHERE id = %s",
            (food_id,)
        )
        food = cursor.fetchone()
        if not food:
            return jsonify({'success': False, 'msg': '菜品不存在'})
        return jsonify({'success': True, 'data': detail_food_to_dict(food)})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/api/recommend', methods=['POST'])
def recommend():
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    taste = data.get('taste', '')
    food_type = data.get('food_type', '')
    avoid = data.get('avoid', '')
    limit = int(data.get('limit', 12))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if user_id and (not taste and not food_type and not avoid):
            cursor.execute(
                "SELECT taste, food_type, avoid FROM user WHERE id = %s",
                (user_id,)
            )
            user_pref = cursor.fetchone()
            if user_pref:
                taste = user_pref[0] or ''
                food_type = user_pref[1] or ''
                avoid = user_pref[2] or ''

        cursor.execute("""
            SELECT id, food_name, category, price, review, rating, original_taste, image_url
            FROM food
            ORDER BY CASE WHEN price > 0 THEN 0 ELSE 1 END,
                     CASE WHEN image_url <> '' THEN 0 ELSE 1 END,
                     rating DESC, id
        """)
        foods = cursor.fetchall()
        foods = [food for food in foods if not should_avoid_food(food, avoid)]

        taste_keywords = expand_preference_keywords(taste)
        food_type_keywords = expand_preference_keywords(food_type)
        foods.sort(
            key=lambda food: (
                score_food_for_recommendation(food, taste_keywords, food_type_keywords),
                float(food[5] or 0),
                float(food[3] or 0)
            ),
            reverse=True
        )
        foods = foods[:limit]
        return jsonify({'success': True, 'data': [food_to_dict(food) for food in foods]})
    except Exception as e:
        return jsonify({'success': False, 'data': [], 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/api/hot-foods', methods=['GET'])
def get_hot_foods():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, food_name, category, price, rating, image_url FROM food ORDER BY CASE WHEN price > 0 THEN 0 ELSE 1 END, CASE WHEN image_url <> '' THEN 0 ELSE 1 END, rating DESC LIMIT 10"
        )
        foods = cursor.fetchall()
        data = []
        for food in foods:
            data.append({
                'id': food[0],
                'food_name': food[1],
                'category': food[2],
                'price': float(food[3]),
                'rating': float(food[4]) if food[4] else 0,
                'image_url': food[5] or ''
            })
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'data': [], 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/api/user/<int:user_id>/history', methods=['POST'])
def add_history(user_id):
    data = request.get_json(silent=True) or {}
    food_id = data.get('food_id')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM user_history WHERE user_id = %s AND food_id = %s", (user_id, food_id))
        cursor.execute("INSERT INTO user_history (user_id, food_id) VALUES (%s, %s)", (user_id, food_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/api/user/<int:user_id>/history', methods=['GET'])
def get_history(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT f.id, f.food_name, f.category, f.price, f.rating, f.image_url
            FROM user_history uh
            JOIN food f ON uh.food_id = f.id
            WHERE uh.user_id = %s
            ORDER BY uh.view_time DESC
        """, (user_id,))
        rows = cursor.fetchall()
        data = []
        for row in rows:
            data.append({
                'id': row[0],
                'food_name': row[1],
                'category': row[2],
                'price': float(row[3]),
                'rating': float(row[4]) if row[4] else 0,
                'image_url': row[5] or ''
            })
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'data': [], 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/api/user/<int:user_id>/favorites', methods=['GET', 'POST', 'DELETE'])
def user_favorites(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'GET':
        try:
            cursor.execute("""
                SELECT f.id, f.food_name, f.category, f.price, f.rating, f.image_url
                FROM user_favorite uf
                JOIN food f ON uf.food_id = f.id
                WHERE uf.user_id = %s
                ORDER BY uf.created_at DESC
            """, (user_id,))
            favorites = cursor.fetchall()
            data = []
            for item in favorites:
                data.append({
                    'id': item[0],
                    'food_name': item[1],
                    'category': item[2],
                    'price': float(item[3]),
                    'rating': float(item[4]) if item[4] else 0,
                    'image_url': item[5] or ''
                })
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            return jsonify({'success': False, 'data': [], 'msg': str(e)})
        finally:
            cursor.close()
            conn.close()

    data = request.get_json(silent=True) or {}
    food_id = data.get('food_id')

    if request.method == 'POST':
        try:
            cursor.execute(
                "INSERT INTO user_favorite (user_id, food_id) VALUES (%s, %s)",
                (user_id, food_id)
            )
            conn.commit()
            return jsonify({'success': True, 'msg': '收藏成功'})
        except pymysql.err.IntegrityError:
            return jsonify({'success': False, 'msg': '已经收藏过了'})
        except Exception as e:
            return jsonify({'success': False, 'msg': str(e)})
        finally:
            cursor.close()
            conn.close()

    try:
        cursor.execute(
            "DELETE FROM user_favorite WHERE user_id = %s AND food_id = %s",
            (user_id, food_id)
        )
        conn.commit()
        return jsonify({'success': True, 'msg': '已取消收藏'})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/api/user/<int:user_id>/favorite/check/<int:food_id>', methods=['GET'])
def check_favorite(user_id, food_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id FROM user_favorite WHERE user_id = %s AND food_id = %s",
            (user_id, food_id)
        )
        exists = cursor.fetchone()
        return jsonify({'success': True, 'is_favorited': exists is not None})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()


@app.route('/api/reviews', methods=['GET', 'POST'])
def reviews():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'GET':
        food_id = request.args.get('food_id')
        try:
            cursor.execute("""
                SELECT r.id, r.user_id, u.username, r.food_id, r.rating, r.content, r.created_at
                FROM user_review r
                LEFT JOIN user u ON r.user_id = u.id
                WHERE r.food_id = %s
                ORDER BY r.created_at DESC
            """, (food_id,))
            rows = cursor.fetchall()
            data = []
            for row in rows:
                created_at = row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] else ''
                data.append({
                    'id': row[0],
                    'user_id': row[1],
                    'username': row[2] or '匿名用户',
                    'food_id': row[3],
                    'rating': row[4] or 5,
                    'content': row[5] or '',
                    'created_at': created_at
                })
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            return jsonify({'success': False, 'data': [], 'msg': str(e)})
        finally:
            cursor.close()
            conn.close()

    data = request.get_json(silent=True) or {}
    try:
        cursor.execute(
            "INSERT INTO user_review (user_id, food_id, rating, content) VALUES (%s, %s, %s, %s)",
            (data.get('user_id'), data.get('food_id'), data.get('rating', 5), data.get('content', ''))
        )
        conn.commit()
        return jsonify({'success': True, 'msg': '评论发布成功'})
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)})
    finally:
        cursor.close()
        conn.close()


def init_database():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS food (
            id INT PRIMARY KEY AUTO_INCREMENT,
            food_name VARCHAR(100) NOT NULL,
            category VARCHAR(50),
            price DECIMAL(10, 2) NOT NULL DEFAULT 0,
            review TEXT,
            rating DECIMAL(3, 1) DEFAULT 0,
            original_taste VARCHAR(200),
            taste_reform_scheme TEXT,
            image_url TEXT,
            source_url TEXT
        )
    """)

    try:
        cursor.execute("ALTER TABLE food MODIFY image_url TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE food ADD COLUMN source_url TEXT")
    except Exception:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user (
            id INT PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL,
            taste VARCHAR(200),
            food_type VARCHAR(200),
            avoid VARCHAR(200),
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_history (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            food_id INT NOT NULL,
            view_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_favorite (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            food_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_favorite (user_id, food_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_review (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            food_id INT NOT NULL,
            rating INT DEFAULT 5,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print('数据库初始化完成')


if __name__ == '__main__':
    init_database()
    print('服务器启动中：http://localhost:5000')
    app.run(host='0.0.0.0', port=5000, debug=True)
