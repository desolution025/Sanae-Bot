from typing import Union
from datetime import datetime
from pathlib import Path
import ujson as json
import yaml

from nonebot.exception import FinishedException

from src.common import logger
from src.common.dbpool import QbotDB


goods_file = Path(__file__).parent/'goods.yml'
goods = {}

def refresh_goods():
    global goods
    with goods_file.open(encoding='utf-8') as f:
        yaml.warnings({'YAMLLoadWarning': False})
        goods = yaml.load(f)

refresh_goods()


class Shelf:

    user_ls = {}  # 所有用户实例

    def __new__(cls, uid: int):
        """用户已被实例化过会返回用户列表中的实例而不会重新创建"""
        if uid in cls.user_ls:
            return cls.user_ls[uid]
        else:
            return super().__new__(cls)

    def __init__(self, uid: int) -> None:
        """未创建过用户时实例化一个新用户"""
        if uid not in self.__class__.user_ls:
            self.uid = uid
            self.loaded = False  # 是否已经读取了用户数据

    @classmethod
    async def load_all_shelf_data(cls):
        async with QbotDB() as qb:
            result = await qb.queryall('SELECT uid FROM shop;')
        for r in result:
            cls.user_ls[r.uid] = Shelf(r.uid)
        logger.success(f'连接数据库，读取到 {len(cls.user_ls)} 条商店信息')
        if len(set(cls.user_ls)) != len(result):
            logger.warning("There are duplicate record(s) in table: shelf !!")

    def __refresh_goods(self):
        """刷新物品，未存入数据库，应被其它方法调用"""
        self.goods = goods['all']  # TODO: 商品按照等级和日期分类计算上架方式
        for g in self.goods:
            g['num'] = 1  # 定义数量
        self.time = datetime.now()

    async def create_user(self):
        self.__refresh_goods()
        async with QbotDB() as qb:
            await qb.insert(
                            "INSERT INTO shop (uid, goods, gen_time) VALUES(%s, %s, NOW())",
                            (self.uid, json.dumps(self.goods, ensure_ascii=False))
                            )
        self.__class__.user_ls[self.uid] = self  # 用户列表加入该用户
        logger.info(f'注册一个新用户货架：{self.uid}')

    async def load_user(self):
        if self.uid in self.__class__.user_ls:
            async with QbotDB() as qb:
                info = await qb.queryone(
                                    'select uid, goods, gen_time from shop where uid=%s',
                                    (self.uid,)
                                    )
            self.goods = json.loads(info.goods)
            self.time = info.gen_time
        else:
            await self.create_user()
        self.loaded = True

    async def _store_info(self):
        async with QbotDB() as qb:
            await qb.update('UPDATE shop SET goods=%s, gen_time=NOW() WHERE uid=%s',
                            (json.dumps(self.goods, ensure_ascii=False), self.uid))
            logger.debug(f'刷新用户 {self.uid} 货架信息')

    async def refresh(self):
        """刷新货架，一般使用道具或者0点和12点整点刷新"""
        self.__refresh_goods()
        await self._store_info()

    async def sold(self, index: int, num: int):
        """售出商品

        Args:
            index (int): 商品在货架上的编号
            num (int): 售出的数量
        """
        self.goods[index]['num'] -= num
        await self._store_info()

    async def __aenter__(self):
        if not self.loaded:
            await self.load_user()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type and exc_type is not FinishedException:
            logger.error(f'EXCType: {exc_type}; EXCValue: {exc_val}; EXCTraceback: {exc_tb}')