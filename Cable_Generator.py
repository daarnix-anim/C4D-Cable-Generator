"""
=============================================================================
Wire / Cable & Data Stream Generator for Maxon Cinema 4D 2026
=============================================================================
Автор: Antigravity (Google DeepMind)
Назначение: 
1. Создает динамический кабель между двумя объектами (Точка А -> Точка Б)
   с полным управлением толщиной и изгибом/провисанием во вьюпорте в реальном времени.
2. Создает эффект обмена данными (бегущие по проводу неоновые сферы MoGraph):
   - движение в обоих направлениях (А -> Б и Б -> А);
   - настройка размера сфер, скорости и дистанции между ними;
   - добавление произвольного количества независимых потоков данных.
3. Единый центр управления: ВСЕ пользовательские параметры (User Data) 
   провода и каждого потока вынесены на самый верхний уровень рига (Wire_Rig)!
   Никакой необходимости кликать по вложенным объектам в Object Manager!
4. Встроенная система пресетов: выбор готовых настроек, сохранение собственных
   пресетов на диск, быстрое применение к выделенному проводу в 1 клик.
5. Инструмент мгновенного обновления тега решения на существующих в сцене ригах.
=============================================================================
"""

import c4d
from c4d import gui
import json
import os

# Идентификатор диалога
DLG_ID = 1062002

# Идентификаторы элементов интерфейса
IDC_GRP_MAIN         = 1000
IDC_GRP_PRESETS      = 1005
IDC_PRESET_LIST      = 1006
IDC_PRESET_NAME      = 1007
IDC_BTN_SAVE_PRESET  = 1008
IDC_BTN_DEL_PRESET   = 1009

IDC_GRP_SELECTION    = 1010
IDC_TXT_SELECTION    = 1011

IDC_GRP_SETTINGS     = 1020
IDC_RADIUS           = 1021
IDC_SAG              = 1022
IDC_AXIS             = 1023
IDC_SUBDIVS          = 1024
IDC_PROFILE_SEG      = 1025

# Секция потоков данных
IDC_GRP_STREAMS      = 1040
IDC_ENABLE_STREAMS   = 1041
IDC_STREAM_PRESET    = 1042
IDC_S1_SIZE          = 1043
IDC_S1_DIST          = 1044
IDC_S1_SPEED         = 1045
IDC_S2_SIZE          = 1046
IDC_S2_DIST          = 1047
IDC_S2_SPEED         = 1048

# Действия и кнопки
IDC_GRP_ACTIONS      = 1030
IDC_BTN_CREATE       = 1031
IDC_BTN_ADD_STREAM   = 1032
IDC_BTN_APPLY_TO_RIG = 1034
IDC_BTN_FIX_RIG      = 1035
IDC_TXT_STATUS       = 1033

# Палитра неоновых цветов для потоков данных
STREAM_COLORS = [
    ("Cyan",    c4d.Vector(0.0, 0.85, 1.0)),     # Голубой неон (А -> Б)
    ("Orange",  c4d.Vector(1.0, 0.45, 0.05)),    # Оранжевый неон (Б -> А)
    ("Magenta", c4d.Vector(0.95, 0.1, 0.8)),     # Розовый/Пурпурный неон
    ("Green",   c4d.Vector(0.1, 1.0, 0.35)),     # Салатовый неон
    ("Yellow",  c4d.Vector(1.0, 0.9, 0.05)),     # Электрический желтый
    ("Blue",    c4d.Vector(0.2, 0.4, 1.0))       # Ультрамариновый синий
]

# Встроенные пресеты по умолчанию
DEFAULT_PRESETS = {
    "Стандартный кабель (2 потока)": {
        "wire_radius": 2.0, "sag": 50.0, "axis_mode": 0, "subdivs": 25, "profile_seg": 8,
        "enable_streams": True, "stream_preset": 2,
        "s1_size": 1.5, "s1_dist": 30.0, "s1_speed": 35.0,
        "s2_size": 1.0, "s2_dist": 45.0, "s2_speed": -25.0
    },
    "Оптоволокно (Быстрый обмен)": {
        "wire_radius": 1.0, "sag": 25.0, "axis_mode": 0, "subdivs": 30, "profile_seg": 8,
        "enable_streams": True, "stream_preset": 3,
        "s1_size": 0.8, "s1_dist": 15.0, "s1_speed": 80.0,
        "s2_size": 0.8, "s2_dist": 15.0, "s2_speed": -80.0
    },
    "Тяжелый провисающий кабель": {
        "wire_radius": 5.0, "sag": 140.0, "axis_mode": 0, "subdivs": 35, "profile_seg": 12,
        "enable_streams": False, "stream_preset": 1,
        "s1_size": 2.0, "s1_dist": 50.0, "s1_speed": 20.0,
        "s2_size": 1.5, "s2_dist": 50.0, "s2_speed": -20.0
    },
    "Киберпанк магистраль (4 канала)": {
        "wire_radius": 3.0, "sag": 40.0, "axis_mode": 0, "subdivs": 30, "profile_seg": 10,
        "enable_streams": True, "stream_preset": 4,
        "s1_size": 1.8, "s1_dist": 35.0, "s1_speed": 45.0,
        "s2_size": 1.2, "s2_dist": 40.0, "s2_speed": -35.0
    },
    "Прямой натянутый провод": {
        "wire_radius": 1.5, "sag": 0.0, "axis_mode": 0, "subdivs": 15, "profile_seg": 8,
        "enable_streams": True, "stream_preset": 1,
        "s1_size": 1.2, "s1_dist": 25.0, "s1_speed": 40.0,
        "s2_size": 1.0, "s2_dist": 30.0, "s2_speed": -30.0
    }
}


def get_preset_filepath():
    """Определяет путь для сохранения файла пресетов."""
    script_dir = os.path.dirname(__file__)
    p1 = os.path.join(script_dir, "cable_presets.json")
    try:
        if os.path.exists(p1) or os.access(script_dir, os.W_OK):
            return p1
    except Exception:
        pass
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, "Maxon", "cable_presets.json")


def load_presets_from_disk():
    """Загружает словарь пресетов из файла JSON или возвращает дефолтные."""
    path = get_preset_filepath()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and len(data) > 0:
                    return data
        except Exception:
            pass
    return dict(DEFAULT_PRESETS)


