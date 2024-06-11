# By GoBlock2021

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, BooleanField, SubmitField
from wtforms.fields.choices import SelectField
from wtforms.fields.datetime import DateField
from wtforms.validators import DataRequired
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import sessionmaker
from sqlalchemy import and_, case

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///web_data.db'
db = SQLAlchemy(app)

migrate = Migrate(app, db)
with app.app_context():
    Session = sessionmaker(bind=db.engine)

app.config['SECRET_KEY'] = 'ebboPjKwol5krcOdOL7WakhoIIBShlv4'
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# 用户模型
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)


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


class GameForm(FlaskForm):
    name = StringField('名称', validators=[DataRequired()])
    type = SelectField('类型', choices=[('Game', '游戏'), ('DLC', 'DLC')], validators=[DataRequired()])
    release_date = DateField('发行日期')
    price = FloatField('价格', validators=[DataRequired()])
    is_discounted = BooleanField('打折')
    discount_price = FloatField('折后价')
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

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# =======================
#       后台管理模块
# =======================

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
        return redirect(url_for('admin_games'))
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
    return redirect(url_for('admin_games'))


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
        flash('New game added successfully!', 'success')
        return redirect(url_for('admin_games'))

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


@app.route('/api/search_game')
def game_list_api():
    # TODO: 实现游戏列表的 API，取代服务端渲染html
    return "Still Working ... :)"


@app.route('/search', methods=['GET'])
def search():
    keyword = request.args.get('keyword', '')
    results = []
    # 查询数据库，筛选包含关键字的游戏
    games = Game.query.filter(Game.name.ilike(f"%{keyword}%")).all()
    # 将查询结果转换为字典形式
    for game in games:
        results.append({"name": game.name, "url": "game/" + str(game.id)})  # 假设 Game 模型有一个 'url' 字段
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
    return "Nothing Here :)"


if __name__ == '__main__':
    app.run(port=2333, debug=True)
