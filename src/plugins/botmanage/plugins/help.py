from nonebot import on_command, get_loaded_plugins
from nonebot.plugin import on_message
from src.common import Bot, MessageEvent, BOTNAME, FRIENDREQUESTCODESALT, BOT_VERSION
from src.common.rules import func_ls, group_func_off, full_match
from src.utils import reply_header, link_res, get_hash_code


_plugin_name = "使用帮助"


WIDTH = 25
total_help = f"""
<Sanae-Bot使用说明>
∴*~★*∴*·∴~*★*∴
[{BOTNAME} on|off] 控制{BOTNAME}在本群的全局开关（需群管理权限）
[开启|关闭 功能名] 控制单个功能开关（需群管理权限）
[签到] 领取每日低保
[查询等级] 查看当前等级
═━═━功能列表━═━═
""" """{sv_ls_}""" f"""
━━━━━━━━━━━━
发送[使用帮助 功能名]查看功能详细说明
at{BOTNAME}并发送[屏蔽我] 使{BOTNAME}不响应你的消息
[关于Sanae-Bot] 本Bot信息
//**隐藏功能请自行探索**//
测试、反馈、交流群：708242151
""".strip()


helper = on_command('help', aliases={'帮助', '使用帮助', '使用说明'}, priority=1)


@helper.handle()
async def show_help(bot: Bot, event: MessageEvent):
    sv_hassub = set([func_ls[f][1] for f in func_ls if func_ls[f][1] != 'top'])
    diver_name = lambda x: f'-{x}-'

    # 总帮助说明
    if not event.message.extract_plain_text().strip():
        if event.message_type == 'group':
            sv_on = [f for f in func_ls if func_ls[f][1] == 'top' and f not in group_func_off[str(event.group_id)]]
            sv_off = [f for f in func_ls if func_ls[f][1] == 'top' and f in group_func_off[str(event.group_id)]]
            sv_ls = ''

            if sv_on:
                sv_ls += "已开启 ✓" + '\n' + '\n'.join(map(diver_name, sv_on))
            if sv_off:
                if sv_on:
                    sv_ls += "\n———————\n"
                sv_ls += "已关闭 ✗" + '\n' + '\n'.join(map(diver_name, sv_off))
        else:
            sv_ls = '\n'.join(map(diver_name, func_ls))
        if sv_hassub:
            sv_ls += "\n———————\n" + "⇣ 含子功能 ⇣\n" + '\n'.join(map(diver_name, sv_hassub))
        await helper.finish(total_help.format(sv_ls_=sv_ls))

    # 单个功能
    name = event.message.extract_plain_text().strip()
    if name not in func_ls and name not in sv_hassub:
        await helper.finish(reply_header(event, f'没有找到名字为<{name}>的功能'))
    else:
        usage = func_ls[name][0] if name in func_ls else ''
        if sub_usage := [f for f in filter(lambda x: func_ls[x][1] == name, func_ls)]:  # 子功能菜单，附加在功能末尾
            if event.message_type == 'group':
                sv_on = [f for f in sub_usage if func_ls[f][1] != 'top' and f not in group_func_off[str(event.group_id)]]
                sv_off = [f for f in sub_usage if func_ls[f][1] != 'top' and f in group_func_off[str(event.group_id)]]
                sv_ls=''

                if sv_on:
                    sv_ls += "已开启 ✓" + '\n' + '\n'.join(map(diver_name, sv_on))
                if sv_off:
                    if sv_on:
                        sv_ls += "\n———————\n"
                    sv_ls += "已关闭 ✗" + '\n' + '\n'.join(map(diver_name, sv_off))
            else:
                sv_ls = '\n'.join(map(diver_name, sub_usage))

            usage += '发送[使用帮助 功能名]查看以下子功能说明\n———————\n' + sv_ls
        if not usage:
            usage = '此功能还未添加描述'
        await helper.finish(f">——<{name}>——<\n{usage}")


about_bot = on_message(rule=full_match("关于Sanae-Bot"))


@about_bot.handle()
async def show_info(bot: Bot, event: MessageEvent):
    # TODO: 完善信息

    msg = link_res('sanae-bot.gif') + f'\nversion-{BOT_VERSION}\n'
    if event.message_type == 'group':
        msg += f'本群授权时间：<->\n本群授权期至：<->\n'
    msg += f'测试、反馈、交流群：708242151'
    await about_bot.finish(msg)