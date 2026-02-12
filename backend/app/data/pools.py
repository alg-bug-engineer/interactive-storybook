"""故事主题、角色、场景池 - 供随机组合生成故事。"""
import random
from typing import Dict

from app.models.story import Character, Setting


THEME_POOL = [
    {"theme": "勇气冒险", "keywords": "勇敢、探索未知、克服恐惧", "plot_seed": "主角踏上一段意外的冒险旅程"},
    {"theme": "友谊互助", "keywords": "交朋友、互相帮助、理解差异", "plot_seed": "主角遇到一个看起来很不同的新朋友"},
    {"theme": "智慧解谜", "keywords": "动脑思考、解决难题、好奇心", "plot_seed": "主角发现了一个需要智慧才能解开的谜题"},
    {"theme": "善良分享", "keywords": "帮助他人、分享快乐、同理心", "plot_seed": "主角遇到了需要帮助的伙伴"},
    {"theme": "成长蜕变", "keywords": "学会新技能、相信自己、坚持不懈", "plot_seed": "主角想要学会一件很难的事情"},
    {"theme": "奇幻探秘", "keywords": "魔法世界、神奇生物、奇妙发现", "plot_seed": "主角偶然进入了一个神奇的世界"},
    {"theme": "守护自然", "keywords": "环保、守护家园、珍惜生命", "plot_seed": "主角发现熟悉的森林正悄悄发生变化"},
    {"theme": "团队协作", "keywords": "分工合作、互补优势、共同目标", "plot_seed": "主角和伙伴必须一起完成一个大任务"},
    {"theme": "诚实担当", "keywords": "诚实、承担后果、修正错误", "plot_seed": "主角不小心闯了祸，必须做出选择"},
    {"theme": "时间旅行", "keywords": "过去未来、历史想象、时空冒险", "plot_seed": "主角捡到一只会倒计时的口袋怀表"},
    {"theme": "发明创造", "keywords": "动手实践、创新、失败再尝试", "plot_seed": "主角想做一台能帮助大家的小机器"},
    {"theme": "文化节日", "keywords": "传统节日、仪式感、家人陪伴", "plot_seed": "主角要准备一场特别的节日庆典"},
    {"theme": "音乐律动", "keywords": "节奏、倾听、表达情绪", "plot_seed": "主角发现了只有夜晚才会响起的旋律"},
    {"theme": "美食温暖", "keywords": "分享食物、劳动成果、温暖社区", "plot_seed": "主角决定为小镇做一份惊喜大餐"},
    {"theme": "海洋守护", "keywords": "海洋生态、责任、行动", "plot_seed": "主角在海边发现一张被冲上岸的求助图"},
    {"theme": "星际探索", "keywords": "宇宙想象、合作、未知文明", "plot_seed": "主角收到一封来自远方星球的邀请函"},
    {"theme": "情绪管理", "keywords": "认识情绪、自我调节、理解他人", "plot_seed": "主角的一颗心情小灯忽明忽暗"},
    {"theme": "规则与自由", "keywords": "规则意识、自律、尊重边界", "plot_seed": "主角来到一个什么都能做却总出乱子的地方"},
    {"theme": "亲情陪伴", "keywords": "家人支持、爱与理解、彼此守护", "plot_seed": "主角和家人一起完成一件重要的小事"},
    {"theme": "社区温情", "keywords": "邻里互助、善意循环、社会责任", "plot_seed": "主角决定帮助街区实现一个共同心愿"},
]


SCENE_POOL = [
    "开场是一场刚下过雨的清晨，空气里都是泥土和花香",
    "夜空突然亮起一条会说话的光带，引来全城围观",
    "主角在集市角落发现一扇只在黄昏出现的小门",
    "风把一封没有署名的信吹到主角脚边",
    "小镇停电后，只有远处灯塔还在发出节奏光",
    "山谷里传来断断续续的钟声，却看不见钟楼",
    "湖面像镜子一样平静，映出平时看不到的图案",
    "庆典前一天，广场中心的装置忽然失灵",
    "晨雾中出现一条发光石阶，尽头通向未知之地",
    "主角在旧仓库里听见一段熟悉又陌生的歌",
    "一场大雪后，村口多出一串神秘脚印",
    "地图上的空白区域突然出现了新的标记",
    "潮水退去后，海岸露出一座半埋的拱门",
    "风铃同时响起，像在提示某个隐藏密码",
    "图书馆闭馆后，书页上浮现会移动的星点",
]


