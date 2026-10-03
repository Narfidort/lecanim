"""lecanim: ノートの定義・定理・証明を Manim + VOICEVOX で解説動画にする制作基盤.

    from lecanim import *                  # manim・色/文字部品・配置・LectureScene（コア）
    from lecanim.domains.graph import *    # 分野の部品（例: グラフ理論）
"""

import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)  # pydub (manim の依存) の古い正規表現の警告

from manim import *  # noqa: F401,F403,E402

from .style import *  # noqa: F401,F403,E402
from .layout import *  # noqa: F401,F403,E402
from .layout import Box, fit, layout_bipartite, layout_circle, layout_groups, layout_line  # noqa: F401,E402
from .units import LiveGroup, mark_overlay  # noqa: F401,E402
from .scene import *  # noqa: F401,F403,E402
from .scene import VOICE_ON, LectureScene  # noqa: F401,E402

# manim 自身の Graph / DiGraph は lecanim.domains.graph と名前がぶつかるので出さない
# （必要なら `import manim; manim.Graph`）．style / scene の star import 経由でも入るので最後に消す
for _n in ("Graph", "DiGraph"):
    globals().pop(_n, None)
del _n
