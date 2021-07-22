import re
from cn2an import cn2an

from nonebot import on_command
from nonebot_adapter_gocq.exception import ActionFailed

from src.common.rules import sv_sw
from src.common.levelsystem import FuncLimiter
from src.common import logger, Bot, MessageEvent, T_State, MessageSegment, CANCEL_EXPRESSION
from src.utils import PagingBar, reply_header
from .netease import search_163
from .qqmusic import search_qm
from .migu import search_migu

# TODO: 重写，太乱

plugin_name = "点歌"
plugin_usage = "网易云、QQ音乐、咪咕，其它再说"


numrex = re.compile(r'[^\d一二三四五六七八九十]*([\d一二三四五六七八九十]*)\D*')


#根据每页最大显示数量生成分页列表
def create_music_page(music_list, display_per_pg: int = 5) -> dict:
    music_page = {}
    for i, musicinfo in enumerate(music_list):
        pgnum = i//display_per_pg+1
        if f'page{pgnum}' not in music_page:
            music_page[f'page{pgnum}'] = [musicinfo]
        else:
            music_page[f'page{pgnum}'].append(musicinfo)
    return music_page


#生成文字列表
def create_str_page(music_pg: dict) -> dict:
    str_pg = {}
    unitid = 0
    for i, unitlist in enumerate(music_pg):
        str_pg[f'page{i+1}'] = ''
        for music in music_pg[unitlist]:
            unitid += 1
            str_pg[f'page{i+1}'] += f'\n{str(unitid).rjust(2, "0")}. {music["artists"]} - {music["name"]}'
    return str_pg

#生成网易云与QQ音乐的混合列表，返回混合的索引列表与文字列表
def mix_song_list(netease: list, qqmusic: list, step: int = 3) -> dict:
    if netease is None:
        netease = []
    if qqmusic is None:
        qqmusic = []
    max_len = max(len(netease), len(qqmusic))
    srlnum = 0
    tmp163 = 0
    tmpqqm = 0
    pgnum = 1

    mix_list = []
    mix_page = {}
 
    while max(tmp163, tmpqqm) < max_len:
        mix_page[f'page{pgnum}'] = '────网易云────'
        
        for j in range(step):
            if tmp163 < len(netease):
                srlnum += 1
                mix_list.append(netease[tmp163])
                mix_page[f'page{pgnum}'] += f'\n{str(srlnum).rjust(2, "0")}. {netease[tmp163]["artists"]} - {netease[tmp163]["name"]}'
                tmp163 += 1
            else:
                if j == 0:
                    mix_page[f'page{pgnum}'] += '\n没有更多了'
                break
        mix_page[f'page{pgnum}'] += '\n────QQ音乐────'
        for j in range(step):
            if tmpqqm < len(qqmusic):
                srlnum += 1
                mix_list.append(qqmusic[tmpqqm])
                mix_page[f'page{pgnum}'] += f'\n{str(srlnum).rjust(2, "0")}. {qqmusic[tmpqqm]["artists"]} - {qqmusic[tmpqqm]["name"]}'
                tmpqqm += 1
            else:
                if j == 0:
                    mix_page[f'page{pgnum}'] += '\n没有更多了'
                break
        pgnum += 1

    return mix_list, mix_page


def filter_noarg(bot: Bot, event: MessageEvent, state: T_State):
    """过滤掉“我想听”但是没有参数的情况"""
    if event.raw_message != '我想听'.strip():
        return True


# 命令部分
music = on_command('点歌',
                    aliases={'搜歌', '我想听', '来首',
                            '网易云','搜网易云', '网易云点歌', '网易云搜歌',
                            'QQ音乐', '搜QQ音乐', 'QQ音乐点歌','QQ音乐搜歌',
                            '咪咕', '搜咪咕', '咪咕点歌', '咪咕搜歌'},
                    rule=sv_sw(plugin_name, plugin_usage)&filter_noarg,
                    priority=2)
limiter = FuncLimiter('点歌', cd_rel=120)


@music.handle()
@limiter.limit_verify(cding='稍等一下，音乐冷却还剩{left_time}秒')
async def recieve_cmd(bot: Bot, event: MessageEvent, state: T_State):
    state['trigger'] = event.raw_message # 检测搜索的指定音乐源还是混合列表
    kwd = event.message.extract_plain_text().strip()
    if kwd:
        state['kwd'] = kwd


