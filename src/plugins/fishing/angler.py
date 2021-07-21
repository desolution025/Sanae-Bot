from datetime import datetime
from typing import Union
from src.common import logger

class Angler:
    """
    钓鱼的人，类属性cluster存储当前正在钓鱼的用户
    
    Attributes:

        uid (str): 用户id，为方便从数据库存取转为了字符串
        rod (int): 用户当前使用的钓竿
    """

    cluster = {}
    logger.debug(f'当前钓鱼成员:{cluster}')

    def __init__(self, uid: Union[int, str]) -> None:
        self.uid = str(uid)
        self.rod = 1
        self.cast_time = datetime.now()
        self.bit_time = None
        self.pull_up_time = None
    
    def cast(self):
        self.__class__.cluster[self.uid] = self
        
    def pull_up(self):
        del self.__class__.cluster[self.uid]

    def free(self):
        return self.uid not in self.__class__.cluster

    def fail(self):
        if self.uid in self.__class__.cluster:
            self.pull_up()
        else:
            logger.warning(f'{self.uid} 不在正在钓鱼的用户列表中！')

    @classmethod
    def get_angler(cls, uid: Union[int,str]):
        if str(uid) in cls.cluster:
            return cls.cluster[str(uid)]
        else:
            return None