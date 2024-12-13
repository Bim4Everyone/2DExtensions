# -*- coding: utf-8 -*-
import os.path as op
import os
import sys
import clr
import math

clr.AddReference('System')
clr.AddReference("System.Windows.Forms")
from System.Windows.Forms import MessageBox
from System.Collections.Generic import List
from Autodesk.Revit.DB import *
from Autodesk.Revit.Creation import ItemFactoryBase
from Autodesk.Revit.UI.Selection import PickBoxStyle
from Autodesk.Revit.UI import RevitCommandId, PostableCommand

from pyrevit import revit
from pyrevit import forms
from pyrevit import EXEC_PARAMS
from dosymep_libs.bim4everyone import *

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app = __revit__.Application
view = __revit__.ActiveUIDocument.ActiveGraphicalView
view = doc.ActiveView

geometryOptions = Options()
geometryOptions.ComputeReferences = True
geometryOptions.View = view

EPS = 1E-9
GRAD_EPS = math.radians(0.01)


class Utils:
    @staticmethod
    def det(a, b, c, d):
        return a * d - b * c

    @staticmethod
    def between(a, b, c):
        return min(a, b) <= c + EPS and c <= max(a, b) + EPS

    @staticmethod
    def intersect_1(a, b, c, d):
        if (a > b):
            a, b = b, a
        if (c > d):
            c, d = d, c
        return max(a, c) <= min(b, d)

    @staticmethod
    def intersect(a, b, c, d):
        A1 = a.Y - b.Y
        B1 = b.X - a.X
        C1 = -A1 * a.X - B1 * a.Y
        A2 = c.Y - d.Y
        B2 = d.X - c.X
        C2 = -A2 * c.X - B2 * c.Y
        zn = Utils.det(A1, B1, A2, B2)
        if (zn != 0):
            x = -Utils.det(C1, B1, C2, B2) * 1. / zn
            y = -Utils.det(A1, C1, A2, C2) * 1. / zn
            return Utils.between(a.X, b.X, x) and Utils.between(a.Y, b.Y, y) and Utils.between(c.X, d.X,
                                                                                               x) and Utils.between(c.Y,
                                                                                                                    d.Y,
                                                                                                                    y)
        else:
            return Utils.det(A1, C1, A2, C2) == 0 and Utils.det(B1, C1, B2, C2) == 0 and Utils.intersect_1(a.X, b.X,
                                                                                                           c.X,
                                                                                                           d.X) and Utils.intersect_1(
                a.Y, b.Y, c.Y, d.Y)

    @staticmethod
    def isEqualAngle(a, b):
        return abs(a - b) < GRAD_EPS

    @staticmethod
    def isEqual(a, b):
        return abs(a - b) < EPS

    @staticmethod
    def isParallel(a, b):
        angle = a.AngleTo(b);
        return GRAD_EPS > angle or Utils.isEqualAngle(angle, math.pi)

    @staticmethod
    def isNormal(a, b):
        angle = abs(a.AngleTo(b) - math.pi / 2);
        return GRAD_EPS > angle or Utils.isEqualAngle(angle, math.pi)


class CashLine:
    def __init__(self, object):
        self.object = object
        self.line = self.object.Location.Curve
        self.start = self.line.Tessellate()[0]
        self.end = self.line.Tessellate()[1]
        self.id = self.object.Id

        self.direction = self.line.Direction


