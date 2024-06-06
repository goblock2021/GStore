# By GoBlock2021
# 12023052132 韩昕炜 仅做作业用途，禁止商用

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import sessionmaker

print("欢迎访问我的期末小作业")
print("12023052132 韩昕炜")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///web_data.db'
db = SQLAlchemy(app)

migrate = Migrate(app, db)
with app.app_context():
    Session = sessionmaker(bind=db.engine)

app.config['SECRET_KEY'] = 'your_secret_key'  # TODO: 替换为随机的安全密钥
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
    release_date = db.Column(db.Date, nullable=True)
    price = db.Column(db.Float, nullable=False)
    is_discounted = db.Column(db.Boolean, default=False)
    discount_price = db.Column(db.Float, nullable=True)
    developer = db.Column(db.String(256), nullable=True)
    publisher = db.Column(db.String(256), nullable=True)
    tags = db.Column(db.String(255), nullable=True)


# 加载用户的回调函数
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        existing_user = User.query.filter_by(username=username).first()
        # 检查用户名是否已存在
        if not existing_user:
            # 将密码哈希后保存到数据库中，实际中应当存储到数据库中
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            return 'Registration successful. <a href="/">Go to Login</a>'
        else:
            return 'Username already exists. Choose another username.'

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


@app.route('/admin/games', methods=['GET'])
@login_required
def admin_games():
    # 确保只有管理员可以访问游戏管理页面
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('index'))
    # 获取所有游戏
    games = Game.query.all()
    return render_template('admin_games.html', games=games)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/explore')
def explore():
    search_term = request.args.get('search', default=None)

    if search_term:
        # Perform search if search term is provided
        games = Game.query.filter(Game.name.ilike(f"%{search_term}%")).all()
    else:
        # Show all games if no search term is provided
        games = Game.query.all()

    return render_template('explore.html', games=games, search_term=search_term)


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


if __name__ == '__main__':
    app.run(port=2333, debug=True)
