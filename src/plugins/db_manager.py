from nonebot import get_driver
from src.common.dbpool import QbotDB


driver = get_driver()


@driver.on_shutdown
async def close_pool():
    await QbotDB.close_pool()