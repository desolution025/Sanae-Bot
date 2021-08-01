from pathlib import Path
import configparser
from pydantic import BaseModel

# from ipaddress import IPv4Address
import aiomysql
from pymysql import Error as PymysqlError

try:
    from src.common.log import logger
except ImportError:
    from loguru import logger


# 数据库配置模型
class DBConfig(BaseModel):
    # host: IPv4Address  连接池传入IPV4地址不能自动转换str
    host: str
    port: int
    user: str
    password: str


cfg = configparser.ConfigParser()
cfg.read(Path(__file__).parent/"dbpool.ini")

dbcfg = DBConfig(**dict(cfg.items("client")))  # 数据库配置


class AttrDict(dict):
    """Dict that can get attribute by dot, and doesn't raise KeyError"""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            return None

class AttrDictCursor(aiomysql.DictCursor):
    dict_type = AttrDict


class MysqlPool:
    """
    :Summary:

        mysql连接池的基类，使用时用子类继承的方法以在不同的子类属性中存储不同的数据库连接池实例
    
    :Args:
    
        ``db``: 要使用哪个数据库
        ``**kw``: 其他参数需要传输数据库配置信息
    """
    # 连接池对象
    _pool = None

    def __init__(self, db: str, **kw):
        self.dbinfo = kw
        self.dbinfo['db'] = db
        self.dbinfo['charset'] = 'utf8mb4'
        self.q = True # 查询模式，用于自动在上下文管理中判断是否需要执行commit

    async def get_conn(self):
        if self.__class__._pool is None:
            self.__class__._pool = await aiomysql.create_pool(**self.dbinfo)
            logger.success('Created connected pool!')
        self._conn : aiomysql.Connection = await self.__class__._pool.acquire()
        self._cursor : aiomysql.DictCursor = await self._conn.cursor(AttrDictCursor)
        return self

    async def _execute(self, cmd, param=()):
        try:
            return await self._cursor.execute(cmd, param)
        except PymysqlError as err:
            logger.exception(err)

    async def queryall(self, cmd, param=()):
        await self._execute(cmd, param)
        return await self._cursor.fetchall()

    async def queryone(self, cmd, param=()):
        await self._execute(cmd, param)
        return await self._cursor.fetchone()

    async def querymany(self, cmd, num, param=()):
        await self._execute(cmd, param)
        return await self._cursor.fetchmany(num)

    async def insert(self, cmd, param=()):
        affect_rows_numbers = await self._execute(cmd, param)
        self.q = False
        return affect_rows_numbers

    async def insertmany(self, cmd, param=[]):
        await self._cursor.executemany(cmd, param)
        self.q = False

    async def update(self, cmd, param=()):
        affect_rows_numbers = await self._execute(cmd, param)
        self.q = False
        return affect_rows_numbers

    async def delete(self, cmd, param=()):
        affect_rows_numbers = await self._execute(cmd, param)
        self.q = False
        return affect_rows_numbers

    async def begin(self):
        """
        @summary: 开启事务
        """
        # self._conn.autocommit(0)
        await self._conn.begin()

    async def commit(self):
        await self._conn.commit()

    async def rollback(self):
        await self._conn.rollback()

    async def close(self):
        try:
            await self._cursor.close()
            self.__class__._pool.release(self._conn)
        except PymysqlError as err:
            logger.exception(err)
    
    @classmethod
    async def close_pool(cls):
        if cls._pool is not None:
            cls._pool.close()
            await cls._pool.wait_closed()
            logger.info('Close mysql connection pool!')
        else:
            logger.info('Did not created mysql connection pool, skip closing!')

    async def __aenter__(self):
        await self.get_conn()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            if self.q is False:
                await self.commit()
            await self.close()
        else:
            logger.error(f'EXCType: {exc_type}; EXCValue: {exc_val}; EXCTraceback: {exc_tb}')


class QbotDB(MysqlPool):
    """
    qbotdb连接池，lable: userinfo, corpus, calltimes
    """
    def __init__(self,) -> None:
        super().__init__('qbotdb', **dbcfg.dict())


class GalleryDB(MysqlPool):
    """
    图库连接池，lable: gallery
    """
    def __init__(self,) -> None:
        super().__init__('gallery', **dbcfg.dict())


if __name__ == "__main__":
    # print(dbcfg.json())
    # print(dbcfg.dict())
    import asyncio

    async def tst():
        async with QbotDB() as qb:
            result = await qb.queryall("select * from userinfo limit 5")
            # result = await qb.queryone("SELECT LAST_INSERT_ID();")
        print(type(result))
        print(result)
        # for r in result:
        #     print(type(r))
        #     if isinstance(r, AttrDict):
        #         print(r.qq_number)
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(tst())
    print('run over')
    # loop.close()
    # with QbotDB() as qb:
    #     result = qb.queryall("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = 'qbotdb' AND TABLE_NAME = 'calltimes' AND column_name like '%%_count';")
    #     print(result)
