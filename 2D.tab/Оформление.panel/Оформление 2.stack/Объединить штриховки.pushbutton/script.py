# coding=utf-8
import Autodesk.Revit.Exceptions
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

import dosymep

clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI.Selection import ISelectionFilter
from Autodesk.Revit.UI.Selection import ObjectType

from pyrevit import forms
from pyrevit import revit
from pyrevit import script
from pyrevit import HOST_APP
from pyrevit import EXEC_PARAMS


from dosymep_libs.bim4everyone import *
from dosymep.Revit.Geometry import *

import regions


class RevitRepository:
    def __init__(self):
        pass

    @staticmethod
    def merge_regions(main_region, other_regions):
        main_solids, other_solids = regions.get_solids(main_region, other_regions)
        solids = list(other_solids)
        solids.append(main_solids)
        result_solids = regions.unite_solids(solids)
        return regions.get_bottom_loops(result_solids, regions.get_normal(main_region))


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    repo = RevitRepository() # type: RevitRepository
    main_region = regions.pick_region("Выберите основную штриховку") # type: FilledRegion
    other_regions = regions.pick_regions(main_region, "Выберите штриховки для объединения") # type: list
    if not other_regions:
        raise System.OperationCanceledException()
    loops = repo.merge_regions(main_region, other_regions)
    try:
        regions.create_region(main_region.GetTypeId(), main_region.OwnerViewId, loops, "BIM: Создание штриховки")
    except Autodesk.Revit.Exceptions.ApplicationException:
        script.output.get_output().close()
        forms.alert("Нельзя объединить штриховки. Скорее всего из-за самопересекающихся контуров", exitscript=True)
    ids = [i.Id for i in other_regions]
    ids.append(main_region.Id)
    regions.delete_elements(ids, "BIM: Удаление старых штриховок")


script_execute()
