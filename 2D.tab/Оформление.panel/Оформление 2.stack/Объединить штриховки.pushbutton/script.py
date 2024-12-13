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
        with forms.WarningBar(title='Выберите штриховки для объединения'):
            references = self.__uidoc.Selection.PickObjects(
                ObjectType.Element,
                CutRegionSelectionFilter(main_region.Id))
            return [self.__doc.GetElement(ref) for ref in references]

    def get_solids(self, main_region, other_regions):
        direction = XYZ.BasisZ
        distance = 1
        main_z = self.get_z(main_region.GetBoundaries()[0])
        other_solids = []
        for region in other_regions:
            loops = region.GetBoundaries()
            z_diff = self.get_z(loops[0]) - main_z
            transform = Transform.CreateTranslation(XYZ(0, 0, -z_diff))
            solid = GeometryCreationUtilities.CreateExtrusionGeometry(
                loops,
                direction,
                distance)
            solid = SolidUtils.CreateTransformed(solid, transform)
            other_solids.append(solid)
        other_solids = self.unite_solids(other_solids)
        main_solid = GeometryCreationUtilities.CreateExtrusionGeometry(
                main_region.GetBoundaries(),
                direction,
                distance)
        other_solids.append(main_solid)
        return other_solids

    @staticmethod
    def get_z(curve_loop):
        return list(curve_loop)[0].GetEndPoint(0).Z

    def merge_regions(self, main_region, other_regions):
        solids = self.get_solids(main_region, other_regions)
        result_solids = self.unite_solids(solids)
        return self.get_bottom_loops(result_solids)

    @staticmethod
    def unite_solids(solids):
        return list(SolidExtensions.CreateUnitedSolids(solids))

    def create_region(self, type_id, view_id, loops):
        with revit.Transaction('BIM: Объединение штриховок'):
            FilledRegion.Create(self.__doc, type_id, view_id, loops)

    @staticmethod
    def get_bottom_loops(solids):
        result_solids = [i for i in solids if i is not None and i.Volume > 0]
        faces_lists = [list(solid.Faces) for solid in result_solids]
        faces = [face for face_list in faces_lists for face in face_list]
        bottom_faces = [face for face in faces if face.ComputeNormal(UV()).IsAlmostEqualTo(-XYZ.BasisZ)]
        loops_list = [i.GetEdgesAsCurveLoops() for i in bottom_faces]
        return [loop for loop_list in loops_list for loop in loop_list]

    def delete_elements(self, ids):
        with revit.Transaction('BIM: Удаление старых штриховок'):
            for i in ids:
                self.__doc.Delete(i)


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    repo = RevitRepository() # type: RevitRepository
    main_region = repo.pick_region() # type: FilledRegion
    other_regions = repo.pick_regions(main_region) # type: list
    loops = repo.merge_regions(main_region, other_regions)
    repo.create_region(main_region.GetTypeId(), main_region.OwnerViewId, loops)
    ids = [i.Id for i in other_regions]
    ids.append(main_region.Id)
    repo.delete_elements(ids)


script_execute()
