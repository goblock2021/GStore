# By GoBlock2021
import copy
import os
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort, send_from_directory, \
    current_app
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from flask_caching import Cache
from flask_wtf.file import FileField
from sqlalchemy import and_, case, event
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from wtforms import StringField, FloatField, BooleanField, SubmitField
from wtforms.fields.choices import SelectField
from wtforms.fields.datetime import DateField
from wtforms.validators import DataRequired, Optional

app = Flask(__name__)

# 配置上传文件夹
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///web_data.db'
app.config['CACHE_TYPE'] = 'simple'
app.config['CACHE_DEFAULT_TIMEOUT'] = 3600

db = SQLAlchemy(app)
cache = Cache(app)

scheduler = BackgroundScheduler()
scheduler.start()

migrate = Migrate(app, db)

with app.app_context():
    Session = sessionmaker(bind=db.engine)

app.config['SECRET_KEY'] = 'ebboPjKwol5krcOdOL7WakhoIIBShlv4'

login_manager = LoginManager(app)
login_manager.login_view = 'login'


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def delete_file(filepath):
    print(filepath)
    if filepath and os.path.exists(filepath):
        os.remove(filepath)


# 数据库模型
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    cart = db.relationship('Cart', backref='user', uselist=False)


class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(255), nullable=True, default='Game')
    release_date = db.Column(db.Date, nullable=True)
    price = db.Column(db.Float, nullable=False)
    is_discounted = db.Column(db.Boolean, default=False)
    discount_price = db.Column(db.Float, nullable=True)
    developer = db.Column(db.String(256), nullable=True)
    publisher = db.Column(db.String(256), nullable=True)
    tags = db.Column(db.String(255), nullable=True)
    cover_image = db.Column(db.String(255), nullable=True)
    screenshots = db.relationship('GameScreenshots', backref='game', lazy=True)
    deleted = db.Column(db.Boolean, default=False)


class GameScreenshots(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)


class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('CartItem', backref='cart', cascade='all, delete-orphan')


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('cart.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    game = db.relationship('Game')


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # 订单状态：Pending, Paid, Expired
    status = db.Column(db.String(50), default='Pending')
    total_price = db.Column(db.Float, nullable=False)
    user = db.relationship('User', backref='orders')
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Float, nullable=False)
    game = db.relationship('Game')


# 表单
class GameForm(FlaskForm):
    name = StringField('名称', validators=[DataRequired()])
    type = SelectField('类型', choices=[('Game', '游戏'), ('DLC', 'DLC')], validators=[DataRequired()])
    release_date = DateField('发行日期')
    price = FloatField('价格', validators=[DataRequired()])
    is_discounted = BooleanField('打折')
    discount_price = FloatField('折后价', validators=[Optional()])
    developer = StringField('开发商')
    publisher = StringField('发行商')
    tags = StringField('标签')
    cover_image = FileField('封面图片')
    screenshots = FileField('截图', render_kw={'multiple': True})
    submit = SubmitField('添加游戏')


# 使用 Flask-Caching 缓存获取所有标签的函数
@cache.cached(timeout=3600, key_prefix='all_tags')
def get_all_tags():
    print("Getting all tags...")
    games = Game.query.all()
    all_tags = set()
    for game in games:
        if game.tags:
            tags = game.tags.split(' ')
            all_tags.update(tags)
    return sorted(list(all_tags))


# 使用 SQLAlchemy 事件监听器在游戏更新后清除缓存
@event.listens_for(Game, 'after_update')
def after_game_update(mapper, connection, target):
    print('Game updated, clearing tag cache...')
    # 清除缓存
    cache.delete('all_tags')


# 自定义未授权处理函数
@login_manager.unauthorized_handler
def unauthorized_callback():
    flash('请先登录以访问此页面。')  # 自定义消息
    return redirect(url_for('login', next=request.url))