def save_presets_to_disk(presets_dict):
    """Сохраняет словарь пресетов в файл JSON."""
    path = get_preset_filepath()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(presets_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Ошибка сохранения пресетов: {e}")
        return False


# =============================================================================
# Код главного мастер-тега решения (сидит на корневом объекте Wire_Rig)
# =============================================================================
TAG_MASTER_SOLVER = '''# Wire Master Solver - Cinema 4D 2026
import c4d

def get_sag_direction(delta, axis_mode):
    dist = delta.GetLength()
    if axis_mode == 0:  # Гравитация (-Y)
        if dist > 0.001 and abs(delta.y / dist) > 0.98:
            return c4d.Vector(1, 0, 0)
        return c4d.Vector(0, -1, 0)
    elif axis_mode == 1:  # Вверх (+Y)
        if dist > 0.001 and abs(delta.y / dist) > 0.98:
            return c4d.Vector(-1, 0, 0)
        return c4d.Vector(0, 1, 0)
    elif axis_mode == 2:  # Перпендикулярно вниз
        down = c4d.Vector(0, -1, 0)
        if dist > 0.001:
            u = delta.GetNormalized()
            perp = down - (down.Dot(u)) * u
            if perp.GetLength() > 0.05:
                return perp.GetNormalized()
        return c4d.Vector(1, 0, 0)
    elif axis_mode == 3:  # Ось X
        return c4d.Vector(1, 0, 0)
    elif axis_mode == 4:  # Ось Z
        return c4d.Vector(0, 0, 1)
    return c4d.Vector(0, -1, 0)

def read_rig_user_data(rig):
    """Считывает все параметры из User Data объекта Wire_Rig."""
    data = {
        "targets": [],
        "target_a": None,
        "target_b": None,
        "radius": None,
        "sag": None,
        "axis": None,
        "subdivs": None,
        "streams": {}  # s_num -> dict
    }

    if not rig:
        return data

    doc = rig.GetDocument() or c4d.documents.GetActiveDocument()

    # 1. Сканирование UserData контейнера
    try:
        container = rig.GetUserDataContainer()
    except Exception:
        container = None

    if container:
        for desc_id, bc in container:
            try:
                if not bc:
                    continue
                try:
                    if desc_id[-1].dtype == c4d.DTYPE_GROUP:
                        continue
                except Exception:
                    pass

                val = None
                try:
                    val = rig[desc_id]
                except Exception:
                    pass
                if val is None:
                    try:
                        param_id = desc_id[1].id
                        val = rig[c4d.ID_USERDATA, param_id]
                    except Exception:
                        pass
                if val is None:
                    continue

                # Извлечение списка опорных объектов из InExclude списка
                if isinstance(val, c4d.InExcludeData):
                    inex_objs = []
                    for i in range(val.GetObjectCount()):
                        obj = val.ObjectFromIndex(doc, i)
                        if obj and obj.IsAlive():
                            try:
                                flags = val.GetFlags(i)
                                if flags is not None and (flags & 1) == 0:
                                    continue
                            except Exception:
                                pass
                            inex_objs.append(obj)
                    if len(inex_objs) >= 2:
                        data["targets"] = inex_objs
                    continue

                if hasattr(val, "GetLink"):
                    val = val.GetLink(doc)

                name = bc[c4d.DESC_NAME] or bc[c4d.DESC_SHORT_NAME] or ""
                name_l = str(name).lower()

                if "поток" in name_l or "stream" in name_l or "канал" in name_l:
                    for s_num in range(1, 20):
                        if (f"поток {s_num}" in name_l or f"stream {s_num}" in name_l or 
                            f"канал {s_num}" in name_l or f"поток_{s_num}" in name_l):
                            if s_num not in data["streams"]:
                                data["streams"][s_num] = {}
                            if "включ" in name_l or "enable" in name_l:
                                data["streams"][s_num]["enable"] = bool(val)
                            elif "размер" in name_l or "сфер" in name_l or "радиус" in name_l:
                                data["streams"][s_num]["radius"] = float(val)
                            elif "скорост" in name_l or "speed" in name_l:
                                data["streams"][s_num]["speed"] = float(val)
                            elif "дистанц" in name_l or "шаг" in name_l or "dist" in name_l:
                                data["streams"][s_num]["dist"] = float(val)
                            elif "смещен" in name_l or "offset" in name_l:
                                data["streams"][s_num]["offset"] = float(val)
                            break
                else:
                    if any(k in name_l for k in ["объект а", "точка а", "старт"]):
                        data["target_a"] = val
                    elif any(k in name_l for k in ["объект б", "точка б", "конец"]):
                        data["target_b"] = val
                    elif "толщин" in name_l or ("радиус" in name_l and "сфер" not in name_l):
                        data["radius"] = float(val)
                    elif "направлен" in name_l or "ось" in name_l:
                        data["axis"] = int(val)
                    elif "провисан" in name_l or "изгиб" in name_l or "sag" in name_l:
                        data["sag"] = float(val)
                    elif "сегмент" in name_l or "детализац" in name_l:
                        data["subdivs"] = int(val)
            except Exception:
                continue

    # Фолбэк для объектов А и Б, если InExclude не заполнен
    if len(data["targets"]) == 0:
        if data["target_a"] is None:
            try:
                ta = rig[c4d.ID_USERDATA, 2]
                if hasattr(ta, "GetLink"): ta = ta.GetLink(doc)
                if ta: data["target_a"] = ta
            except Exception: pass

        if data["target_b"] is None:
            try:
                tb = rig[c4d.ID_USERDATA, 3]
                if hasattr(tb, "GetLink"): tb = tb.GetLink(doc)
                if tb: data["target_b"] = tb
            except Exception: pass

        if data["target_a"] and data["target_b"]:
            data["targets"] = [data["target_a"], data["target_b"]]

    if data["radius"] is None:
        try:
            r = rig[c4d.ID_USERDATA, 4]
            if r is not None: data["radius"] = float(r)
        except Exception: pass

    if data["sag"] is None:
        try:
            s = rig[c4d.ID_USERDATA, 5]
            if s is not None: data["sag"] = float(s)
        except Exception: pass

    if data["axis"] is None:
        try:
            a = rig[c4d.ID_USERDATA, 6]
            if a is not None: data["axis"] = int(a)
        except Exception: pass

    if data["subdivs"] is None:
        try:
            sub = rig[c4d.ID_USERDATA, 7]
            if sub is not None: data["subdivs"] = int(sub)
        except Exception: pass

    return data

def main():
    host = op.GetObject()
    if not host:
        return

    rig = None
    sweep = None
    streams_group = None

    if host.CheckType(c4d.Osweep):
        sweep = host
        parent = host.GetUp()
        if parent and "Wire_Rig" in parent.GetName():
            rig = parent
        else:
            rig = host
    else:
        rig = host
        for child in rig.GetChildren():
            if child.CheckType(c4d.Osweep):
                sweep = child
            elif child.GetName() == "Data_Streams":
                streams_group = child

    if not sweep:
        return

    if not streams_group and rig:
        for child in rig.GetChildren():
            if child.GetName() == "Data_Streams":
                streams_group = child
                break

    # Отслеживание изменений данных объекта для графа зависимостей C4D
    try:
        _ = rig.GetDirty(c4d.DIRTYFLAGS_DATA)
        _ = sweep.GetDirty(c4d.DIRTYFLAGS_DATA)
    except Exception:
        pass

    ud = read_rig_user_data(rig)
    if not ud["targets"] and sweep != rig:
        ud_sw = read_rig_user_data(sweep)
        for k, v in ud_sw.items():
            if k == "streams":
                if not ud["streams"]:
                    ud["streams"] = v
            elif k == "targets":
                if not ud["targets"]:
                    ud["targets"] = v
            elif ud[k] is None:
                ud[k] = v

    targets  = ud["targets"]
    radius   = ud["radius"] if ud["radius"] is not None else 2.0
    sag      = ud["sag"] if ud["sag"] is not None else 50.0
    axis     = ud["axis"] if ud["axis"] is not None else 0
    subdivs  = ud["subdivs"] if ud["subdivs"] is not None else 25

    profile = None
    path = None
    for child in sweep.GetChildren():
        if child.CheckType(c4d.Osplinecircle) or "profile" in child.GetName().lower():
            profile = child
        elif child.CheckType(c4d.Ospline) or "path" in child.GetName().lower():
            path = child
    if not profile:
        profile = sweep.GetDown()
    if not path and profile:
        path = profile.GetNext()

    if not profile or not path:
        return

    # 1. ОБНОВЛЕНИЕ ТОЛЩИНЫ (ПРОФИЛЯ)
    radius_changed = False
    if profile.CheckType(c4d.Osplinecircle) and radius is not None and radius > 0:
        curr_rad = profile[c4d.PRIM_CIRCLE_RADIUS]
        if abs(curr_rad - radius) > 0.0001:
            profile[c4d.PRIM_CIRCLE_RADIUS] = radius
            profile.SetDirty(c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_CACHE)
            profile.Message(c4d.MSG_CHANGE)
            profile.Message(c4d.MSG_UPDATE)
            radius_changed = True

    # 2. ОБНОВЛЕНИЕ КРИВИЗНЫ И ТОЧЕК СПЛАЙНА ЧЕРЕЗ ВСЕ ОПОРНЫЕ ОБЪЕКТЫ
    pts_changed = False
    if len(targets) >= 2:
        try:
            target_positions = []
            for t in targets:
                if t and t.IsAlive():
                    _ = t.GetDirty(c4d.DIRTYFLAGS_MATRIX)
                    target_positions.append(t.GetMg().off)

            if len(target_positions) >= 2:
                pts_per_seg = max(4, int(subdivs)) if subdivs else 25
                sag_val = sag if sag is not None else 0.0
                axis_val = axis if axis is not None else 0
                inv_mg = ~path.GetMg()

                new_pts = []
                num_segs = len(target_positions) - 1
                for seg_idx in range(num_segs):
                    pos_a = target_positions[seg_idx]
                    pos_b = target_positions[seg_idx + 1]
                    delta = pos_b - pos_a
                    sag_dir = get_sag_direction(delta, axis_val)

                    end_k = pts_per_seg if (seg_idx == num_segs - 1) else (pts_per_seg - 1)
                    for k in range(end_k + 1):
                        t = float(k) / float(pts_per_seg)
                        droop = 4.0 * t * (1.0 - t)
                        pt_world = pos_a + delta * t + sag_dir * (sag_val * droop)
                        pt_local = inv_mg * pt_world
                        new_pts.append(pt_local)

                num_pts = len(new_pts)
                if path.GetPointCount() != num_pts:
                    path.ResizeObject(num_pts)
                    pts_changed = True

                current_pts = path.GetAllPoints()
                if not pts_changed:
                    if len(current_pts) != num_pts:
                        pts_changed = True
                    else:
                        diff = sum((p1 - p2).GetLength() for p1, p2 in zip(current_pts, new_pts))
                        if diff > 0.001:
                            pts_changed = True

                if pts_changed:
                    path.SetAllPoints(new_pts)
                    path.SetDirty(c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_CACHE)
                    path.Message(c4d.MSG_POINTS_CHANGED)
                    path.Message(c4d.MSG_UPDATE)
        except Exception:
            pass

    # 3. ИНВАЛИДАЦИЯ КЭША SWEEP
    if pts_changed or radius_changed:
        sweep.SetDirty(c4d.DIRTYFLAGS_CACHE | c4d.DIRTYFLAGS_DATA)
        sweep.Message(c4d.MSG_UPDATE)
        c4d.EventAdd()

    # 4. ОБНОВЛЕНИЕ ВСЕХ ПОТОКОВ ДАННЫХ (КЛОНЕРОВ И СФЕР)
    if streams_group:
        cloners = streams_group.GetChildren()
        for cloner in cloners:
            if not cloner.CheckType(c4d.Omgcloner):
                continue

            cloner_name = cloner.GetName()
            s_num = None
            for n in range(1, 20):
                if f"Stream_{n}" in cloner_name:
                    s_num = n
                    break

            if not s_num or s_num not in ud["streams"]:
                continue

            s_data = ud["streams"][s_num]
            cloner_changed = False

            enable = s_data.get("enable", True)
            if enable is not None:
                if cloner[c4d.ID_BASEOBJECT_GENERATOR_FLAG] != enable:
                    cloner[c4d.ID_BASEOBJECT_GENERATOR_FLAG] = enable
                    cloner.SetEditorMode(c4d.MODE_ON if enable else c4d.MODE_OFF)
                    cloner.SetRenderMode(c4d.MODE_ON if enable else c4d.MODE_OFF)
                    cloner_changed = True

            if not enable:
                if cloner_changed:
                    cloner.SetDirty(c4d.DIRTYFLAGS_CACHE | c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_CHILDREN)
                    cloner.Message(c4d.MSG_UPDATE)
                    c4d.EventAdd()
                continue

            # Гарантируем режим Render Instance (не Multi-Instance, блокирующий обновление формы)
            if cloner[c4d.MGCLONER_VOLUMEINSTANCES_MODE] != c4d.MGCLONER_VOLUMEINSTANCES_MODE_RENDERINSTANCE:
                cloner[c4d.MGCLONER_VOLUMEINSTANCES_MODE] = c4d.MGCLONER_VOLUMEINSTANCES_MODE_RENDERINSTANCE
                cloner_changed = True

            # Управление размером сфер: радиус примитива Osphere
            sphere = cloner.GetDown()
            s_rad = s_data.get("radius")
            if sphere and s_rad is not None and s_rad > 0:
                if abs(sphere[c4d.PRIM_SPHERE_RAD] - s_rad) > 0.001:
                    sphere[c4d.PRIM_SPHERE_RAD] = s_rad
                    sphere.SetDirty(c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_CACHE)
                    sphere.Message(c4d.MSG_CHANGE)
                    sphere.Message(c4d.MSG_UPDATE)
                    cloner_changed = True

            # Скорость (%/сек)
            s_speed = s_data.get("speed")
            if s_speed is not None:
                rate_val = s_speed / 100.0
                if abs(cloner[c4d.MG_SPLINE_RATE] - rate_val) > 0.0001:
                    cloner[c4d.MG_SPLINE_RATE] = rate_val
                    cloner_changed = True

            # Дистанция (шаг между сферами, см)
            s_dist = s_data.get("dist")
            if s_dist is not None and s_dist > 0:
                if abs(cloner[c4d.MG_SPLINE_STEP] - s_dist) > 0.01:
                    cloner[c4d.MG_SPLINE_STEP] = s_dist
                    cloner_changed = True

            # Смещение вдоль провода (%)
            s_off = s_data.get("offset")
            if s_off is not None:
                off_val = s_off / 100.0
                if abs(cloner[c4d.MG_SPLINE_OFFSET] - off_val) > 0.0001:
                    cloner[c4d.MG_SPLINE_OFFSET] = off_val
                    cloner_changed = True

            if cloner_changed:
                cloner.SetDirty(c4d.DIRTYFLAGS_CACHE | c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_CHILDREN)
                cloner.Message(c4d.MSG_CHANGE)
                cloner.Message(c4d.MSG_UPDATE)
                c4d.EventAdd()

def message(id, data):
    if id in (c4d.MSG_DESCRIPTION_POSTSETPARAMETER, c4d.MSG_CHANGE):
        main()
        c4d.EventAdd()
'''


def calc_sag_direction(delta, axis_mode):
    """Вычисляет вектор направления провисания провода."""
    dist = delta.GetLength()
    if axis_mode == 0:  # Гравитация (-Y)
        if dist > 0.001 and abs(delta.y / dist) > 0.98:
            return c4d.Vector(1, 0, 0)
        return c4d.Vector(0, -1, 0)
    elif axis_mode == 1:  # Вверх (+Y)
        if dist > 0.001 and abs(delta.y / dist) > 0.98:
            return c4d.Vector(-1, 0, 0)
        return c4d.Vector(0, 1, 0)
    elif axis_mode == 2:  # Перпендикулярно вниз
        down = c4d.Vector(0, -1, 0)
        if dist > 0.001:
            u = delta.GetNormalized()
            perp = down - (down.Dot(u)) * u
            if perp.GetLength() > 0.05:
                return perp.GetNormalized()
        return c4d.Vector(1, 0, 0)
    elif axis_mode == 3:  # Ось X
        return c4d.Vector(1, 0, 0)
    elif axis_mode == 4:  # Ось Z
        return c4d.Vector(0, 0, 1)
    return c4d.Vector(0, -1, 0)


def create_glowing_material(doc, name, color):
    """Создает светящийся неоновый материал для сфер потока данных."""
    mat = c4d.BaseMaterial(c4d.Mmaterial)
    mat.SetName(f"Mat_{name}")
    mat[c4d.MATERIAL_USE_COLOR] = True
    mat[c4d.MATERIAL_COLOR_COLOR] = color
    mat[c4d.MATERIAL_USE_LUMINANCE] = True
    mat[c4d.MATERIAL_LUMINANCE_COLOR] = color
    mat[c4d.MATERIAL_LUMINANCE_BRIGHTNESS] = 2.5
    doc.InsertMaterial(mat)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, mat)
    return mat


