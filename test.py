import itertools
from datetime import date
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import random
from app import Game

# 初始化 Flask 应用
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///web_data.db'  # 替换为你的数据库URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

g_num = int(input("请输入需要的样本数据量："))

# 确保数据库和表已创建
with app.app_context():
    db.create_all()

# 定义12个标签
tag_list = [
    '冒险', '角色扮演', '动作', '射击', '益智',
    '策略', '模拟', '体育', '竞速', '恐怖',
    '休闲', '多人'
]

# 一堆发行商的名称
publishers = [
    "Electronic Arts",
    "Activision",
    "Ubisoft",
    "Square Enix",
    "Nintendo",
    "Sony Interactive Entertainment",
    "Microsoft Studios",
    "Bethesda Softworks",
    "Rockstar Games",
    "2K Games",
    "Capcom",
    "Bandai Namco Entertainment",
    "Sega",
    "Blizzard Entertainment",
    "Konami",
    "Warner Bros. Interactive Entertainment",
    "CD Projekt",
    "THQ Nordic",
    "Paradox Interactive",
    "Deep Silver",
    "Devolver Digital",
    "Atari",
    "Focus Home Interactive",
    "Gearbox Software",
    "505 Games",
    "Annapurna Interactive",
    "Koei Tecmo",
    "Tencent Games",
    "Riot Games",
    "Epic Games"
]

# 定义游戏名称的不同部分
prefixes = [
    "Shadow", "Eternal", "Mystic", "Galactic", "Infinite", "Legend of", "Secret of",
    "Dark", "Fallen", "Rising", "Ancient", "Hidden", "Lost", "Beyond"
]

middles = [
    "Dragon", "Knight", "Empire", "Quest", "Saga", "Hero", "Realm", "Warrior",
    "Magic", "Mystery", "Hunter", "Fantasy", "World", "Adventure"
]

suffixes = [
    "Reborn", "Chronicles", "Odyssey", "Revenge", "Legacy", "War", "Prophecy",
    "Journey", "Awakening", "Destiny", "Conquest", "Legend", "Reckoning", "Ascension"
]

# 生成所有可能的组合
all_combinations = list(itertools.product(prefixes, middles, suffixes))
random.shuffle(all_combinations)  # 打乱顺序以增加随机性


# 定义一个生成器来逐个返回唯一的游戏名称
def generate_unique_game_names(combinations):
    for prefix, middle, suffix in combinations:
        yield f"{prefix} {middle} {suffix}"


# 创建生成器对象
unique_name_generator = generate_unique_game_names(all_combinations)

# 生成唯一的游戏名称
game_names = [next(unique_name_generator) for _ in range(g_num)]

games = []
for i in range(g_num):
    selected_tags = random.sample(tag_list, random.randint(1, 10))  # 随机选择1到10个标签
    tags = ' '.join(selected_tags)  # 将标签组合成字符串
    discounted = bool(random.getrandbits(1))  # 随机折扣状态
    price = round(random.uniform(0, 648), 2)  # 随机价格
    discount_price = round(random.uniform(0, price), 2) if discounted else None
    new_game = Game(
        name=game_names[i],
        release_date=date(random.randint(2000, 2024), random.randint(1, 12), random.randint(1, 28)),  # 随机日期
        type=random.choice(['Game', 'DLC']),
        price=round(random.uniform(0, 648), 2),  # 随机价格
        is_discounted=discounted,
        discount_price=discount_price,
        developer=random.choice(publishers),
        publisher=random.choice(publishers),
        tags=tags  # 随机标签组合
    )
    games.append(new_game)

with app.app_context():
    # 将生成的游戏数据添加到会话
    db.session.bulk_save_objects(games)

    # 提交会话以保存到数据库
    try:
        db.session.commit()
        print(g_num, "games added successfully.")
    except Exception as e:
        print("An error occurred:", e)
        db.session.rollback()  # 如果出错，回滚事务
