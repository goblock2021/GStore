# GStore

这是一个使用Python和JavaScript开发的游戏商店项目。项目使用了Flask框架，并使用SQLite作为数据库。

## 项目特性

- 用户注册和登录功能
- 游戏搜索和筛选功能
- 购物车
- 订单创建和支付(需要额外配置支付接口)功能
- 后台管理模块，包括游戏的增删改查
- 定时任务，用于检查订单是否过期

## 项目结构

主要的Python代码位于`app.py`文件中，包括了路由和数据库模型。

前端代码主要在`templates`文件夹中，使用了HTML和JavaScript。

数据库文件为`instance/web_data.db`，使用SQLite作为数据库。

static文件夹中包含了一些静态资源，如图片和CSS文件。

## 如何运行

1. 确保你的环境中已经安装了Python和pip。
2. 克隆项目到本地：
   ```bash
   git clone https://github.com/goblock2021/GStore.git
   cd GStore
    ```
3. (可选) 使用虚拟环境：
   ```bash
   python -m venv ./venv
   venv\Scripts\activate
   ```
4. 安装项目依赖：
    ```bash
    pip install -r requirements.txt
    ```
5. 运行项目：
   ```bash
   python app.py
   ```

## 开源协议

本项目使用MIT开源协议，详情请参考[LICENSE](LICENSE)文件。

## 贡献

欢迎任何形式的贡献，包括但不限于提交问题、提出改进建议、提交Pull Request。

## 联系方式

如果你有任何问题或者建议，欢迎通过GitHub Issues与我联系。