def add_stream_user_data_group(rig, s_num, s_label, enable=True, radius=1.5, speed=30.0, dist=30.0, offset=0.0):
    """Добавляет аккуратную группу User Data для конкретного потока данных на верхний Wire_Rig."""
    bc_grp_stream = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
    bc_grp_stream[c4d.DESC_NAME] = f"Поток {s_num}: {s_label}"
    bc_grp_stream[c4d.DESC_TITLEBAR] = True
    bc_grp_stream[c4d.DESC_DEFAULT] = True
    id_grp_s = rig.AddUserData(bc_grp_stream)

    # Включить поток
    bc_en = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
    bc_en[c4d.DESC_NAME] = f"Поток {s_num}: Включить"
    bc_en[c4d.DESC_PARENTGROUP] = id_grp_s
    id_en = rig.AddUserData(bc_en)
    rig[id_en] = enable

    # Размер сфер
    bc_r = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
    bc_r[c4d.DESC_NAME] = f"Поток {s_num}: Размер сфер (см)"
    bc_r[c4d.DESC_UNIT] = c4d.DESC_UNIT_METER
    bc_r[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
    bc_r[c4d.DESC_MIN] = 0.05
    bc_r[c4d.DESC_MAX] = 50.0
    bc_r[c4d.DESC_STEP] = 0.1
    bc_r[c4d.DESC_PARENTGROUP] = id_grp_s
    id_r = rig.AddUserData(bc_r)
    rig[id_r] = radius

    # Скорость
    bc_sp = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
    bc_sp[c4d.DESC_NAME] = f"Поток {s_num}: Скорость (%/сек)"
    bc_sp[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
    bc_sp[c4d.DESC_MIN] = -300.0
    bc_sp[c4d.DESC_MAX] = 300.0
    bc_sp[c4d.DESC_STEP] = 1.0
    bc_sp[c4d.DESC_PARENTGROUP] = id_grp_s
    id_sp = rig.AddUserData(bc_sp)
    rig[id_sp] = speed

    # Дистанция
    bc_d = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
    bc_d[c4d.DESC_NAME] = f"Поток {s_num}: Дистанция (см)"
    bc_d[c4d.DESC_UNIT] = c4d.DESC_UNIT_METER
    bc_d[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
    bc_d[c4d.DESC_MIN] = 2.0
    bc_d[c4d.DESC_MAX] = 300.0
    bc_d[c4d.DESC_STEP] = 1.0
    bc_d[c4d.DESC_PARENTGROUP] = id_grp_s
    id_d = rig.AddUserData(bc_d)
    rig[id_d] = dist

    # Смещение
    bc_off = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
    bc_off[c4d.DESC_NAME] = f"Поток {s_num}: Смещение (%)"
    bc_off[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
    bc_off[c4d.DESC_MIN] = 0.0
    bc_off[c4d.DESC_MAX] = 100.0
    bc_off[c4d.DESC_STEP] = 1.0
    bc_off[c4d.DESC_PARENTGROUP] = id_grp_s
    id_off = rig.AddUserData(bc_off)
    rig[id_off] = offset


def add_data_stream_cloner(doc, path_spline, parent_null, name, radius=1.5, speed=30.0, step_dist=30.0, color_idx=0, offset=0.0):
    """Создает Cloner MoGraph со сферой и неоновым материалом."""
    color_name, color_vec = STREAM_COLORS[color_idx % len(STREAM_COLORS)]

    sphere = c4d.BaseObject(c4d.Osphere)
    sphere.SetName(f"{name}_Sphere")
    sphere[c4d.PRIM_SPHERE_RAD] = radius
    sphere[c4d.PRIM_SPHERE_SUB] = 16

    cloner = c4d.BaseObject(c4d.Omgcloner)
    cloner.SetName(name)
    cloner[c4d.ID_MG_MOTIONGENERATOR_MODE] = c4d.ID_MG_MOTIONGENERATOR_MODE_OBJECT
    cloner[c4d.MG_OBJECT_LINK] = path_spline
    cloner[c4d.MG_SPLINE_MODE] = c4d.MG_SPLINE_MODE_STEP
    cloner[c4d.MG_SPLINE_STEP] = step_dist
    cloner[c4d.MG_SPLINE_RATE] = speed / 100.0
    cloner[c4d.MG_SPLINE_OFFSET] = offset / 100.0
    cloner[c4d.MG_SPLINE_LOOP] = True
    cloner[c4d.MGCLONER_VOLUMEINSTANCES_MODE] = c4d.MGCLONER_VOLUMEINSTANCES_MODE_RENDERINSTANCE

    doc.InsertObject(cloner, parent=parent_null)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, cloner)
    doc.InsertObject(sphere, parent=cloner)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, sphere)

    mat = create_glowing_material(doc, name, color_vec)
    tex_tag = cloner.MakeTag(c4d.Ttexture)
    tex_tag[c4d.TEXTURETAG_MATERIAL] = mat
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, tex_tag)

    return cloner


def find_wire_path_in_selection(selected_obj):
    """
    Ищет Wire_Path сплайн, контейнер Data_Streams и корневой Wire_Rig в выделении.
    """
    if not selected_obj:
        return None, None, None

    def search_path(obj):
        if not obj:
            return None
        if obj.GetName() == "Wire_Path" and obj.CheckType(c4d.Ospline):
            return obj
        for child in obj.GetChildren():
            res = search_path(child)
            if res:
                return res
        return None

    path_spline = search_path(selected_obj)

    curr = selected_obj
    while not path_spline and curr.GetUp():
        curr = curr.GetUp()
        path_spline = search_path(curr)

    if not path_spline:
        return None, None, None

    sweep = path_spline.GetUp()
    rig_root = sweep.GetUp() if (sweep and sweep.GetUp()) else sweep

    data_streams = None

    if rig_root and rig_root != sweep:
        for child in rig_root.GetChildren():
            if child.GetName() == "Data_Streams":
                data_streams = child
                break
        if not data_streams:
            doc = path_spline.GetDocument()
            if doc:
                data_streams = c4d.BaseObject(c4d.Onull)
                data_streams.SetName("Data_Streams")
                doc.InsertObject(data_streams, parent=rig_root)
                doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, data_streams)
    else:
        # Если Sweep корневой
        next_obj = sweep.GetNext()
        if next_obj and next_obj.GetName() == "Data_Streams":
            data_streams = next_obj
        pred_obj = sweep.GetPred()
        if not data_streams and pred_obj and pred_obj.GetName() == "Data_Streams":
            data_streams = pred_obj

        if not data_streams:
            doc = path_spline.GetDocument()
            if doc:
                data_streams = c4d.BaseObject(c4d.Onull)
                data_streams.SetName("Data_Streams")
                doc.InsertObject(data_streams, pred=sweep)
                doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, data_streams)

    return path_spline, data_streams, rig_root


