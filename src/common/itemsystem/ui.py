from pathlib import Path
import imageio
from PIL import Image
from ..easy_setting import RESPATH


respath = Path(RESPATH)
item_icon_folder = respath/'ui'/'icon'/'item'
sc_icon_folder = respath/'ui'/'icon'/'spell_card'

# item_n图标框
icon_frame_n= Image.fromarray(imageio.imread(item_icon_folder/'frame_n.png'))

# 物品图标丢失
icon_missing = Image.fromarray(imageio.imread(item_icon_folder/'missing.png'))

# 鱼竿图标
icon_fishing_rod = Image.fromarray(imageio.imread(item_icon_folder/'fishing-rod.png'))