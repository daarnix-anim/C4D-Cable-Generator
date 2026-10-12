"""
=============================================================================
Быстрый скрипт для обновления тегов всех проводов в открытой сцене C4D
=============================================================================
Обновляет теги на всех существующих в сцене ригах Wire_Rig до последней версии
(TPYTHON_FRAME = False, двойной солвер на Rig и Sweep, мгновенный отклик User Data).
"""
import c4d
import sys
import importlib

# Гарантированная перезагрузка Cable_Generator из файловой системы,
# чтобы Cinema 4D не использовал старую версию модуля из кэша памяти
if "Cable_Generator" in sys.modules:
    try:
        importlib.reload(sys.modules["Cable_Generator"])
    except Exception:
        pass

import Cable_Generator
from Cable_Generator import TAG_MASTER_SOLVER, update_rig_solver_tag

def main():
    doc = c4d.documents.GetActiveDocument()
    if not doc:
        return

    doc.StartUndo()
    count = 0
    updated_rigs = set()

    def check_obj(obj):
        nonlocal count
        if not obj:
            return

        target_rig = None
        if "Wire_Rig" in obj.GetName():
            target_rig = obj
        elif any("Wire_" in t.GetName() for t in obj.GetTags()):
            target_rig = obj.GetUp() if (obj.GetUp() and "Wire_Rig" in obj.GetUp().GetName()) else obj

        if target_rig and target_rig not in updated_rigs:
            if update_rig_solver_tag(target_rig):
                updated_rigs.add(target_rig)
                doc.AddUndo(c4d.UNDOTYPE_CHANGE, target_rig)
                target_rig.Message(c4d.MSG_CHANGE)
                count += 1

        for child in obj.GetChildren():
            check_obj(child)

    root = doc.GetFirstObject()
    while root:
        check_obj(root)
        root = root.GetNext()

    doc.EndUndo()
    c4d.EventAdd()

    if count > 0:
        c4d.gui.MessageDialog(
            f"✅ Успешно обновлено проводов в сцене (v0.9.1): {count}!\n\n"
            f"• Все теги переведены в режим реального времени (TPYTHON_FRAME = False)\n"
            f"• Добавлены дублирующие солверы на Sweep для мгновенного обновления кэша\n"
            f"• Клонеры переведены в Render Instance — размер сфер и параметры разблокированы\n"
            f"• Добавлен список опорных точек (InExclude) для маршрутизации через N объектов\n"
            f"• Любые изменения в User Data на Wire_Rig сразу видны во вьюпорте!"
        )
    else:
        c4d.gui.MessageDialog(
            "Провода Wire_Rig в сцене не найдены.\n"
            "Выделите 2 объекта и создайте провод через генератор кабелей."
        )

if __name__ == "__main__":
    main()
