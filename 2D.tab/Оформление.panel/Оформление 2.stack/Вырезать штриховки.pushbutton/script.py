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
        self.__doc = HOST_APP.doc # type: Document
        self.__uidoc = HOST_APP.uidoc

    def pick_region(self):
        with forms.WarningBar(title='Выберите основную штриховку'):
            reference = self.__uidoc.Selection.PickObject(ObjectType.Element, MainRegionSelectionFilter())
            return self.__doc.GetElement(reference)

    def pick_regions(self, main_region):
        with forms.WarningBar(title='Выберите штриховки для вырезания'):
            references = self.__uidoc.Selection.PickObjects(
                ObjectType.Element,
                CutRegionSelectionFilter(main_region.Id))
            return [self.__doc.GetElement(ref) for ref in references]

    def get_solids(self, main_region, cutting_regions):
        direction = XYZ.BasisZ
        distance = 1
        main_z = self.get_z(main_region.GetBoundaries()[0])
        cut_solids = []
        for region in cutting_regions:
            loops = region.GetBoundaries()
            z_diff = self.get_z(loops[0]) - main_z
            transform = Transform.CreateTranslation(XYZ(0, 0, -z_diff))
            solid = GeometryCreationUtilities.CreateExtrusionGeometry(
                loops,
                direction,
                distance)
            solid = SolidUtils.CreateTransformed(solid, transform)
            cut_solids.append(solid)
        cut_solids = self.unite_solids(cut_solids)
        main_solid = GeometryCreationUtilities.CreateExtrusionGeometry(
                main_region.GetBoundaries(),
                direction,
                distance)
        return main_solid, cut_solids

    @staticmethod
    def get_z(curve_loop):
        return list(curve_loop)[0].GetEndPoint(0).Z

    def cut_regions(self, main_region, cutting_regions):
        main_solid, cutting_solids = self.get_solids(main_region, cutting_regions)
        result_solids = self.cut_solids(main_solid, cutting_solids)
        result_solids = self.unite_solids(result_solids)
        return self.get_bottom_loops(result_solids)

    def cut_solids(self, first_solid, second_solids):
        result = first_solid
        for solid in second_solids:
            result = BooleanOperationsUtils.ExecuteBooleanOperation(
                result,
                solid,
                BooleanOperationsType.Difference)
        return self.unite_solids([result])

    @staticmethod
    def unite_solids(solids):
        return SolidExtensions.CreateUnitedSolids(solids)

    def create_region(self, type_id, view_id, loops):
        with revit.Transaction('BIM: Вырезание штриховки'):
            FilledRegion.Create(self.__doc, type_id, view_id, loops)

    @staticmethod
    def get_bottom_loops(solids):
        result_solids = [i for i in solids if i is not None and i.Volume > 0]
        faces_lists = [list(solid.Faces) for solid in result_solids]
        faces = [face for face_list in faces_lists for face in face_list]
        bottom_faces = [face for face in faces if face.ComputeNormal(UV()).IsAlmostEqualTo(-XYZ.BasisZ)]
        loops_list = [i.GetEdgesAsCurveLoops() for i in bottom_faces]
        return [loop for loop_list in loops_list for loop in loop_list]

    def delete_element(self, elem_id):
        with revit.Transaction('BIM: Удаление старой штриховки'):
            self.__doc.Delete(elem_id)


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    repo = RevitRepository()
    main_region = repo.pick_region() # type: FilledRegion
    cutting_regions = repo.pick_regions(main_region) # type: list
    loops = repo.cut_regions(main_region, cutting_regions)
    repo.create_region(main_region.GetTypeId(), main_region.OwnerViewId, loops)
    repo.delete_element(main_region.Id)


script_execute()
