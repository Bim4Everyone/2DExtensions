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


class CutRegionSelectionFilter(ISelectionFilter):
    def __init__(self, main_id):
        self.__main_id = main_id

    def AllowElement(self, elem):
        return isinstance(elem, FilledRegion) and (elem.Id != self.__main_id)

    def AllowReference(self, ref, point):
        return False


class MainRegionSelectionFilter(ISelectionFilter):
    def AllowElement(self, elem):
        return isinstance(elem, FilledRegion)

    def AllowReference(self, ref, point):
        return False

class RevitRepository:
    def __init__(self):
        self.__doc = HOST_APP.doc
        self.__uidoc = HOST_APP.uidoc

    def select_region(self):
        with forms.WarningBar(title='Выберите основную штриховку'):
            reference = self.__uidoc.Selection.PickObject(ObjectType.Element, MainRegionSelectionFilter())
            return self.__doc.GetElement(reference)

    def select_regions(self, main_region):
        with forms.WarningBar(title='Выберите штриховки для вырезания'):
            references = self.__uidoc.Selection.PickObjects(
                ObjectType.Element,
                CutRegionSelectionFilter(main_region.Id))
            return [self.__doc.GetElement(ref) for ref in references]

    @staticmethod
    def get_solids(main_region, cutting_regions):
        direction = XYZ.BasisZ
        distance = 1
        main_z = list(main_region.GetBoundaries()[0])[0].GetEndPoint(0).Z
        cut_solids = []
        for region in cutting_regions:
            boundaries = region.GetBoundaries()
            for loop in boundaries:
                z_diff = list(loop)[0].GetEndPoint(0).Z - main_z
                transform = Transform.CreateTranslation(XYZ(0,0,-z_diff))
                loop_transformed = CurveLoop.CreateViaTransform(loop, transform)
                solid = GeometryCreationUtilities.CreateExtrusionGeometry(
                    [loop_transformed],
                    direction,
                    distance)
                cut_solids.append(solid)
        main_solids = []
        for loop in main_region.GetBoundaries():
            main_solids.append(GeometryCreationUtilities.CreateExtrusionGeometry(
                [loop],
                direction,
                distance))
        return main_solids, cut_solids

    def cut_regions(self, main_region, cutting_regions):
        main_solids, cutting_solids = self.get_solids(main_region, cutting_regions)
        result_solids = []
        for main_solid in main_solids:
            result_solid = main_solid
            for cutting_solid in cutting_solids:
                result_solid = BooleanOperationsUtils.ExecuteBooleanOperation(
                    result_solid,
                    cutting_solid,
                    BooleanOperationsType.Difference)
            result_solids.append(result_solid)
        return self.get_curve_loops(result_solids)

    def create_region(self, type_id, view_id, loops):
        with revit.Transaction('Вырезание штриховки'):
            FilledRegion.Create(self.__doc, type_id, view_id, loops)

    @staticmethod
    def get_curve_loops(solids):
        result_solids = [i for i in solids if i is not None and i.Volume > 0]
        faces_lists = [list(solid.Faces) for solid in result_solids]
        faces = [face for face_list in faces_lists for face in face_list]
        bottom_faces = [face for face in faces if face.ComputeNormal(UV()).IsAlmostEqualTo(-XYZ.BasisZ)]
        loops_list = [i.GetEdgesAsCurveLoops() for i in bottom_faces]
        return [loop for loop_list in loops_list for loop in loop_list]

@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    repo = RevitRepository()
    main_region = repo.select_region() # type: FilledRegion
    cutting_regions = repo.select_regions(main_region) # type: list
    loops = repo.cut_regions(main_region, cutting_regions)
    repo.create_region(main_region.GetTypeId(), main_region.OwnerViewId, loops)


script_execute()
