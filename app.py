# By GoBlock2021
import json
from datetime import datetime, timedelta, date
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, abort
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, BooleanField, SubmitField
from wtforms.fields.choices import SelectField
from wtforms.fields.datetime import DateField
from wtforms.validators import DataRequired, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import sessionmaker
from sqlalchemy import and_, case

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///web_data.db'
db = SQLAlchemy(app)

scheduler = BackgroundScheduler()
scheduler.start()

migrate = Migrate(app, db)
with app.app_context():
    Session = sessionmaker(bind=db.engine)

app.config['SECRET_KEY'] = 'ebboPjKwol5krcOdOL7WakhoIIBShlv4'
login_manager = LoginManager(app)
login_manager.login_view = 'login'


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
    submit = SubmitField('添加游戏')





# 加载用户的回调函数
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


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
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
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
# TODO: 添加管理员权限检查
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
# TODO: 添加管理员权限检查
def admin_games():
    # 确保只有管理员可以访问游戏管理页面
    if not current_user.is_admin:
        flash('您没有权限访问此页面', 'error')
        return redirect(url_for('index'))
    # 获取所有游戏
    games = Game.query.all()
    return render_template('admin_games.html', games=games)


@app.route('/admin/games/<int:game_id>/edit', methods=['GET', 'POST'])
@login_required
# TODO: 添加管理员权限检查
def edit_game(game_id):
    game = Game.query.get_or_404(game_id)
    form = GameForm(obj=game)
    if form.validate_on_submit():
        game.name = form.name.data
        game.release_date = form.release_date.data  # 更新日期
        game.price = form.price.data
        game.is_discounted = form.is_discounted.data
        game.discount_price = form.discount_price.data
        game.developer = form.developer.data
        game.publisher = form.publisher.data
        game.tags = form.tags.data
        db.session.commit()
        return redirect(url_for('admin'))
    else:
        flash('请检查输入是否正确', 'error')
    return render_template('edit_game.html', form=form, game_id=game_id)


@app.route('/admin/games/<int:game_id>/delete', methods=['POST'])
@login_required
# TODO: 添加管理员权限检查
def delete_game(game_id):
    # 确保只有管理员可以添加新游戏
    if not current_user.is_admin:
        flash('您没有权限访问此页面', 'error')
        return redirect(url_for('index'))
    game = Game.query.get_or_404(game_id)
    db.session.delete(game)
    db.session.commit()
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
        new_game = Game(
            name=form.name.data,
            release_date=form.release_date.data,
            price=form.price.data,
            is_discounted=form.is_discounted.data,
            discount_price=form.discount_price.data,
            developer=form.developer.data,
            publisher=form.publisher.data,
            tags=form.tags.data
        )
        db.session.add(new_game)
        db.session.commit()
        flash('游戏添加成功！', 'success')
        return redirect(url_for('admin'))

    return render_template('add_game.html', form=form)


# =======================
#       正常页面模块
# =======================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/explore')
def explore():
    search_term = request.args.get('search', default="")
    search_tags = request.args.get('tags', default="")
    max_price = request.args.get('max_price', type=float)  # 获取最大价格参数
    sort_option = request.args.get('sort', default="")  # 获取排序选项

    games_query = Game.query

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

    # 根据排序选项进行排序
    if sort_option == "price_asc":
        # 排序时考虑折后价格
        games_query = games_query.order_by(
            case(
                (Game.is_discounted == True, Game.discount_price),
                else_=Game.price
            ).asc()
        )
    elif sort_option == "price_desc":
        # 排序时考虑折后价格
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

    games = games_query.all()

    # 查询所有可用于搜索的标签
    # TODO: 可能会有性能问题，可以考虑缓存标签
    all_tags = set()
    for game in games:
        if game.tags:
            tags = game.tags.split(' ')
            all_tags.update(tags)

    return render_template('explore.html', games=games, search_term=search_term, search_tags=search_tags,
                           max_price=max_price, sort_option=sort_option, tags=sorted(all_tags))


@app.route('/api/game/search', methods=['GET'])
def search_games():
    search_term = request.args.get('search', default="")
    search_tags = request.args.get('tags', default="")
    max_price = request.args.get('max_price', type=float)
    sort_option = request.args.get('sort', default="")
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=10, type=int)

    games_query = Game.query

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

    # games = games_query.all()

    # 分页查询
    pagination = games_query.paginate(page=page, per_page=per_page)
    games = pagination.items

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
            'url': 'game/' + str(game.id)
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
        }
    }

    return jsonify(response)


@app.route('/search', methods=['GET'])
def search():
    keyword = request.args.get('keyword', '')
    results = []
    # 查询数据库，筛选包含关键字的游戏
    games = Game.query.filter(Game.name.ilike(f"%{keyword}%")).all()
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


@app.route('/order/<int:order_id>/pay')
@login_required
def pay_order(order_id):
    order = Order.query.get_or_404(order_id)
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

    # TODO: 调整页面布局，支持成功/失败图标

    # 从查询参数中获取重定向 URL 和消息
    redirect_url = request.args.get('url', '/')
    message = request.args.get('message', '跳转中')
    title = request.args.get('title', '跳转中')

    # 你可以设置一个默认的重定向时间，例如 5 秒
    redirect_time = 5

    # 将重定向 URL、消息和倒计时时间传递给模板
    return render_template('redirect.html', redirect_url=redirect_url, message=message, redirect_time=redirect_time,
                           tittle=title)


@app.route('/debug')
def dbg():
    return render_template('debug.html')


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


if __name__ == '__main__':
    app.run(port=2333, debug=True)
