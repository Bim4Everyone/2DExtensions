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


def get_bottom_loops(solids, up_vector):
    result_solids = [i for i in solids if i is not None and i.Volume > 0]
    faces_lists = [list(solid.Faces) for solid in result_solids]
    faces = [face for face_list in faces_lists for face in face_list]
    bottom_faces = [face for face in faces if face.ComputeNormal(UV()).IsAlmostEqualTo(-up_vector)]
    loops_list = [i.GetEdgesAsCurveLoops() for i in bottom_faces]
    return [loop for loop_list in loops_list for loop in loop_list]

def get_point(curve_loop):
    return list(curve_loop)[0].GetEndPoint(0)

def unite_solids(solids):
    if solids:
        return SolidExtensions.CreateUnitedSolids(solids)

def get_solids(main_region, cutting_regions):
    direction = get_normal(main_region) # type: XYZ
    distance = 1
    main_point = get_point(main_region.GetBoundaries()[0])
    cut_solids = []
    for region in cutting_regions:
        loops = region.GetBoundaries()
        distance_diff = (get_point(loops[0]) - main_point).DotProduct(direction) # type: XYZ
        transform = Transform.CreateTranslation(direction * (-distance_diff))
        solid = GeometryCreationUtilities.CreateExtrusionGeometry(
            loops,
            direction,
            distance)
        solid = SolidUtils.CreateTransformed(solid, transform)
        cut_solids.append(solid)
    cut_solids = unite_solids(cut_solids)
    main_solid = GeometryCreationUtilities.CreateExtrusionGeometry(
            main_region.GetBoundaries(),
            direction,
            distance)
    return main_solid, cut_solids

def get_normal(region):
    return region.GetBoundaries()[0].GetPlane().Normal # type: XYZ

def pick_region(title):
    with forms.WarningBar(title=title):
        reference = HOST_APP.uidoc.Selection.PickObject(ObjectType.Element, MainRegionSelectionFilter())
        return HOST_APP.doc.GetElement(reference)

def pick_regions(main_region, title):
    with forms.WarningBar(title=title):
        references = HOST_APP.uidoc.Selection.PickObjects(
            ObjectType.Element,
            CutRegionSelectionFilter(main_region))
        return [HOST_APP.doc.GetElement(ref) for ref in references]

def create_region(type_id, view_id, loops, title):
    if loops:
        with revit.Transaction(title):
            FilledRegion.Create(HOST_APP.doc, type_id, view_id, loops)

def delete_element(elem_id, title):
    with revit.Transaction(title):
        HOST_APP.doc.Delete(elem_id)

def delete_elements(ids, title):
    if ids:
        with revit.Transaction(title):
            for i in ids:
                HOST_APP.doc.Delete(i)


class CutRegionSelectionFilter(ISelectionFilter):
    def __init__(self, main_region):
        self.__id = main_region.Id
        self.__normal = get_normal(main_region)
        self.__n_normal = self.__normal.Negate()

    def AllowElement(self, elem):
        return (isinstance(elem, FilledRegion)
                and (elem.Id != self.__id)
                and (get_normal(elem).IsAlmostEqualTo(self.__normal)
                or get_normal(elem).IsAlmostEqualTo(self.__n_normal)))

    def AllowReference(self, ref, point):
        return False


class MainRegionSelectionFilter(ISelectionFilter):
    def AllowElement(self, elem):
        return isinstance(elem, FilledRegion)

    def AllowReference(self, ref, point):
        return False