# 加载用户的回调函数
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# 设置静态文件路由
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# =======================
#       用户登录模块
# =======================


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        existing_user = User.query.filter_by(username=username).first()
        # 检查用户名是否已存在
        if not existing_user:
            # 将密码哈希后保存到数据库中
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()

            # 创建购物车并关联到用户
            new_cart = Cart(user_id=new_user.id)
            db.session.add(new_cart)
            db.session.commit()

            return redirect(
                url_for('redirect_with_message') + '?url=/login&message=注册成功，即将跳转至登录页面&title=注册成功')
        else:
            return redirect(
                url_for('redirect_with_message') + '?url=/register&message=注册失败，用户名不能重复&title=注册失败')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    next_page = request.args.get('next', default="/")
    print(next_page)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)

            return redirect(next_page)
        else:
            flash('用户名或密码错误', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# =======================
#       后台管理模块
# =======================

@app.route('/admin', methods=['GET'])
@login_required
def admin():
    # 确保只有管理员可以访问游戏管理页面
    if not current_user.is_admin:
        flash('您没有权限访问此页面', 'error')
        return redirect(url_for('index'))
    # 获取所有游戏
    games = Game.query.all()
    users = User.query.all()
    return render_template('admin/admin.html', games=games, users=users)


@app.route('/admin/games', methods=['GET'])
@login_required
def admin_games():
    # TODO: 需要移除
    # 确保只有管理员可以访问游戏管理页面
    if not current_user.is_admin:
        flash('您没有权限访问此页面', 'error')
        return redirect(url_for('index'))
    # 获取所有游戏
    games = Game.query.all()
    return render_template('admin/old/admin_games.html', games=games)


@app.route('/admin/games/<int:game_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_game(game_id):
    # 确保只有管理员可以编辑游戏
    if not current_user.is_admin:
        flash('您没有权限访问此页面', 'error')
        return redirect(url_for('index'))

    game = Game.query.get_or_404(game_id)
    form = GameForm(obj=game)

    if form.validate_on_submit():
        try:
            # 更新游戏信息
            game.name = form.name.data
            game.release_date = form.release_date.data
            game.price = form.price.data
            game.is_discounted = form.is_discounted.data
            game.discount_price = form.discount_price.data
            game.developer = form.developer.data
            game.publisher = form.publisher.data
            game.tags = form.tags.data

            # 处理封面图片
            if form.cover_image.data:
                cover_image_file = form.cover_image.data
                if allowed_file(cover_image_file.filename):
                    # 删除旧的封面图片（如果有）
                    if game.cover_image:
                        old_cover_image_path = game.cover_image
                        print(old_cover_image_path)
                        if os.path.exists(old_cover_image_path):
                            os.remove(old_cover_image_path)

                    filename = secure_filename(cover_image_file.filename)
                    cover_image_path = os.path.join(app.config['UPLOAD_FOLDER'], (str(game.id) + '_cover_' + filename))
                    cover_image_file.save(cover_image_path)

                    # 更新封面图片路径
                    game.cover_image = cover_image_path
                else:
                    raise ValueError("Invalid cover image file type")

            # 处理新的截图
            if form.screenshots.data:
                for file in request.files.getlist('screenshots'):
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        screenshot_path = os.path.join(app.config['UPLOAD_FOLDER'],
                                                       (str(game.id) + '_screenshot_' + filename))
                        file.save(screenshot_path)
                        screenshot = GameScreenshots(game_id=game.id, image_path=screenshot_path)
                        db.session.add(screenshot)
                    else:
                        raise ValueError("Invalid screenshot file type")

            db.session.commit()
            flash('游戏信息已成功更新!')
            return redirect(url_for('admin'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新游戏信息失败: {str(e)}')
            return redirect(url_for('edit_game', game_id=game_id))

    return render_template('admin/edit_game.html', form=form, game=game)


@app.route('/admin/games/<int:game_id>/delete', methods=['POST'])
@login_required
def delete_game(game_id):
    # 确保只有管理员可以添加新游戏
    if not current_user.is_admin:
        flash('您没有权限访问此页面', 'error')
        return redirect(url_for('index'))
    game = Game.query.get_or_404(game_id)
    db.session.delete(game)
    db.session.commit()
    flash(f'游戏 ID:{game_id} 已被删除', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/games/new', methods=['GET', 'POST'])
@login_required
def add_game():
    # 确保只有管理员可以添加新游戏
    if not current_user.is_admin:
        flash('您没有权限访问此页面', 'error')
        return redirect(url_for('index'))
    form = GameForm()
    if form.validate_on_submit():
        try:
            # 开始一个新的事务
            with db.session.begin_nested():
                # 创建新的游戏对象
                game = Game(
                    name=form.name.data,
                    type=form.type.data,
                    release_date=form.release_date.data,
                    price=form.price.data,
                    is_discounted=form.is_discounted.data,
                    discount_price=form.discount_price.data,
                    developer=form.developer.data,
                    publisher=form.publisher.data,
                    tags=form.tags.data
                )
                db.session.add(game)
                db.session.flush()  # 确保游戏对象的ID被生成

                # 处理封面图片
                if form.cover_image.data:
                    cover_image_file = form.cover_image.data
                    if allowed_file(cover_image_file.filename):
                        filename = secure_filename(cover_image_file.filename)  # 获取原有的文件名
                        cover_image_path = os.path.join(app.config['UPLOAD_FOLDER'],
                                                        (str(game.id) + '_cover_' + filename))
                        cover_image_file.save(cover_image_path)
                        game.cover_image = cover_image_path
                    else:
                        raise ValueError("Invalid cover image file type")

                # 处理截图
                if form.screenshots.data:
                    for file in request.files.getlist('screenshots'):
                        if file and allowed_file(file.filename):
                            filename = secure_filename(file.filename)
                            screenshot_path = os.path.join(app.config['UPLOAD_FOLDER'],
                                                           (str(game.id) + '_screenshot_' + filename))
                            file.save(screenshot_path)
                            screenshot = GameScreenshots(game_id=game.id, image_path=screenshot_path)
                            db.session.add(screenshot)
                        else:
                            raise ValueError("Invalid screenshot file type")

            # 提交事务
            db.session.commit()
            flash('游戏已成功添加!')
            return redirect(url_for('admin'))
        except Exception as e:
            db.session.rollback()
            flash(f'添加游戏失败: {str(e)}')
            return redirect(url_for('add_game'))

    return render_template('admin/add_game.html', form=form)


@app.route('/game/<int:game_id>/manage_screenshots')
def manage_screenshots(game_id):
    # 根据游戏ID查询游戏和其对应的截图
    game = Game.query.get_or_404(game_id)
    screenshots = game.screenshots
    cover_image = game.cover_image
    return render_template('admin/game_images.html', game=game, screenshots=screenshots, cover_image=cover_image)


# 上传封面图像
@app.route('/admin/game/images/upload_cover/<int:game_id>', methods=['POST'])
def upload_cover_image(game_id):
    game = Game.query.get_or_404(game_id)

    if 'cover-image' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['cover-image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = f"cover_{game_id}_{secure_filename(file.filename)}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    # 删除旧的封面图像（如果存在）
    if game.cover_image:
        try:
            os.remove(os.path.join(game.cover_image))
        except Exception as e:
            print(f"Error deleting file: {e}")

    game.cover_image = file_path
    db.session.commit()
    return jsonify({'file_path': file_path}), 200


# 删除封面图像
@app.route('/admin/game/images/delete_cover/<int:game_id>', methods=['POST'])
def delete_cover_image(game_id):
    game = Game.query.get_or_404(game_id)
    if not game.cover_image:
        return jsonify({'error': 'No cover image to delete'}), 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], game.cover_image)
    try:
        os.remove(file_path)
    except Exception as e:
        print(f"Error deleting file: {e}")
        return jsonify({'error': 'Error deleting file'}), 500

    game.cover_image = None
    db.session.commit()
    return jsonify({'success': True}), 200


# 上传截图
@app.route('/admin/game/images/upload_screenshot/<int:game_id>', methods=['POST'])
def upload_screenshot(game_id):
    game = Game.query.get_or_404(game_id)
    print(request.files)
    if 'screenshots' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['screenshots']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = f"screenshot_{game_id}_{secure_filename(file.filename)}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    screenshot = GameScreenshots(game_id=game_id, image_path=file_path)
    db.session.add(screenshot)
    db.session.commit()
    return jsonify({'file_path': file_path}), 200


# 删除截图
@app.route('/admin/game/images/delete_screenshot/<int:screenshot_id>', methods=['POST'])
def delete_screenshot(screenshot_id):
    screenshot = GameScreenshots.query.get_or_404(screenshot_id)
    file_path = os.path.join(screenshot.image_path)
    try:
        db.session.delete(screenshot)
        db.session.commit()
        os.remove(file_path)
    except Exception as e:
        print(f"Error deleting file: {e}")
        return jsonify({'error': 'Error deleting file'}), 500

    return jsonify({'success': True}), 200


# 列出游戏的截图
@app.route('/admin/game/images/list_screenshots/<int:game_id>', methods=['GET'])
def list_screenshots(game_id):
    game = Game.query.get_or_404(game_id)

    screenshots = [{
        'source': "/" + s.image_path,
        'options': {
            'metadata': {
                'id': s.id,
                'game_id': s.game_id,
                'server_side': True
            }
        }
    } for s in game.screenshots]

    return jsonify(screenshots)


@app.route('/admin/game/images/list_cover_image/<int:game_id>', methods=['GET'])
def list_cover_image(game_id):
    game = Game.query.get_or_404(game_id)

    # 这个列表总是只有一个元素
    cover_image = [{
        'source': "/" + game.cover_image,
        'options': {
            'metadata': {
                'id': game.id,
                'game_id': game.id,
                'server_side': True
            }
        }
    }]

    return jsonify(cover_image)


# =======================
#       正常页面模块
# =======================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/explore')
def explore():
    return render_template('explore.html', tags=get_all_tags())


@app.route('/api/game/search', methods=['GET'])
def search_games():
    search_term = request.args.get('search', default="")
    search_tags = request.args.get('tags', default="")
    max_price = request.args.get('max_price', type=float)
    sort_option = request.args.get('sort', default="")
    discount_only = request.args.get('discount_only', default="false")
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=20, type=int)

    games_query = Game.query
    discount_only = True if discount_only == "true" else False

    # 根据游戏名称进行搜索
    if search_term:
        games_query = games_query.filter(Game.name.ilike(f"%{search_term}%"))

    # 根据标签搜索
    if search_tags:
        tags_list = search_tags.split()
        and_conditions = [Game.tags.ilike(f"%{tag}%") for tag in tags_list]
        games_query = games_query.filter(and_(*and_conditions))

    # 根据最大价格进行过滤
    if max_price is not None:
        games_query = games_query.filter(
            (Game.is_discounted == False) & (Game.price <= max_price) |
            (Game.is_discounted == True) & (Game.discount_price <= max_price)
        )

    # 根据是否只显示打折游戏进行过滤
    if discount_only == True:
        games_query = games_query.filter(Game.is_discounted == True)

    # 根据排序选项进行排序
    if sort_option == "price_asc":
        games_query = games_query.order_by(
            case(
                (Game.is_discounted == True, Game.discount_price),
                else_=Game.price
            ).asc()
        )
    elif sort_option == "price_desc":
        games_query = games_query.order_by(
            case(
                (Game.is_discounted == True, Game.discount_price),
                else_=Game.price
            ).desc()
        )
    elif sort_option == "release_date_desc":
        games_query = games_query.order_by(Game.release_date.desc())
    elif sort_option == "release_date_asc":
        games_query = games_query.order_by(Game.release_date.asc())

    # 分页查询
    pagination = games_query.paginate(page=page, per_page=per_page)
    games = pagination.items
    total_pages = pagination.pages

    # 构建响应数据
    games_list = [
        {
            'id': game.id,
            'name': game.name,
            'type': game.type,
            'release_date': game.release_date.strftime('%Y-%m-%d') if game.release_date else None,
            'release_date_dict': {
                'year': game.release_date.year,
                'month': game.release_date.month,
                'day': game.release_date.day
            } if game.release_date else None,
            'price': game.price,
            'is_discounted': game.is_discounted,
            'discount_price': game.discount_price,
            'developer': game.developer,
            'publisher': game.publisher,
            'tags': game.tags,
            'url': 'game/' + str(game.id),
            'picture_url': game.cover_image if game.cover_image else '/static/images/game_no_cover.png'
        }
        for game in games
    ]

    response = {

        'response': 'success',
        'games': games_list,

        'search_params': {
            'search_term': search_term,
            'search_tags': search_tags,
            'max_price': max_price,
            'sort_option': sort_option,
            'page': page,
            'per_page': per_page
        },

        'total_pages': total_pages,
        'total_games': pagination.total,

    }

    return jsonify(response)


# TODO:即将废弃
@app.route('/search', methods=['GET'])
def search():
    keyword = request.args.get('keyword', '')
    results = []
    # 查询数据库，筛选包含关键字的游戏
    games = Game.query.filter(Game.name.ilike(f"%{keyword}%")).limit(10).all()
    # 将查询结果转换为字典形式
    for game in games:
        results.append({"name": game.name, "url": "game/" + str(game.id)})
    return jsonify(results)


@app.route('/game/<int:game_id>')
def game_detail(game_id):
    # 创建一个数据库会话
    session = Session()
    # 使用 Session.get() 方法获取游戏信息
    game = session.get(Game, game_id)
    # 关闭数据库会话
    session.close()
    # 渲染游戏展示页面，并传递游戏信息到模板中
    return render_template('game_detail.html', game=game)


@app.route('/api/user/cart/add/<int:game_id>', methods=['POST'])
@login_required
def add_to_cart(game_id):
    game = Game.query.get_or_404(game_id)
    cart = current_user.cart

    # TODO:注册时创建购物车
    if cart is None:
        # 如果用户还没有购物车，则创建一个新的购物车
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()  # 先提交以生成购物车ID

    # 检查购物车中是否已经存在该游戏
    cart_item = CartItem.query.filter_by(cart_id=cart.id, game_id=game.id).first()

    if cart_item:
        # 如果存在，则更新数量
        cart_item.quantity += 1
    else:
        # 如果不存在，则添加新项
        cart_item = CartItem(cart_id=cart.id, game_id=game.id, quantity=1)
        db.session.add(cart_item)

    db.session.commit()
    flash('添加成功', 'success')
    return redirect(url_for('view_cart'))


@app.route('/api/user/cart/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_cart_item(item_id):
    cart = current_user.cart
    cart_item = CartItem.query.filter_by(cart_id=cart.id, game_id=item_id).first()
    if not cart_item:
        abort(404)  # 如果购物车项目不存在，则返回404

    db.session.delete(cart_item)
    db.session.commit()
    flash('已从购物车删除', 'success')
    return redirect(url_for('view_cart'))


@app.route('/cart')
@login_required
def view_cart():
    cart = current_user.cart
    if cart:
        items = cart.items
    else:
        items = []

    total_price = sum(
        (item.game.discount_price if item.game.is_discounted else item.game.price) * item.quantity
        for item in items
    )

    total_price = round(total_price, 2)

    return render_template('cart.html', items=items, total_price=total_price)


@app.route('/checkout')
@login_required
def checkout():
    # 检查用户是否有未支付的订单
    unpaid_order = Order.query.filter_by(user_id=current_user.id, status='Pending').first()
    if unpaid_order:
        flash('您有未支付的订单，请先完成支付', 'warning')
        return redirect(url_for('view_orders'))

    # 检查购物车是否为空
    cart = current_user.cart
    if not cart or not cart.items:
        flash('购物车是空的！', 'warning')
        return redirect(url_for('view_cart'))

    # 创建订单
    order = Order(user_id=current_user.id, total_price=0)  # 初始化订单，总价先设置为0
    db.session.add(order)
    db.session.commit()

    # 将购物车中的商品添加到订单中
    total_price = 0
    for cart_item in cart.items:
        order_item = OrderItem(order_id=order.id, game_id=cart_item.game_id, quantity=cart_item.quantity,
                               price=cart_item.game.price)
        db.session.add(order_item)
        total_price += cart_item.quantity * cart_item.game.price  # 计算总价
    order.total_price = total_price  # 更新订单总价
    db.session.commit()

    # 清空购物车
    CartItem.query.filter_by(cart_id=cart.id).delete()
    db.session.delete(cart)
    db.session.commit()

    flash('成功创建订单！', 'success')
    return redirect(url_for('view_orders'))


@app.route('/orders')
@login_required
def view_orders():
    orders = current_user.orders
    return render_template('orders.html', orders=orders)


@app.route('/order/<int:order_id>')
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    # 确认订单属于当前用户
    if order.user_id != current_user.id:
        flash('无权限查看此订单', 'error')
        return redirect(url_for('view_orders'))
    return render_template('order_detail.html', order=order)


@app.route('/order/<int:order_id>/pay')
@login_required
def pay_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash('无权限查看此订单', 'error')
        return redirect(url_for('view_orders'))
    # 在这里添加支付逻辑，比如跳转到支付页面或者调用支付接口
    # 如果订单为待支付，继续支付流程
    if order.status == 'Pending':
        # 在这里模拟支付成功
        order.status = 'Paid'
        db.session.commit()
        flash('订单 {} 支付成功！'.format(order_id), 'success')
    else:
        flash('订单 {} 已支付或已过期'.format(order_id), 'error')

    return redirect(url_for('view_orders'))


# =======================
#       功能页面模块
# =======================

@app.route('/redirect')
def redirect_with_message():
    """ 重定向到指定URL并显示消息 """

    # TODO: 支持成功/失败图标

    # 从查询参数中获取重定向 URL 和消息
    redirect_url = request.args.get('url', '/')
    message = request.args.get('message', '跳转中')
    title = request.args.get('title', '跳转中')

    # 默认的重定向时间
    redirect_time = 5

    # 将重定向 URL、消息和倒计时时间传递给模板
    return render_template('redirect.html', redirect_url=redirect_url, message=message, redirect_time=redirect_time,
                           tittle=title)


# 定义定时任务，每分钟检查一次订单是否过期
@scheduler.scheduled_job('interval', minutes=1)
def check_expired_orders():
    print("[定时任务]检查过期订单...")
    with app.app_context():
        orders = Order.query.filter_by(status='Pending').all()
        for order in orders:
            # 检查订单是否超过30分钟
            if order.created_at + timedelta(minutes=30) < datetime.utcnow():
                print('订单 {} 已过期'.format(order.id))
                # 更新订单状态为过期
                order.status = 'Expired'
                db.session.commit()


@app.cli.command('clean_files')
def clean_files():
    with app.app_context():
        # 查询所有 cover_img 和 image_path
        cover_imgs = {img[0] for img in db.session.query(Game.cover_image).all()}
        screenshot_imgs = {img[0] for img in db.session.query(GameScreenshots.image_path).all()}

        # 所有数据库中的文件
        db_files = cover_imgs.union(screenshot_imgs)

        # 遍历上传文件夹，检查是否有文件不存在于数据库中
        unused_files = []
        for root, dirs, files in os.walk(UPLOAD_FOLDER):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, UPLOAD_FOLDER)
                # print("RRRRR",relative_path,"PPPP",file_path)
                if file_path not in db_files:
                    unused_files.append(file_path)

        # 检查数据库中的文件是否存在于文件系统中
        missing_files = []
        for file in db_files:
            if file:
                if not os.path.exists(file):
                    missing_files.append(file)

        print("="*30)
        # 打印所有异常数据和文件
        if unused_files:
            print("Unused files found:")
            for file in unused_files:
                print(file)

        if missing_files:
            print("Missing files in filesystem:")
            for file in missing_files:
                print(file)

        print(f"Found {len(unused_files)} unused files.")
        print(f"Found {len(missing_files)} missing files.")

        # 询问用户是否删除未使用的文件
        if unused_files:
            delete = input("Do you want to delete these unused files? (y/n): ")
            if delete.lower() == 'y':
                for file in unused_files:
                    os.remove(file)
                    print(f"Deleted unused file: {file}")




if __name__ == '__main__':
    app.run(port=2333, debug=True)
