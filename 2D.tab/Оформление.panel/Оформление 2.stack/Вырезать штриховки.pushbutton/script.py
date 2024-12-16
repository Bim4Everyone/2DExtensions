# coding=utf-8

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
        self.__doc = HOST_APP.doc # type: Document
        self.__uidoc = HOST_APP.uidoc

    def get_loops(self, main_region, cutting_regions):
        main_solid, cutting_solids = regions.get_solids(main_region, cutting_regions)
        result_solids = self.cut_solids(main_solid, cutting_solids)
        result_solids = regions.unite_solids(result_solids)
        return regions.get_bottom_loops(result_solids, regions.get_normal(main_region))

    @staticmethod
    def cut_solids(first_solid, second_solids):
        result = first_solid
        for solid in second_solids:
            result = BooleanOperationsUtils.ExecuteBooleanOperation(
                result,
                solid,
                BooleanOperationsType.Difference)
        return regions.unite_solids([result])


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    repo = RevitRepository()
    main_region = regions.pick_region("Выберите основную штриховку") # type: FilledRegion
    cutting_regions = regions.pick_regions(main_region, "Выберите штриховки для вырезания") # type: list
    if not cutting_regions:
        raise System.OperationCanceledException()
    loops = repo.get_loops(main_region, cutting_regions)
    regions.create_region(main_region.GetTypeId(), main_region.OwnerViewId, loops, "BIM: Создание штриховки")
    regions.delete_element(main_region.Id, "BIM: Удаление старой штриховки")


script_execute()