def update_rig_solver_tag(rig):
    """Обновляет теги решения на объекте Wire_Rig и объекте Sweep до актуальной версии."""
    if not rig:
        return False
    doc = rig.GetDocument()

    sweep = None
    if rig.CheckType(c4d.Osweep):
        sweep = rig
        if rig.GetUp() and "Wire_Rig" in rig.GetUp().GetName():
            rig = rig.GetUp()
    else:
        for child in rig.GetChildren():
            if child.CheckType(c4d.Osweep):
                sweep = child
                break

    def ensure_tag(target_obj, tag_name):
        found_tag = None
        for tag in target_obj.GetTags():
            if tag.CheckType(c4d.Tpython) and (tag.GetName() == tag_name or "Wire_" in tag.GetName()):
                found_tag = tag
                break
        if not found_tag:
            found_tag = c4d.BaseTag(c4d.Tpython)
            found_tag.SetName(tag_name)
            target_obj.InsertTag(found_tag)
            if doc:
                doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, found_tag)

        found_tag[c4d.TPYTHON_FRAME] = False  # ОБЯЗАТЕЛЬНО False для работы во вьюпорте в реальном времени!
        priority = found_tag[c4d.EXPRESSION_PRIORITY]
        if priority is not None:
            priority.SetPriorityValue(c4d.PRIORITYVALUE_MODE, c4d.CYCLE_EXPRESSION)
            priority.SetPriorityValue(c4d.PRIORITYVALUE_PRIORITY, 400)
            found_tag[c4d.EXPRESSION_PRIORITY] = priority
        found_tag[c4d.TPYTHON_CODE] = TAG_MASTER_SOLVER
        found_tag.Message(c4d.MSG_CHANGE)
        target_obj.Message(c4d.MSG_CHANGE)
        return found_tag

    # 1. Тег на верхнем объекте Wire_Rig
    ensure_tag(rig, "Wire_Master_Solver")

    # 2. Тег-компаньон на дочернем объекте Sweep
    if sweep and sweep != rig:
        ensure_tag(sweep, "Wire_Sweep_Solver")

    # 3. Обновляем режим клонеров потоков данных на RENDERINSTANCE (разблокирует интерактивное изменение сфер)
    for child in rig.GetChildren():
        if child.GetName() == "Data_Streams":
            for cloner in child.GetChildren():
                if cloner.CheckType(c4d.Omgcloner):
                    cloner[c4d.MGCLONER_VOLUMEINSTANCES_MODE] = c4d.MGCLONER_VOLUMEINSTANCES_MODE_RENDERINSTANCE
                    cloner.SetDirty(c4d.DIRTYFLAGS_CACHE | c4d.DIRTYFLAGS_DATA | c4d.DIRTYFLAGS_CHILDREN)
                    cloner.Message(c4d.MSG_CHANGE)
                    cloner.Message(c4d.MSG_UPDATE)

    # 4. Проверяем наличие InExclude списка опорных точек и добавляем его, если это старый риг
    has_inex = False
    id_grp_wire = None
    target_a_obj = None
    target_b_obj = None
    try:
        container = rig.GetUserDataContainer()
        if container:
            for desc_id, bc in container:
                if not bc:
                    continue
                name = bc[c4d.DESC_NAME] or ""
                name_l = name.lower()
                if "параметры провода" in name_l:
                    id_grp_wire = desc_id
                val = rig[desc_id]
                if isinstance(val, c4d.InExcludeData):
                    has_inex = True
                elif any(k in name_l for k in ["объект а", "точка а", "старт"]):
                    if hasattr(val, "GetLink"):
                        val = val.GetLink(doc)
                    if val:
                        target_a_obj = val
                elif any(k in name_l for k in ["объект б", "точка б", "конец"]):
                    if hasattr(val, "GetLink"):
                        val = val.GetLink(doc)
                    if val:
                        target_b_obj = val

        if not has_inex and (target_a_obj or target_b_obj):
            bc_inex = c4d.GetCustomDataTypeDefault(c4d.CUSTOMDATATYPE_INEXCLUDE_LIST)
            bc_inex[c4d.DESC_NAME] = "Опорные объекты (Точки кабеля)"
            bc_inex[c4d.DESC_SHORT_NAME] = "Опорные точки"
            if id_grp_wire:
                bc_inex[c4d.DESC_PARENTGROUP] = id_grp_wire
            id_inex = rig.AddUserData(bc_inex)
            inex_data = c4d.InExcludeData()
            if target_a_obj and target_a_obj.IsAlive():
                inex_data.InsertObject(target_a_obj, 1)
            if target_b_obj and target_b_obj.IsAlive():
                inex_data.InsertObject(target_b_obj, 1)
            rig[id_inex] = inex_data
    except Exception:
        pass

    rig.Message(c4d.MSG_CHANGE)
    if sweep:
        sweep.SetDirty(c4d.DIRTYFLAGS_CACHE | c4d.DIRTYFLAGS_DATA)
        sweep.Message(c4d.MSG_UPDATE)
    c4d.EventAdd()
    return True


def apply_preset_to_rig(rig, preset_data):
    """Записывает значения пресета в User Data выделенного Wire_Rig и обновляет его."""
    if not rig or not preset_data:
        return False
    doc = rig.GetDocument()
    if doc:
        doc.StartUndo()
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, rig)

    try:
        container = rig.GetUserDataContainer()
        if container:
            for desc_id, bc in container:
                try:
                    if desc_id[-1].dtype == c4d.DTYPE_GROUP:
                        continue
                except Exception:
                    pass
                name = bc[c4d.DESC_NAME] or ""
                name_l = str(name).lower()

                if "поток 1" in name_l:
                    if "включ" in name_l:
                        rig[desc_id] = preset_data.get("enable_streams", True)
                    elif "размер" in name_l or "сфер" in name_l or "радиус" in name_l:
                        rig[desc_id] = float(preset_data.get("s1_size", 1.5))
                    elif "дистанц" in name_l or "шаг" in name_l:
                        rig[desc_id] = float(preset_data.get("s1_dist", 30.0))
                    elif "скорост" in name_l:
                        rig[desc_id] = float(preset_data.get("s1_speed", 35.0))
                elif "поток 2" in name_l:
                    if "включ" in name_l:
                        rig[desc_id] = (preset_data.get("enable_streams", True) and preset_data.get("stream_preset", 2) >= 2)
                    elif "размер" in name_l or "сфер" in name_l or "радиус" in name_l:
                        rig[desc_id] = float(preset_data.get("s2_size", 1.0))
                    elif "дистанц" in name_l or "шаг" in name_l:
                        rig[desc_id] = float(preset_data.get("s2_dist", 45.0))
                    elif "скорост" in name_l:
                        rig[desc_id] = float(preset_data.get("s2_speed", -25.0))
                else:
                    if "толщин" in name_l or "радиус" in name_l:
                        rig[desc_id] = float(preset_data.get("wire_radius", 2.0))
                    elif "направлен" in name_l or "ось" in name_l:
                        rig[desc_id] = int(preset_data.get("axis_mode", 0))
                    elif "провисан" in name_l or "изгиб" in name_l or "sag" in name_l:
                        rig[desc_id] = float(preset_data.get("sag", 50.0))
                    elif "сегмент" in name_l or "детализац" in name_l:
                        rig[desc_id] = int(preset_data.get("subdivs", 25))
    except Exception:
        pass

    update_rig_solver_tag(rig)

    if doc:
        doc.EndUndo()
    rig.Message(c4d.MSG_CHANGE)
    c4d.EventAdd()
    return True