@music.got("kwd", prompt='你想听什么歌呢？')
async def parse_func(bot: Bot, event: MessageEvent, state: T_State):
    kwd = state['kwd'] if "kwd" in state else event.message.extract_plain_text().strip()
    if kwd in CANCEL_EXPRESSION:
        await music.finish('好吧，那就不听了')
    trigger = state['trigger']
    # 不同的搜索类型生成对应app的列表，脑抽搞乱了
    if trigger.find('网易云') != -1:
        music_list = await search_163(kwd, result_num=15)
        music_page = create_str_page(create_music_page(music_list))
        for page in music_page:
            music_page[page] = '────网易云────' + music_page[page]
    elif trigger.find('QQ音乐') != -1:
        music_list = await search_qm(kwd, result_num=15)
        music_page = create_str_page(create_music_page(music_list))
        for page in music_page:
            music_page[page] = '─────QQ音乐────' + music_page[page]
    elif trigger.find('咪咕') != -1:
        music_list = await search_migu(kwd, result_num=15)
        music_page = create_str_page(create_music_page(music_list))
        for page in music_page:
            music_page[page] = '────咪咕音乐────' + music_page[page]
    # 为防止列表过长就不把咪咕加进混合列表了
    else:
        netease_list = await search_163(kwd, result_num=15)
        qqmusic_list = await search_qm(kwd, result_num=15)
        music_list, music_page = mix_song_list(netease_list, qqmusic_list)

    if music_list:
        state['music_list'] = music_list
        state['music_page'] = music_page
        state['pgbar'] = PagingBar(len(music_page))
        state['crtpg'] = 1
        
        base_list = '{main_list}\n────────────\n{pgbar}'    #只有标题栏、歌曲和分页栏的基本列表
        total_list = "♪搜索到以下歌曲♫\n" + base_list + '\n输入"下一页"翻页查看列表，输入[序号]播放，任何时间输入"退出"结束当前会话'  #第一次展示的列表
        state["error_time"] = 0 #错误次数，连续输入错误操作一定次数后会强制结束对话
        await music.send(reply_header(event, total_list.format(main_list=music_page[f'page{state["crtpg"]}'], pgbar=state['pgbar'].bar)))
    else:
        await music.finish(reply_header(event, '没搜到相关的歌曲呢~试试换个搜索方式？'))


@music.receive()
@limiter.inventory()
async def operate_list(bot: Bot, event: MessageEvent, state: T_State):
    music_list = state['music_list'] 
    music_page = state['music_page']
    turning_page = '{main_list}\n────────────\n{pgbar}' + '\n输入"上一页""下一页"翻页查看列表，输入[序号]播放'  #在翻页时展示的列表

    operation = event.message.extract_plain_text().strip()

    if operation in CANCEL_EXPRESSION:
        await music.finish('已结束当前会话')

    if operation == '上一页':
        if state['crtpg'] == 1:
            await music.reject('当前已经是首页了哦~')
        else:
            state['crtpg'] -= 1
            state['pgbar'].pgup()
            await music.reject(turning_page.format(main_list=music_page[f'page{state["crtpg"]}'], pgbar=state['pgbar'].bar))

    if operation == '下一页':
        if state['crtpg'] == len(music_page):
            await music.reject('已经是最后页了~')
        else:
            state['crtpg'] += 1
            state['pgbar'].pgdn()
            await music.reject(turning_page.format(main_list=music_page[f'page{state["crtpg"]}'], pgbar=state['pgbar'].bar))

    try:
        index= cn2an(numrex.search(operation).group(1), 'smart')
    except:
        state['error_time'] += 1
        if state['error_time'] < 4:
            await music.reject('请发送正确的格式，如"第一首"、"第1首"或仅仅输入序号"1"等带有数字提示的语句\n若要进行其他对话请先发送[退出]结束本次点歌')
        else:
            await music.finish('输入错误次数太多了，请重新开启本对话吧~')

    if index > 0 and index <= len(music_list):
        music_ = music_list[index-1]
        if music_['type'] == '163':
            msc = MessageSegment.music('163', music_['id'])
        elif music_['type'] == 'custom':
            msc = MessageSegment(type='music', data=music_)
        else:
            msc = MessageSegment.music('qq', music_['id'])
            #     data={
            #         'id': music_['id'],
            #         'type': 'qq',
            #         'content': music_['artists']
            #     }
            # )
        try:
            await music.send(msc)
            return 'completed'  # 点歌成功
        except ActionFailed as e:
            await music.finish('好像歌曲坏了呢')
            logger.error("%s - %s 发送失败"%(music['type'], music['id']))
    else:
        await music.reject(f'序号{index}不在列表中呢~')