class CashWall:
    def __init__(self, object):
        self.object = object
        self.box = self.object.BoundingBox[view]
        self.start = self.box.Min
        self.end = self.box.Max
        self.id = self.object.Id
        self.pairs = []
        self.pairs.append([self.start, XYZ(self.start.X, self.end.Y, 0)])
        self.pairs.append([self.start, XYZ(self.end.X, self.start.Y, 0)])
        self.pairs.append([self.end, XYZ(self.start.X, self.end.Y, 0)])
        self.pairs.append([self.end, XYZ(self.end.X, self.start.Y, 0)])

        geometry = self.object.get_Geometry(geometryOptions)
        self.faces = []
        for geometryElement in geometry:
            if isinstance(geometryElement, Solid):
                for geomFace in geometryElement.Faces:
                    self.faces.append(geomFace)

    def isIntersect(self, line):
        return any([Utils.intersect(line.start, line.end, x[0], x[1]) for x in self.pairs])

    def getNormalReferences(self, line):
        res = []

        for face in self.getNormalFaces(line):
            res.append(face.Reference)

        return res

    def getNormalFaces(self, line):
        res = []

        for face in self.faces:
            if face.Intersect(line.line) == SetComparisonResult.Overlap and Utils.isParallel(face.FaceNormal,
                                                                                             line.direction):
                res.append(face)

        return res

    def hasCylindricalFace(self):
        for face in self.faces:
            if isinstance(face, CylindricalFace):
                return True
        return False

    def getReferences(self, line):
        return self.getNormalReferences(line)


class CashGrid:
    def __init__(self, obj):
        self.object = obj
        self.id = self.object.Id

        geometry = self.object.Geometry[geometryOptions]
        lineIterator = geometry.GetEnumerator()
        lineIterator.MoveNext()
        self.line = lineIterator.Current

        self.start = self.line.Tessellate()[0]
        self.end = self.line.Tessellate()[1]

    def getNormalReferences(self, line):
        res = []
        directionLine = line.direction

        direction = self.line.Direction

        if Utils.isNormal(directionLine, direction):
            res.append(self.line.Reference)

        return res

    def getRange(self, line):
        return self.line.Project(line.start).Distance

    def isIntersect(self, line):
        return Utils.intersect(line.start, line.end, self.start, self.end)

    def getReferences(self, line):
        return self.getNormalReferences(line)

    def getNormalFaces(self, line):
        res = []

        return res


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    grids = [CashGrid(x) for x in FilteredElementCollector(doc, view.Id).OfClass(Grid).ToElements()]
    detail_lines = [CashLine(x) for x in revit.get_selection().elements if isinstance(x, DetailLine)]

    if not detail_lines:
        with forms.WarningBar(title="Выберите линии"):
            detail_lines = revit.pick_elements_by_category(BuiltInCategory.OST_Lines, "Выберите линии")
            if not detail_lines:
                forms.alert("Нужно выбрать хотя бы одну линию.", exitscript=True)

            detail_lines = [CashLine(x) for x in detail_lines]

    with revit.Transaction("BIM: Оси"):
        for detail_line in detail_lines:
            references = ReferenceArray()

            intersected_girds = []
            for grid in grids:
                if grid.isIntersect(detail_line):
                    intersected_girds.append(grid)

            maximum_ranged_elements = [intersected_girds[0].getReferences(detail_line),
                                       intersected_girds[0].getReferences(detail_line)]

            distance = 0
            for grid in intersected_girds:
                for grid2 in intersected_girds:
                    distance_temp = grid.getRange(grid2)
                    if distance_temp > distance:
                        distance = distance_temp
                        maximum_ranged_elements = [grid.getReferences(detail_line)[0],
                                                   grid2.getReferences(detail_line)[0]]

            ranged_references = ReferenceArray()
            ranged_references.Append(maximum_ranged_elements[0])
            ranged_references.Append(maximum_ranged_elements[1])

            for grid in intersected_girds:
                for reference in grid.getReferences(detail_line):
                    references.Append(reference)

            line = Line.CreateBound(detail_line.start, detail_line.end)

            line_tessellated = line.Tessellate()
            new_start = XYZ(line_tessellated[0].X - 20, line_tessellated[0].Y + 20, line_tessellated[0].Z)
            new_finish = XYZ(line_tessellated[1].X - 20, line_tessellated[1].Y + 20, line_tessellated[1].Z)
            maximum_ranged_line = Line.CreateBound(new_start, new_finish)

            doc.Create.NewDimension(view, line, references)
            doc.Create.NewDimension(view, maximum_ranged_line, ranged_references)

            doc.Delete(detail_line.id)


script_execute()