def create_wire_rig(doc, targets=None, target_a=None, target_b=None, wire_radius=2.0, sag=50.0, axis_mode=0, subdivs=25, profile_seg=8,
                    enable_streams=True, stream_preset=2,
                    s1_size=1.5, s1_dist=30.0, s1_speed=35.0,
                    s2_size=1.0, s2_dist=45.0, s2_speed=-25.0):
    """
    Создает полный риг провода через 2 или более объектов (Точки пути)
    со ВСЕМИ параметрами User Data на верхнем объекте Wire_Rig.
    """
    if not doc:
        return None

    # Подготовка списка целевых объектов
    valid_targets = []
    if targets and isinstance(targets, (list, tuple)):
        valid_targets = [t for t in targets if t and t.IsAlive()]
    elif target_a and target_b:
        if target_a.IsAlive() and target_b.IsAlive():
            valid_targets = [target_a, target_b]

    if len(valid_targets) < 2:
        return None

    doc.StartUndo()

    # 1. Корневой Null рига (Центр управления User Data)
    rig_null = c4d.BaseObject(c4d.Onull)
    if len(valid_targets) == 2:
        rig_null.SetName(f"Wire_Rig_{valid_targets[0].GetName()}_{valid_targets[1].GetName()}")
        sweep_name = f"Wire_{valid_targets[0].GetName()}_{valid_targets[1].GetName()}"
    else:
        rig_null.SetName(f"Wire_Rig_{valid_targets[0].GetName()}_to_{valid_targets[-1].GetName()}_({len(valid_targets)}pts)")
        sweep_name = f"Wire_{valid_targets[0].GetName()}_to_{valid_targets[-1].GetName()}"

    doc.InsertObject(rig_null)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, rig_null)

    # 2. Sweep генератор провода
    sweep = c4d.BaseObject(c4d.Osweep)
    sweep.SetName(sweep_name)

    circle = c4d.BaseObject(c4d.Osplinecircle)
    circle.SetName("Wire_Profile")
    circle[c4d.PRIM_CIRCLE_RADIUS] = wire_radius
    circle[c4d.PRIM_PLANE] = c4d.PRIM_PLANE_XY
    if profile_seg >= 3:
        circle[c4d.SPLINEOBJECT_SUB] = profile_seg

    # Вычисление первоначальных точек сплайна через все объекты
    num_targets = len(valid_targets)
    pts_per_seg = max(4, int(subdivs))
    pts = []
    for seg_idx in range(num_targets - 1):
        pos_a = valid_targets[seg_idx].GetMg().off
        pos_b = valid_targets[seg_idx + 1].GetMg().off
        delta = pos_b - pos_a
        sag_dir = calc_sag_direction(delta, axis_mode)

        end_k = pts_per_seg if (seg_idx == num_targets - 2) else (pts_per_seg - 1)
        for k in range(end_k + 1):
            t = float(k) / float(pts_per_seg)
            droop = 4.0 * t * (1.0 - t)
            pt_world = pos_a + delta * t + sag_dir * (sag * droop)
            pts.append(pt_world)

    total_num_pts = len(pts)
    path_spline = c4d.SplineObject(total_num_pts, c4d.SPLINETYPE_BSPLINE)
    path_spline.SetName("Wire_Path")
    path_spline[c4d.SPLINEOBJECT_CLOSED] = False
    path_spline[c4d.SPLINEOBJECT_TYPE] = c4d.SPLINEOBJECT_TYPE_BSPLINE
    path_spline[c4d.SPLINEOBJECT_INTERPOLATION] = c4d.SPLINEOBJECT_INTERPOLATION_ADAPTIVE
    path_spline[c4d.SPLINEOBJECT_ANGLE] = c4d.utils.Rad(5.0)
    path_spline.SetAllPoints(pts)
    path_spline.Message(c4d.MSG_POINTS_CHANGED)

    doc.InsertObject(sweep, parent=rig_null)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, sweep)
    doc.InsertObject(circle, parent=sweep)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, circle)
    doc.InsertObject(path_spline, parent=sweep, pred=circle)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, path_spline)

    # 3. Добавление User Data на верхний объект Wire_Rig
    # Группа: Параметры провода
    bc_grp_wire = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
    bc_grp_wire[c4d.DESC_NAME] = "Параметры провода"
    bc_grp_wire[c4d.DESC_TITLEBAR] = True
    bc_grp_wire[c4d.DESC_DEFAULT] = True
    id_grp_wire = rig_null.AddUserData(bc_grp_wire)

    # Интерактивный InExclude список опорных объектов
    bc_inex = c4d.GetCustomDataTypeDefault(c4d.CUSTOMDATATYPE_INEXCLUDE_LIST)
    bc_inex[c4d.DESC_NAME] = "Опорные объекты (Точки кабеля)"
    bc_inex[c4d.DESC_SHORT_NAME] = "Опорные точки"
    bc_inex[c4d.DESC_PARENTGROUP] = id_grp_wire
    id_inex = rig_null.AddUserData(bc_inex)
    
    inex_data = c4d.InExcludeData()
    for t in valid_targets:
        inex_data.InsertObject(t, 1)
    rig_null[id_inex] = inex_data

    # Для совместимости при 2 объектах сохраняем и ссылки А и Б
    if len(valid_targets) == 2:
        bc1 = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BASELISTLINK)
        bc1[c4d.DESC_NAME] = "Объект А (Старт)"
        bc1[c4d.DESC_SHORT_NAME] = "Точка А"
        bc1[c4d.DESC_PARENTGROUP] = id_grp_wire
        id1 = rig_null.AddUserData(bc1)
        rig_null[id1] = valid_targets[0]

        bc2 = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BASELISTLINK)
        bc2[c4d.DESC_NAME] = "Объект Б (Конец)"
        bc2[c4d.DESC_SHORT_NAME] = "Точка Б"
        bc2[c4d.DESC_PARENTGROUP] = id_grp_wire
        id2 = rig_null.AddUserData(bc2)
        rig_null[id2] = valid_targets[1]

    # Толщина
    bc3 = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
    bc3[c4d.DESC_NAME] = "Толщина кабеля (см)"
    bc3[c4d.DESC_SHORT_NAME] = "Толщина"
    bc3[c4d.DESC_UNIT] = c4d.DESC_UNIT_METER
    bc3[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
    bc3[c4d.DESC_MIN] = 0.05
    bc3[c4d.DESC_MAX] = 200.0
    bc3[c4d.DESC_STEP] = 0.1
    bc3[c4d.DESC_PARENTGROUP] = id_grp_wire
    id3 = rig_null.AddUserData(bc3)
    rig_null[id3] = wire_radius

    # Провисание
    bc4 = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
    bc4[c4d.DESC_NAME] = "Провисание кабеля (см)"
    bc4[c4d.DESC_SHORT_NAME] = "Провисание"
    bc4[c4d.DESC_UNIT] = c4d.DESC_UNIT_METER
    bc4[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
    bc4[c4d.DESC_MIN] = -1000.0
    bc4[c4d.DESC_MAX] = 1000.0
    bc4[c4d.DESC_STEP] = 1.0
    bc4[c4d.DESC_PARENTGROUP] = id_grp_wire
    id4 = rig_null.AddUserData(bc4)
    rig_null[id4] = sag

    # Направление изгиба
    bc5 = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
    bc5[c4d.DESC_NAME] = "Направление провисания (Ось)"
    bc5[c4d.DESC_SHORT_NAME] = "Ось"
    cycle_bc = c4d.BaseContainer()
    cycle_bc.SetString(0, "Гравитация (Вниз -Y)")
    cycle_bc.SetString(1, "Вверх (+Y)")
    cycle_bc.SetString(2, "Перпендикулярно (Авто)")
    cycle_bc.SetString(3, "По горизонтали (Ось X)")
    cycle_bc.SetString(4, "По горизонтали (Ось Z)")
    bc5[c4d.DESC_CYCLE] = cycle_bc
    bc5[c4d.DESC_PARENTGROUP] = id_grp_wire
    id5 = rig_null.AddUserData(bc5)
    rig_null[id5] = axis_mode

    # Сегментов сплайна
    bc6 = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
    bc6[c4d.DESC_NAME] = "Сегментов сплайна (на пролет)"
    bc6[c4d.DESC_SHORT_NAME] = "Сегментов"
    bc6[c4d.DESC_MIN] = 4
    bc6[c4d.DESC_MAX] = 100
    bc6[c4d.DESC_STEP] = 1
    bc6[c4d.DESC_PARENTGROUP] = id_grp_wire
    id6 = rig_null.AddUserData(bc6)
    rig_null[id6] = pts_per_seg

    # 4. Потоки данных (Cloners MoGraph)
    if enable_streams and stream_preset > 0:
        streams_null = c4d.BaseObject(c4d.Onull)
        streams_null.SetName("Data_Streams")
        doc.InsertObject(streams_null, parent=rig_null)
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, streams_null)

        # Поток 1: А -> Б
        add_data_stream_cloner(
            doc=doc,
            path_spline=path_spline,
            parent_null=streams_null,
            name="Stream_1_Forward [A->B]",
            radius=s1_size,
            speed=s1_speed,
            step_dist=s1_dist,
            color_idx=0,
            offset=0.0
        )
        add_stream_user_data_group(
            rig=rig_null,
            s_num=1,
            s_label="Вперед [А ➔ Б]",
            enable=True,
            radius=s1_size,
            speed=s1_speed,
            dist=s1_dist,
            offset=0.0
        )

        # Поток 2: Б -> А
        if stream_preset >= 2:
            add_data_stream_cloner(
                doc=doc,
                path_spline=path_spline,
                parent_null=streams_null,
                name="Stream_2_Return [B->A]",
                radius=s2_size,
                speed=s2_speed,
                step_dist=s2_dist,
                color_idx=1,
                offset=50.0
            )
            add_stream_user_data_group(
                rig=rig_null,
                s_num=2,
                s_label="Встречный [Б ➔ А]",
                enable=True,
                radius=s2_size,
                speed=s2_speed,
                dist=s2_dist,
                offset=50.0
            )

        # Поток 3: Быстрый микро-импульс (А -> Б)
        if stream_preset >= 3:
            p3_r = max(0.4, s1_size * 0.6)
            p3_sp = s1_speed * 1.8
            p3_d = s1_dist * 1.5
            add_data_stream_cloner(
                doc=doc,
                path_spline=path_spline,
                parent_null=streams_null,
                name="Stream_3_Pulse [A->B]",
                radius=p3_r,
                speed=p3_sp,
                step_dist=p3_d,
                color_idx=2,
                offset=25.0
            )
            add_stream_user_data_group(
                rig=rig_null,
                s_num=3,
                s_label="Импульс [А ➔ Б]",
                enable=True,
                radius=p3_r,
                speed=p3_sp,
                dist=p3_d,
                offset=25.0
            )

        # Поток 4: Обратный микро-импульс (Б -> А)
        if stream_preset >= 4:
            p4_r = max(0.5, s2_size * 0.7)
            p4_sp = s2_speed * 1.6
            p4_d = s2_dist * 1.4
            add_data_stream_cloner(
                doc=doc,
                path_spline=path_spline,
                parent_null=streams_null,
                name="Stream_4_Pulse [B->A]",
                radius=p4_r,
                speed=p4_sp,
                step_dist=p4_d,
                color_idx=3,
                offset=75.0
            )
            add_stream_user_data_group(
                rig=rig_null,
                s_num=4,
                s_label="Импульс [Б ➔ А]",
                enable=True,
                radius=p4_r,
                speed=p4_sp,
                dist=p4_d,
                offset=75.0
            )

    # 5. Мастер-тег Python на корневом объекте Wire_Rig
    master_tag = c4d.BaseTag(c4d.Tpython)
    master_tag.SetName("Wire_Master_Solver")
    master_tag[c4d.TPYTHON_FRAME] = False  # ОБЯЗАТЕЛЬНО False для работы во вьюпорте в реальном времени!
    priority = master_tag[c4d.EXPRESSION_PRIORITY]
    if priority is not None:
        priority.SetPriorityValue(c4d.PRIORITYVALUE_MODE, c4d.CYCLE_EXPRESSION)
        priority.SetPriorityValue(c4d.PRIORITYVALUE_PRIORITY, 400)
        master_tag[c4d.EXPRESSION_PRIORITY] = priority
    master_tag[c4d.TPYTHON_CODE] = TAG_MASTER_SOLVER
    rig_null.InsertTag(master_tag)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, master_tag)

    # 6. Тег-компаньон на самом Sweep объекте (гарантирует немедленный пересчет кэша генератора во вьюпорте)
    sweep_tag = c4d.BaseTag(c4d.Tpython)
    sweep_tag.SetName("Wire_Sweep_Solver")
    sweep_tag[c4d.TPYTHON_FRAME] = False  # ОБЯЗАТЕЛЬНО False!
    priority_sw = sweep_tag[c4d.EXPRESSION_PRIORITY]
    if priority_sw is not None:
        priority_sw.SetPriorityValue(c4d.PRIORITYVALUE_MODE, c4d.CYCLE_EXPRESSION)
        priority_sw.SetPriorityValue(c4d.PRIORITYVALUE_PRIORITY, 400)
        sweep_tag[c4d.EXPRESSION_PRIORITY] = priority_sw
    sweep_tag[c4d.TPYTHON_CODE] = TAG_MASTER_SOLVER
    sweep.InsertTag(sweep_tag)
    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, sweep_tag)

    # Выделяем верхний объект Wire_Rig
    doc.SetActiveObject(rig_null, c4d.SELECTION_NEW)
    doc.EndUndo()
    c4d.EventAdd()

    return rig_null


