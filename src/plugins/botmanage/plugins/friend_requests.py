from nonebot.plugin import on_request
from nonebot_adapter_gocq.event import FriendRequestEvent

from src.common import Bot, FRIENDREQUESTCODESALT, SUPERUSERS, logger
from src.common.rules import comman_rule
from src.common.levelsystem import UserLevel
from src.utils import get_hash_code


_plugin_name = '处理好友请求'


friend_request = on_request(rule=comman_rule(FriendRequestEvent))


@friend_request.handle()
async def virify_request(bot: Bot, event: FriendRequestEvent):
    pure_comment = event.comment.split('\n回答:')[1]
    async with UserLevel(event.user_id) as user:
        if pure_comment == get_hash_code(FRIENDREQUESTCODESALT, event.get_user_id()) and user.level > 3:
            # await event.approve()  为啥这个不好使？？？
            await bot.set_friend_add_request(flag=event.flag, approve=True)
            logger.success(f'Approved friend request with user: {event.user_id}')
            for sps in SUPERUSERS:
                await bot.send_private_msg(user_id=sps, message=f'用户 {event.user_id} 通过了好友验证，已添加好友')
        else:
            logger.info(f'Wrong request-code, refuse to add friend with: {event.user_id}')
            await bot.set_friend_add_request(flag=event.flag, approve=False)