TASK_POOL = [
    "在天黑前找到失落的钥匙并打开通道",
    "帮助三位不同性格的伙伴达成和解",
    "修好镇上的核心装置，让大家恢复正常生活",
    "把重要物资送到山顶观测站",
    "在迷雾消散前完成古老试炼",
    "为即将到来的节日准备一场惊喜演出",
    "解开地图上的四个线索并找到终点",
    "带领伙伴穿越复杂地形安全返回营地",
    "说服固执的守门人放行并说明理由",
    "在有限时间内搭建临时避风港",
    "找到失联伙伴并查明失踪原因",
    "用有限材料造出能跨越峡谷的小工具",
    "修复被打乱顺序的星图，定位下一站",
    "完成一场需要默契配合的团队挑战",
    "在不伤害环境的前提下解决资源短缺",
]


PLOT_TWIST_POOL = [
    "原来“反派”只是误会了主角的意图",
    "关键道具并不在终点，而在出发点附近",
    "主角最害怕的东西恰好是破解难题的关键",
    "看似失败的尝试其实悄悄打开了新路径",
    "一直沉默的配角拥有决定性线索",
    "真正的挑战不是速度，而是彼此信任",
    "主角必须先帮助别人，才能完成自己的任务",
    "地图上的标记会随主角选择实时变化",
    "倒计时并非灾难，而是一次珍贵机会",
    "答案藏在一首童谣的节奏里",
    "终点会移动，只有合作才能看到方向",
    "守护者考验的不是力量而是诚实",
    "大家寻找的宝物其实是修复关系的方法",
    "最不起眼的物品成了最后的关键机关",
    "主角发现自己曾经的错误才是谜题源头",
]


LOCATION_HINT_POOL = [
    "雾松峡谷", "风铃港", "银月台地", "彩陶街区", "潮汐洞庭",
    "晨光驿站", "萤火坡", "蓝莓平原", "星轨塔", "白鹭湿地",
    "云端菜园", "回声峡", "琥珀沙湾", "玻璃温室", "望潮灯塔",
]


CHARACTER_POOL = [
    Character(name="小白", species="兔子", trait="好奇心旺盛，胆子小但很勇敢",
              appearance="a small fluffy white rabbit with big blue eyes and a red scarf"),
    Character(name="团团", species="小熊猫", trait="憨厚可爱，力气大心地善良",
              appearance="a chubby red panda with round face and fluffy striped tail"),
    Character(name="星星", species="小狐狸", trait="聪明机灵，有点调皮但很忠诚",
              appearance="a small orange fox with sparkling golden eyes and a starry collar"),
    Character(name="泡泡", species="小龙", trait="害羞内向，会吐彩色泡泡",
              appearance="a tiny pastel blue baby dragon with rainbow bubbles around"),
    Character(name="朵朵", species="小猫", trait="优雅温柔，喜欢唱歌跳舞",
              appearance="a graceful calico kitten with a flower crown and pink bow"),
    Character(name="闪闪", species="萤火虫", trait="活泼开朗，喜欢照亮别人",
              appearance="a cute glowing firefly with tiny wings and warm golden light"),
    Character(name="波波", species="小企鹅", trait="冒失但热心，经常摔跤",
              appearance="a clumsy baby penguin with a wobbly walk and cheerful expression"),
    Character(name="叮当", species="小鹿", trait="优美灵动，跑得最快",
              appearance="a young deer with silver spots and graceful antlers with bells"),
    Character(name="米粒", species="小仓鼠", trait="善于收纳，总能找到应急物品",
              appearance="a tiny hamster with a patchwork satchel and bright eyes"),
    Character(name="阿岩", species="小山羊", trait="稳重可靠，擅长攀爬陡坡",
              appearance="a young mountain goat with cream fur and sturdy little horns"),
    Character(name="悠悠", species="海獭", trait="乐观爱笑，擅长水下侦查",
              appearance="a playful sea otter with a shell necklace and glossy brown fur"),
    Character(name="栗子", species="刺猬", trait="谨慎细心，观察力超强",
              appearance="a round hedgehog with chestnut quills and a tiny explorer cape"),
    Character(name="铃铛", species="小鹦鹉", trait="记忆力超群，爱学各种声音",
              appearance="a green parrot chick with yellow cheeks and a silver ankle bell"),
    Character(name="阿墨", species="章鱼", trait="多才多艺，临场应变很快",
              appearance="a baby octopus with violet skin and a painter's beret"),
    Character(name="糖糖", species="蜜蜂", trait="勤快认真，时间观念很强",
              appearance="a tiny bee with striped scarf and transparent golden wings"),
    Character(name="阿跃", species="青蛙", trait="幽默健谈，擅长活跃气氛",
              appearance="a bright green frog with a polka-dot raincoat and wide smile"),
    Character(name="圆圆", species="猫头鹰", trait="知识丰富，夜里特别精神",
              appearance="a fluffy owlet with amber eyes and a little scholar hat"),
    Character(name="咚咚", species="小象", trait="温和有耐心，记忆力很好",
              appearance="a baby elephant with soft gray skin and a blue backpack"),
]