class CableGeneratorDialog(gui.GeDialog):
    """Интерактивное меню создания провода, управления пресетами и потоками данных."""
    DLG_ID = DLG_ID

    def __init__(self):
        super().__init__()
        self.presets = load_presets_from_disk()
        self.preset_keys = list(self.presets.keys())

    def CreateLayout(self):
        self.SetTitle("Генератор проводов и потоков данных - C4D 2026")

        # -------------------------------------------------------------
        # 1. ПРЕСЕТЫ НАСТРОЕК
        # -------------------------------------------------------------
        self.GroupBegin(IDC_GRP_PRESETS, c4d.BFH_SCALEFIT, 2, 0, "Пресеты настроек", 10)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.GroupBorderSpace(10, 8, 10, 8)

        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Загрузить пресет:", c4d.BORDER_NONE)
        self.AddComboBox(IDC_PRESET_LIST, c4d.BFH_SCALEFIT)

        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Сохранить текущие:", c4d.BORDER_NONE)
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 3, 0, "", 0)
        self.AddEditText(IDC_PRESET_NAME, c4d.BFH_SCALEFIT, 140, 0)
        self.AddButton(IDC_BTN_SAVE_PRESET, c4d.BFH_RIGHT, 90, 0, "💾 Сохранить")
        self.AddButton(IDC_BTN_DEL_PRESET, c4d.BFH_RIGHT, 80, 0, "🗑️ Удалить")
        self.GroupEnd()

        self.GroupEnd()

        # -------------------------------------------------------------
        # 2. СТАТУС ВЫДЕЛЕНИЯ
        # -------------------------------------------------------------
        self.GroupBegin(IDC_GRP_SELECTION, c4d.BFH_SCALEFIT, 1, 0, "Выбор объектов в сцене", 10)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.GroupBorderSpace(10, 8, 10, 8)
        self.AddStaticText(IDC_TXT_SELECTION, c4d.BFH_SCALEFIT, 0, 0, "Поиск объектов...", c4d.BORDER_NONE)
        self.GroupEnd()

        # -------------------------------------------------------------
        # 3. ПАРАМЕТРЫ ПРОВОДА
        # -------------------------------------------------------------
        self.GroupBegin(IDC_GRP_SETTINGS, c4d.BFH_SCALEFIT, 2, 0, "Параметры провода", 10)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.GroupBorderSpace(10, 8, 10, 8)

        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Толщина (Радиус, см):", c4d.BORDER_NONE)
        self.AddEditSlider(IDC_RADIUS, c4d.BFH_SCALEFIT)

        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Провисание / Изгиб (см):", c4d.BORDER_NONE)
        self.AddEditSlider(IDC_SAG, c4d.BFH_SCALEFIT)

        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Направление изгиба:", c4d.BORDER_NONE)
        self.AddComboBox(IDC_AXIS, c4d.BFH_SCALEFIT)
        self.AddChild(IDC_AXIS, 0, "Гравитация (Вниз -Y)")
        self.AddChild(IDC_AXIS, 1, "Вверх (+Y)")
        self.AddChild(IDC_AXIS, 2, "Перпендикулярно (Авто)")
        self.AddChild(IDC_AXIS, 3, "По горизонтали (Ось X)")
        self.AddChild(IDC_AXIS, 4, "По горизонтали (Ось Z)")

        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Детализация сплайна:", c4d.BORDER_NONE)
        self.AddEditSlider(IDC_SUBDIVS, c4d.BFH_SCALEFIT)

        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Сечение (Граней):", c4d.BORDER_NONE)
        self.AddEditSlider(IDC_PROFILE_SEG, c4d.BFH_SCALEFIT)

        self.GroupEnd()

        # -------------------------------------------------------------
        # 4. ПОТОКИ ДАННЫХ (БЕГУЩИЕ СФЕРЫ)
        # -------------------------------------------------------------
        self.GroupBegin(IDC_GRP_STREAMS, c4d.BFH_SCALEFIT, 2, 0, "Эффект обмена данными (Бегущие сферы)", 10)
        self.GroupBorder(c4d.BORDER_GROUP_IN)
        self.GroupBorderSpace(10, 8, 10, 8)

        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Эффект частиц:", c4d.BORDER_NONE)
        self.AddCheckbox(IDC_ENABLE_STREAMS, c4d.BFH_LEFT, 0, 0, "Включить сферы данных (MoGraph)")

        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Режим каналов:", c4d.BORDER_NONE)
        self.AddComboBox(IDC_STREAM_PRESET, c4d.BFH_SCALEFIT)
        self.AddChild(IDC_STREAM_PRESET, 1, "1 поток: А ➔ Б (Прямой)")
        self.AddChild(IDC_STREAM_PRESET, 2, "2 встречных потока: А ➔ Б и Б ➔ А (Обмен)")
        self.AddChild(IDC_STREAM_PRESET, 3, "3 потока: 2 вперед + 1 встречный")
        self.AddChild(IDC_STREAM_PRESET, 4, "4 потока: разноскоростные каналы")

        # Настройки Потока 1
        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Поток 1 (А➔Б) Размер сфер (см):", c4d.BORDER_NONE)
        self.AddEditSlider(IDC_S1_SIZE, c4d.BFH_SCALEFIT)

        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Поток 1 Дистанция (см):", c4d.BORDER_NONE)
        self.AddEditSlider(IDC_S1_DIST, c4d.BFH_SCALEFIT)

        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Поток 1 Скорость (%/сек):", c4d.BORDER_NONE)
        self.AddEditSlider(IDC_S1_SPEED, c4d.BFH_SCALEFIT)

        # Настройки Потока 2
        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Поток 2 (Б➔А) Размер сфер (см):", c4d.BORDER_NONE)
        self.AddEditSlider(IDC_S2_SIZE, c4d.BFH_SCALEFIT)

        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Поток 2 Дистанция (см):", c4d.BORDER_NONE)
        self.AddEditSlider(IDC_S2_DIST, c4d.BFH_SCALEFIT)

        self.AddStaticText(0, c4d.BFH_LEFT, 0, 0, "Поток 2 Скорость (%/сек):", c4d.BORDER_NONE)
        self.AddEditSlider(IDC_S2_SPEED, c4d.BFH_SCALEFIT)

        self.GroupEnd()

        # -------------------------------------------------------------
        # 5. ДЕЙСТВИЯ И КНОПКИ УПРАВЛЕНИЯ
        # -------------------------------------------------------------
        self.GroupBegin(IDC_GRP_ACTIONS, c4d.BFH_SCALEFIT, 1, 0, "", 10)
        self.GroupBorderSpace(10, 5, 10, 10)
        self.AddButton(IDC_BTN_CREATE, c4d.BFH_SCALEFIT, 0, 32, "⚡ Создать кабель / провод (через выбранные объекты)")

        self.GroupBegin(0, c4d.BFH_SCALEFIT, 3, 0, "", 0)
        self.AddButton(IDC_BTN_ADD_STREAM, c4d.BFH_SCALEFIT, 0, 26, "➕ Добавить поток")
        self.AddButton(IDC_BTN_APPLY_TO_RIG, c4d.BFH_SCALEFIT, 0, 26, "📋 Применить пресет")
        self.AddButton(IDC_BTN_FIX_RIG, c4d.BFH_SCALEFIT, 0, 26, "🔄 Обновить тег")
        self.GroupEnd()

        self.AddStaticText(IDC_TXT_STATUS, c4d.BFH_SCALEFIT, 0, 0, "💡 Все параметры провода и сфер вынесены в User Data на верхний Wire_Rig!", c4d.BORDER_NONE)
        self.GroupEnd()

        return True

    def RefreshPresetsMenu(self):
        """Обновляет список пресетов в комбобоксе."""
        self.FreeChildren(IDC_PRESET_LIST)
        self.preset_keys = list(self.presets.keys())
        for idx, name in enumerate(self.preset_keys):
            self.AddChild(IDC_PRESET_LIST, idx, name)

    def ApplyPreset(self, name):
        """Применяет выбранный пресет к элементам управления диалога."""
        if name not in self.presets:
            return
        p = self.presets[name]
        self.SetFloat(IDC_RADIUS, p.get("wire_radius", 2.0))
        self.SetFloat(IDC_SAG, p.get("sag", 50.0))
        self.SetInt32(IDC_AXIS, p.get("axis_mode", 0))
        self.SetFloat(IDC_SUBDIVS, float(p.get("subdivs", 25)))
        self.SetFloat(IDC_PROFILE_SEG, float(p.get("profile_seg", 8)))

        self.SetBool(IDC_ENABLE_STREAMS, p.get("enable_streams", True))
        self.SetInt32(IDC_STREAM_PRESET, p.get("stream_preset", 2))
        self.SetFloat(IDC_S1_SIZE, p.get("s1_size", 1.5))
        self.SetFloat(IDC_S1_DIST, p.get("s1_dist", 30.0))
        self.SetFloat(IDC_S1_SPEED, p.get("s1_speed", 35.0))

        self.SetFloat(IDC_S2_SIZE, p.get("s2_size", 1.0))
        self.SetFloat(IDC_S2_DIST, p.get("s2_dist", 45.0))
        self.SetFloat(IDC_S2_SPEED, p.get("s2_speed", -25.0))

        self.SetString(IDC_TXT_STATUS, f"✅ Применен пресет: '{name}'")

    def GetCurrentValuesDict(self):
        """Считывает текущие значения диалога в виде словаря пресета."""
        return {
            "wire_radius": self.GetFloat(IDC_RADIUS),
            "sag": self.GetFloat(IDC_SAG),
            "axis_mode": self.GetInt32(IDC_AXIS),
            "subdivs": int(self.GetFloat(IDC_SUBDIVS)),
            "profile_seg": int(self.GetFloat(IDC_PROFILE_SEG)),
            "enable_streams": self.GetBool(IDC_ENABLE_STREAMS),
            "stream_preset": self.GetInt32(IDC_STREAM_PRESET),
            "s1_size": self.GetFloat(IDC_S1_SIZE),
            "s1_dist": self.GetFloat(IDC_S1_DIST),
            "s1_speed": self.GetFloat(IDC_S1_SPEED),
            "s2_size": self.GetFloat(IDC_S2_SIZE),
            "s2_dist": self.GetFloat(IDC_S2_DIST),
            "s2_speed": self.GetFloat(IDC_S2_SPEED)
        }

    def InitValues(self):
        # Первоначальная инициализация списка пресетов
        self.RefreshPresetsMenu()
        self.SetInt32(IDC_PRESET_LIST, 0)
        self.SetString(IDC_PRESET_NAME, "Мой пресет")

        # Настройки по умолчанию
        self.SetFloat(IDC_RADIUS, 2.0, min=0.1, max=200.0, step=0.5)
        self.SetFloat(IDC_SAG, 50.0, min=-500.0, max=500.0, step=5.0)
        self.SetInt32(IDC_AXIS, 0)
        self.SetFloat(IDC_SUBDIVS, 25.0, min=4.0, max=100.0, step=1.0)
        self.SetFloat(IDC_PROFILE_SEG, 8.0, min=3.0, max=32.0, step=1.0)

        self.SetBool(IDC_ENABLE_STREAMS, True)
        self.SetInt32(IDC_STREAM_PRESET, 2)
        self.SetFloat(IDC_S1_SIZE, 1.5, min=0.1, max=30.0, step=0.1)
        self.SetFloat(IDC_S1_DIST, 30.0, min=5.0, max=200.0, step=1.0)
        self.SetFloat(IDC_S1_SPEED, 35.0, min=-300.0, max=300.0, step=1.0)

        self.SetFloat(IDC_S2_SIZE, 1.0, min=0.1, max=30.0, step=0.1)
        self.SetFloat(IDC_S2_DIST, 45.0, min=5.0, max=200.0, step=1.0)
        self.SetFloat(IDC_S2_SPEED, -25.0, min=-300.0, max=300.0, step=1.0)

        # Применяем первый пресет
        if self.preset_keys:
            self.ApplyPreset(self.preset_keys[0])

        self.SetTimer(250)
        self.UpdateSelectionUI()
        return True

    def UpdateSelectionUI(self):
        doc = c4d.documents.GetActiveDocument()
        if not doc:
            self.SetString(IDC_TXT_SELECTION, "Нет активного документа")
            self.Enable(IDC_BTN_CREATE, False)
            self.Enable(IDC_BTN_ADD_STREAM, False)
            self.Enable(IDC_BTN_APPLY_TO_RIG, False)
            self.Enable(IDC_BTN_FIX_RIG, False)
            return

        sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_SELECTIONORDER)
        if len(sel) < 2:
            sel = doc.GetActiveObjects(0)

        if len(sel) >= 2:
            if len(sel) == 2:
                self.SetString(IDC_TXT_SELECTION, f"🟢 Готово (2 объекта): [{sel[0].GetName()}] ➔ [{sel[1].GetName()}]")
            elif len(sel) <= 4:
                chain = " ➔ ".join([f"[{o.GetName()}]" for o in sel])
                self.SetString(IDC_TXT_SELECTION, f"🟢 Готово ({len(sel)} точки): {chain}")
            else:
                self.SetString(IDC_TXT_SELECTION, f"🟢 Готово ({len(sel)} точек): [{sel[0].GetName()}] ➔ ... ➔ [{sel[-1].GetName()}]")
            self.Enable(IDC_BTN_CREATE, True)
        else:
            self.SetString(IDC_TXT_SELECTION, f"ℹ️ Выделите 2 или более объектов/Null (сейчас: {len(sel)})")
            self.Enable(IDC_BTN_CREATE, False)

        active_obj = doc.GetActiveObject()
        path_spline, _, rig_root = find_wire_path_in_selection(active_obj)
        if path_spline and rig_root:
            self.Enable(IDC_BTN_ADD_STREAM, True)
            self.Enable(IDC_BTN_APPLY_TO_RIG, True)
            self.Enable(IDC_BTN_FIX_RIG, True)
            if len(sel) < 2:
                self.SetString(IDC_TXT_SELECTION, f"🎯 Выбран провод: [{rig_root.GetName()}] (доступно управление)")
        else:
            self.Enable(IDC_BTN_ADD_STREAM, False)
            self.Enable(IDC_BTN_APPLY_TO_RIG, False)
            self.Enable(IDC_BTN_FIX_RIG, False)

    def Timer(self, msg):
        self.UpdateSelectionUI()

    def Command(self, id, msg):
        doc = c4d.documents.GetActiveDocument()
        if not doc:
            return True

        # Смена пресета в списке
        if id == IDC_PRESET_LIST:
            idx = self.GetInt32(IDC_PRESET_LIST)
            if 0 <= idx < len(self.preset_keys):
                name = self.preset_keys[idx]
                self.ApplyPreset(name)
                self.SetString(IDC_PRESET_NAME, name)

        # Сохранение нового пресета
        elif id == IDC_BTN_SAVE_PRESET:
            name = self.GetString(IDC_PRESET_NAME).strip()
            if not name:
                gui.MessageDialog("Пожалуйста, введите имя пресета!")
                return True

            self.presets[name] = self.GetCurrentValuesDict()
            if save_presets_to_disk(self.presets):
                self.RefreshPresetsMenu()
                new_idx = self.preset_keys.index(name) if name in self.preset_keys else 0
                self.SetInt32(IDC_PRESET_LIST, new_idx)
                self.SetString(IDC_TXT_STATUS, f"💾 Пресет '{name}' успешно сохранен на диск!")
            else:
                self.SetString(IDC_TXT_STATUS, "❌ Ошибка сохранения пресета")

        # Удаление пресета
        elif id == IDC_BTN_DEL_PRESET:
            idx = self.GetInt32(IDC_PRESET_LIST)
            if 0 <= idx < len(self.preset_keys):
                name = self.preset_keys[idx]
                if name in self.presets:
                    del self.presets[name]
                    save_presets_to_disk(self.presets)
                    self.RefreshPresetsMenu()
                    self.SetInt32(IDC_PRESET_LIST, 0)
                    if self.preset_keys:
                        self.ApplyPreset(self.preset_keys[0])
                    self.SetString(IDC_TXT_STATUS, f"🗑️ Пресет '{name}' удален")

        # Создание нового рига
        elif id == IDC_BTN_CREATE:
            sel = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_SELECTIONORDER)
            if len(sel) < 2:
                sel = doc.GetActiveObjects(0)

            if len(sel) < 2:
                gui.MessageDialog("Пожалуйста, выделите как минимум 2 объекта в сцене!\n(Опорные точки кабеля по порядку)")
                return True

            rig = create_wire_rig(
                doc=doc,
                targets=sel,
                wire_radius=self.GetFloat(IDC_RADIUS),
                sag=self.GetFloat(IDC_SAG),
                axis_mode=self.GetInt32(IDC_AXIS),
                subdivs=int(self.GetFloat(IDC_SUBDIVS)),
                profile_seg=int(self.GetFloat(IDC_PROFILE_SEG)),
                enable_streams=self.GetBool(IDC_ENABLE_STREAMS),
                stream_preset=self.GetInt32(IDC_STREAM_PRESET),
                s1_size=self.GetFloat(IDC_S1_SIZE),
                s1_dist=self.GetFloat(IDC_S1_DIST),
                s1_speed=self.GetFloat(IDC_S1_SPEED),
                s2_size=self.GetFloat(IDC_S2_SIZE),
                s2_dist=self.GetFloat(IDC_S2_DIST),
                s2_speed=self.GetFloat(IDC_S2_SPEED)
            )

            if rig:
                self.SetString(IDC_TXT_STATUS, f"✅ Создан: {rig.GetName()} ({len(sel)} точек)")
            else:
                self.SetString(IDC_TXT_STATUS, "❌ Ошибка создания")

        # Добавление нового потока к существующему проводу
        elif id == IDC_BTN_ADD_STREAM:
            active_obj = doc.GetActiveObject()
            path_spline, parent_group, rig_root = find_wire_path_in_selection(active_obj)

            if not path_spline or not parent_group or not rig_root:
                gui.MessageDialog("Пожалуйста, выделите провод (Wire_Rig) в Object Manager!")
                return True

            doc.StartUndo()

            # Подсчет существующих потоков
            existing_count = 0
            for child in parent_group.GetChildren():
                if "Stream" in child.GetName():
                    existing_count += 1

            new_idx = existing_count + 1
            is_forward = (new_idx % 2 != 0)
            stream_speed = 35.0 if is_forward else -25.0
            dir_label = "А ➔ Б" if is_forward else "Б ➔ А"
            stream_name = f"Stream_{new_idx}_[A->B]" if is_forward else f"Stream_{new_idx}_[B->A]"

            # Создаем клонер
            cloner = add_data_stream_cloner(
                doc=doc,
                path_spline=path_spline,
                parent_null=parent_group,
                name=stream_name,
                radius=1.2,
                speed=stream_speed,
                step_dist=35.0,
                color_idx=existing_count % len(STREAM_COLORS),
                offset=(existing_count * 20.0) % 100.0
            )

            # Добавляем User Data группу для нового потока на верхний Wire_Rig
            add_stream_user_data_group(
                rig=rig_root,
                s_num=new_idx,
                s_label=f"Канал {new_idx} [{dir_label}]",
                enable=True,
                radius=1.2,
                speed=stream_speed,
                dist=35.0,
                offset=(existing_count * 20.0) % 100.0
            )

            update_rig_solver_tag(rig_root)

            doc.SetActiveObject(rig_root, c4d.SELECTION_NEW)
            doc.EndUndo()
            c4d.EventAdd()

            self.SetString(IDC_TXT_STATUS, f"✅ Добавлен Поток {new_idx} (параметры добавлены на {rig_root.GetName()})")

        # Применение пресета к выделенному проводу
        elif id == IDC_BTN_APPLY_TO_RIG:
            active_obj = doc.GetActiveObject()
            _, _, rig_root = find_wire_path_in_selection(active_obj)
            if not rig_root:
                gui.MessageDialog("Пожалуйста, выделите провод (Wire_Rig) в сцене!")
                return True
            preset_data = self.GetCurrentValuesDict()
            if apply_preset_to_rig(rig_root, preset_data):
                self.SetString(IDC_TXT_STATUS, f"✅ Пресет применен к '{rig_root.GetName()}'!")
            else:
                self.SetString(IDC_TXT_STATUS, "❌ Не удалось применить пресет")

        # Обновление / починка тега на выделенном проводе
        elif id == IDC_BTN_FIX_RIG:
            active_obj = doc.GetActiveObject()
            _, _, rig_root = find_wire_path_in_selection(active_obj)
            if not rig_root:
                gui.MessageDialog("Пожалуйста, выделите провод (Wire_Rig) в сцене!")
                return True
            if update_rig_solver_tag(rig_root):
                rig_root.Message(c4d.MSG_CHANGE)
                c4d.EventAdd()
                self.SetString(IDC_TXT_STATUS, f"✅ Тег решения на '{rig_root.GetName()}' обновлен до актуальной версии!")
            else:
                self.SetString(IDC_TXT_STATUS, "❌ Ошибка обновления тега")

        return True


CURRENT_DIALOG = None

def main():
    global CURRENT_DIALOG
    if CURRENT_DIALOG is not None:
        try:
            CURRENT_DIALOG.Close()
        except Exception:
            pass
        CURRENT_DIALOG = None

    CURRENT_DIALOG = CableGeneratorDialog()
    CURRENT_DIALOG.Open(
        dlgtype=c4d.DLG_TYPE_ASYNC,
        pluginid=CableGeneratorDialog.DLG_ID,
        defaultw=440,
        defaulth=540
    )

if __name__ == "__main__":
    main()
