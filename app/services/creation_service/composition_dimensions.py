"""构图维度枚举集中管理。所有 Prompt 装配层通过 get_dimension_values() 读取。

新增/删除/改名枚举值只需在此文件调整,不需要修改 Prompt 模板与节点拓扑。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Tuple


@dataclass(frozen=True)
class DimensionValue:
    code: str
    display_name: str
    description: str


_MANUAL_ASPECT: List[DimensionValue] = [
    DimensionValue("16:9", "16:9", "横向宽屏,适合横向卧姿/横构图"),
    DimensionValue("4:3",  "4:3",  "横向常规,适合半环境居中构图"),
    DimensionValue("1:1",  "1:1",  "正方形,适合居中坐姿/居中构图"),
    DimensionValue("3:4",  "3:4",  "竖向常规,适合竖向全身"),
    DimensionValue("9:16", "9:16", "竖向宽屏,适合竖向全身/纵深构图"),
]

_EXTRA_AUTO_ASPECT: List[DimensionValue] = [
    DimensionValue("4:5", "4:5", "接近竖向正方形,适合半环境竖构图"),
    DimensionValue("5:4", "5:4", "接近正方形略横,适合居中坐姿"),
    DimensionValue("2:3", "2:3", "竖向偏窄,适合竖向全身"),
    DimensionValue("3:2", "3:2", "横向偏窄,适合横向全身"),
]

VALID_MANUAL_ASPECT_CODES: FrozenSet[str] = frozenset(v.code for v in _MANUAL_ASPECT)
VALID_AUTO_ASPECT_CODES: FrozenSet[str] = frozenset(
    v.code for v in (_MANUAL_ASPECT + _EXTRA_AUTO_ASPECT)
)

_SUBJECT_AREA_MIN: List[DimensionValue] = [
    DimensionValue("0.45", "45%", "较低占比,适合大空间/纵深强调环境"),
    DimensionValue("0.55", "55%", "中等偏低,常用平衡档"),
    DimensionValue("0.65", "65%", "中等偏高,缩略图友好的默认建议档"),
    DimensionValue("0.75", "75%", "高占比,主体强调/角色特写但仍全身可见"),
]

_POSE_FAMILY: List[DimensionValue] = [
    DimensionValue("sitting",    "坐姿",   "坐在椅/沙发/床沿/窗台等平面上"),
    DimensionValue("lying",      "躺姿",   "侧卧/仰卧/俯卧于床/地板/沙发"),
    DimensionValue("kneeling",   "跪姿",   "跪坐/跽坐,双膝着地"),
    DimensionValue("squatting",  "蹲姿",   "蹲下或半蹲,腿脚仍完整可见"),
    DimensionValue("leaning",    "倚靠",   "倚靠墙/沙发靠背/窗框,身体重心倾斜"),
    DimensionValue("cross_leg",  "盘腿坐", "盘腿坐或双腿交叠坐,腿脚自然收拢"),
]

_SHOOTING_ANGLE: List[DimensionValue] = [
    DimensionValue("front",              "正面",       "镜头正对角色正面"),
    DimensionValue("three_quarter",      "3/4 正面",   "镜头 3/4 侧前方"),
    DimensionValue("side",               "侧面",       "镜头完全侧面"),
    DimensionValue("three_quarter_back", "3/4 背面",   "镜头 3/4 后方"),
    DimensionValue("back_glance",        "背面(回眸)", "镜头在角色后方,角色上半身回头朝向镜头、视线接触观者"),
]

_CAMERA_HEIGHT: List[DimensionValue] = [
    DimensionValue("slight_up",   "略仰", "机位略低于视平,轻微仰拍"),
    DimensionValue("eye_level",   "平视", "机位与视平齐"),
    DimensionValue("slight_down", "略俯", "机位略高于视平,轻微俯拍"),
    DimensionValue("high_down",   "大俯", "机位明显高于视平,明显俯拍"),
]

_GAZE_DIRECTION: List[DimensionValue] = [
    DimensionValue("to_camera",         "看镜头",     "视线直接接触观者"),
    DimensionValue("three_quarter_out", "3/4 看出画", "视线朝画面外 3/4 方向"),
    DimensionValue("to_side",           "侧面看",     "视线朝纯侧面"),
    DimensionValue("to_down",           "看下方",     "视线略微下垂"),
    DimensionValue("to_far",            "看远处",     "视线望向远方,焦点在画外"),
]

_REGISTRY: Dict[str, List[DimensionValue]] = {
    "aspect_ratio_manual":            _MANUAL_ASPECT,
    "aspect_ratio_auto_full":         _MANUAL_ASPECT + _EXTRA_AUTO_ASPECT,
    "aspect_ratio_auto_mainstream":   _MANUAL_ASPECT,
    "subject_area_min":               _SUBJECT_AREA_MIN,
    "pose_family":                    _POSE_FAMILY,
    "shooting_angle":                 _SHOOTING_ANGLE,
    "camera_height":                  _CAMERA_HEIGHT,
    "gaze_direction":                 _GAZE_DIRECTION,
}


def get_dimension_values(dimension_code: str) -> List[DimensionValue]:
    if dimension_code not in _REGISTRY:
        raise KeyError(f"unknown dimension_code: {dimension_code!r}")
    return list(_REGISTRY[dimension_code])


_HOME_SETTING_POSE_HINTS: List[Tuple[str, List[str]]] = [
    ("卧室大床",   ["躺姿", "倚靠", "盘腿坐"]),
    ("客厅沙发",   ["倚靠", "坐姿", "躺姿"]),
    ("日式榻榻米", ["跪姿", "盘腿坐", "坐姿"]),
    ("飘窗台",     ["坐姿", "倚靠"]),
    ("书房地毯",   ["盘腿坐", "蹲姿", "跪姿"]),
]


def get_home_setting_pose_hints() -> List[Tuple[str, List[str]]]:
    return [(s, list(poses)) for s, poses in _HOME_SETTING_POSE_HINTS]