SETTING_POOL = [
    Setting(location="魔法森林", time="春天的早晨", weather="阳光明媚",
            visual_description="enchanted forest with giant colorful mushrooms and glowing flowers"),
    Setting(location="云朵王国", time="金色的黄昏", weather="霞光满天",
            visual_description="kingdom above clouds with rainbow bridges and crystal castles"),
    Setting(location="海底花园", time="阳光穿透海面的午后", weather="海水清澈",
            visual_description="underwater garden with coral reef, colorful fish and seashell houses"),
    Setting(location="星光小镇", time="满天星星的夜晚", weather="星光闪烁",
            visual_description="tiny magical town under starry sky with lantern-lit cobblestone streets"),
    Setting(location="彩虹山谷", time="雨后初晴", weather="彩虹挂天",
            visual_description="valley with waterfall creating rainbows, flowers in every color"),
    Setting(location="雪花村庄", time="冬天的黎明", weather="雪花飘飘",
            visual_description="cozy snowy village with warm glowing windows and northern lights"),
    Setting(location="风铃海岸", time="夏日午后", weather="海风轻拂",
            visual_description="seaside cliffs with wind chimes, white foam waves and blue horizon"),
    Setting(location="镜湖营地", time="清晨薄雾", weather="微凉湿润",
            visual_description="lakeside camp with pine trees, misty water and wooden docks"),
    Setting(location="琥珀沙湾", time="傍晚", weather="暖风晴朗",
            visual_description="golden beach with amber rocks, tide pools and orange sunset"),
    Setting(location="回声峡谷", time="午后", weather="晴空高远",
            visual_description="narrow canyon with layered cliffs and echoing stone corridors"),
    Setting(location="玻璃温室城", time="清晨", weather="温暖湿润",
            visual_description="vast glass greenhouse city with vines, canals and sunlight beams"),
    Setting(location="银月灯塔", time="深夜", weather="海雾弥漫",
            visual_description="ancient lighthouse on dark sea cliffs with rotating silver beacon"),
    Setting(location="云端菜园", time="日出时分", weather="微风轻柔",
            visual_description="floating terraced gardens above clouds with dew and tiny bridges"),
    Setting(location="古树图书馆", time="下午", weather="林间微光",
            visual_description="library built inside giant trees with spiral stairs and hanging lanterns"),
    Setting(location="极地科研站", time="冬夜", weather="极光闪动",
            visual_description="polar station under aurora sky with ice domes and snow trails"),
    Setting(location="蒸汽工坊街", time="黄昏", weather="薄雾朦胧",
            visual_description="steampunk alley with brass pipes, clock towers and soft steam lights"),
    Setting(location="珊瑚集市", time="正午", weather="浪花温柔",
            visual_description="floating market near reefs with colorful tents and shell boats"),
    Setting(location="星轨观测台", time="夜晚", weather="空气清澈",
            visual_description="mountain observatory with rotating telescope and star maps"),
    Setting(location="白鹭湿地", time="清晨", weather="露水晶莹",
            visual_description="wetland boardwalk with reeds, white egrets and mirror-like ponds"),
    Setting(location="纸鸢平原", time="春日下午", weather="和风徐徐",
            visual_description="wide grassland filled with colorful kites, wildflowers and distant hills"),
    Setting(location="火山温泉谷", time="傍晚", weather="温热蒸汽",
            visual_description="volcanic valley with hot springs, red rocks and glowing dusk clouds"),
    Setting(location="月影石桥镇", time="夜幕初降", weather="清爽干燥",
            visual_description="old town of stone bridges and moonlit canals with warm lantern reflections"),
]


def pick_theme() -> Dict[str, str]:
    """
    选择主题并注入更多故事种子，提升随机组合丰富度。
    兼容旧字段：theme / keywords / plot_seed。
    """
    base = random.choice(THEME_POOL).copy()
    base["scene_seed"] = random.choice(SCENE_POOL)
    base["core_task"] = random.choice(TASK_POOL)
    base["plot_twist"] = random.choice(PLOT_TWIST_POOL)
    base["location_hint"] = random.choice(LOCATION_HINT_POOL)
    return base


def pick_character() -> Character:
    return random.choice(CHARACTER_POOL)


def pick_setting() -> Setting:
    return random.choice(SETTING_POOL)


def pick_story_preset() -> Dict[str, object]:
    """一次性返回完整预设组合，便于后续扩展其他服务调用。"""
    return {
        "theme": pick_theme(),
        "character": pick_character(),
        "setting": pick_setting(),
    }
