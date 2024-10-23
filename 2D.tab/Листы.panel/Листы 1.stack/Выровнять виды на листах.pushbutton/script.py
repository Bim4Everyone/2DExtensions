# -*- coding: utf-8 -*-
import os.path as op
import re

import clr
clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from Autodesk.Revit.DB import *

from pyrevit import forms
from pyrevit import revit
from pyrevit import script
from pyrevit import EXEC_PARAMS

from dosymep_libs.bim4everyone import *
from dosymep.Bim4Everyone.SharedParams import *


ALIGN_POINT_TOP_LEFT = 'Верх-лево'
ALIGN_POINT_TOP_RIGHT = 'Верх-право'
ALIGN_POINT_CENTER = 'Центр'
ALIGN_POINT_BOTTOM_LEFT = 'Низ-лево'
ALIGN_POINT_BOTTOM_RIGHT = 'Низ-право'

class Option(object):
    def __init__(self, obj, doc, state=False):
        self.state = state
        self.name = obj.GetParamValueOrDefault(BuiltInParameter.VIEW_NAME)
        self.number = obj.GetParamValueOrDefault(BuiltInParameter.VIEWPORT_SHEET_NUMBER)
        self.viewName = '{} - {}'.format(self.number, self.name)
        self.obj = obj
        self.str_number = ''.join([i for i in self.number if not i.isdigit()])
        num = [int(x) for x in re.findall(r'\d+', self.number)]
        self.priority = num[0] if len(num) > 0 else 1000

        sheet = doc.GetElement(obj.OwnerViewId)
        self.sheet_album = sheet.GetParamValueOrDefault(SharedParamsConfig.Instance.AlbumBlueprints)

    def __nonzero__(self):
        return self.state

    def __str__(self):
        return self.name


class SelectPortViewForm(forms.TemplateUserInputWindow):
    xaml_source = op.join(op.dirname(__file__), 'SelectPortViewForm.xaml')

    def _setup(self, **kwargs):
        self.checked_only = kwargs.get('checked_only', True)

        View2align2 = kwargs.get('View2align2')
        self.View2align2.ItemsSource = View2align2
        self.View2align2.SelectedItem = View2align2[0]

        alignment_points = [ALIGN_POINT_TOP_LEFT,
                            ALIGN_POINT_TOP_RIGHT,
                            ALIGN_POINT_CENTER,
                            ALIGN_POINT_BOTTOM_LEFT,
                            ALIGN_POINT_BOTTOM_RIGHT]
        self.Height = 650
        for point in alignment_points:
            self.alignmentPoint.AddText(point)
        self.alignmentPoint.SelectedItem = alignment_points[2]
        self._list_options()

    def _verify_context(self):
        new_context = []
        for item in self._context:
            if not hasattr(item, 'state'):
                new_context.append(BaseCheckBoxItem(item))
            else:
                new_context.append(item)

        self._context = new_context

    def _list_options(self, checkbox_filter=None):
        if checkbox_filter:
            self.checkall_b.Content = 'Check'
            self.uncheckall_b.Content = 'Uncheck'
            self.toggleall_b.Content = 'Toggle'
            checkbox_filter = checkbox_filter.lower()
            self.Views2align.ItemsSource = \
                [checkbox for checkbox in self._context
                 if checkbox_filter in checkbox.name.lower()]
        else:
            self.checkall_b.Content = 'Выбрать все'
            self.uncheckall_b.Content = 'Снять выбор'
            self.toggleall_b.Content = 'Инвертировать'
            self.Views2align.ItemsSource = self._context

    def _set_states(self, state=True, flip=False, selected=False):
        all_items = self.Views2align.ItemsSource
        if selected:
            current_list = self.Views2align.SelectedItems
        else:
            current_list = self.Views2align.ItemsSource
        for checkbox in current_list:
            if flip:
                checkbox.state = not checkbox.state
            else:
                checkbox.state = state

        # push list view to redraw
        self.Views2align.ItemsSource = None
        self.Views2align.ItemsSource = all_items

    def toggle_all(self, sender, args):
        """Handle toggle all button to toggle state of all check boxes."""
        self._set_states(flip=True)

    def check_all(self, sender, args):
        """Handle check all button to mark all check boxes as checked."""
        self._set_states(state=True)

    def uncheck_all(self, sender, args):
        """Handle uncheck all button to mark all check boxes as un-checked."""
        self._set_states(state=False)

    def check_selected(self, sender, args):
        """Mark selected checkboxes as checked."""
        self._set_states(state=True, selected=True)

    def uncheck_selected(self, sender, args):
        """Mark selected checkboxes as unchecked."""
        self._set_states(state=False, selected=True)

    def enable_accuracy(self, sender, args):
        """Mark selected checkboxes as unchecked."""
        self.accuracy.IsEnabled = True

    def disenable_accuracy(self, sender, args):
        """Mark selected checkboxes as unchecked."""
        self.accuracy.IsEnabled = False

    def button_select(self, sender, args):
        """Handle select button click."""
        if self.checked_only:
            self.response = [x for x in self._context if x.state]
        else:
            self.response = self._context
        self.response = {'ports_toalign': self.response,
                         'port_toalignto': self.View2align2.SelectedItem,
                         'alignmentPoint': self.alignmentPoint.SelectedItem
                         }
        self.Close()



@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    doc = __revit__.ActiveUIDocument.Document
    active_view = doc.ActiveView
    if not isinstance(active_view, ViewSheet):
        forms.alert("Открытый вид не является листом.", exitscript=True)

    all_view_ports = FilteredElementCollector(doc).OfClass(Viewport)
    all_view_ports = [Option(x, doc) for x in all_view_ports]
    all_view_ports = sorted(all_view_ports, key=lambda x: (x.sheet_album, x.str_number, x.priority))

    active_view_view_port_ids = active_view.GetAllViewports()
    active_view_view_ports = [doc.GetElement(x) for x in active_view_view_port_ids]
    active_view_view_ports = [Option(x, doc) for x in active_view_view_ports]
    active_view_view_ports = sorted(active_view_view_ports, key=lambda x: (x.str_number, x.priority))

    if len(active_view_view_ports) == 0:
        forms.alert("В проекте отсутствуют листы с размещенными видовыми экранами.", exitscript=True)

    res = SelectPortViewForm.show(all_view_ports, title='Выравнивание видов', View2align2=active_view_view_ports)
    if res:
        ports_toalign = [x for x in res['ports_toalign']]
        port_toalignto = res['port_toalignto']
        alignmentPoint = res['alignmentPoint']
    else:
        script.exit()

    primaryViewPort = port_toalignto.obj

    with revit.Transaction("BIM: Выравнивание видов"):
        for port in ports_toalign:
            currentViewPort = port.obj
            if alignmentPoint == ALIGN_POINT_TOP_RIGHT:
                d1 = primaryViewPort.GetBoxOutline().MaximumPoint  # MinimumPoint
                d2 = currentViewPort.GetBoxOutline().MaximumPoint
                delta = d1 - d2
                newCenter = currentViewPort.GetBoxCenter().Add(delta)
                currentViewPort.SetBoxCenter(newCenter)

            elif alignmentPoint == ALIGN_POINT_TOP_LEFT:
                p_Max = primaryViewPort.GetBoxOutline().MaximumPoint  # MinimumPoint
                p_Min = primaryViewPort.GetBoxOutline().MinimumPoint
                c_Max = currentViewPort.GetBoxOutline().MaximumPoint
                c_Min = currentViewPort.GetBoxOutline().MinimumPoint

                delta = p_Max - c_Max
                P_delta_X = abs(p_Max.X - p_Min.X)
                C_delta_X = abs(c_Max.X - c_Min.X)

                newCenter = currentViewPort.GetBoxCenter().Add(delta).Subtract(XYZ(P_delta_X - C_delta_X, 0, 0))
                currentViewPort.SetBoxCenter(newCenter)

            elif alignmentPoint == ALIGN_POINT_BOTTOM_LEFT:
                P_Min = primaryViewPort.GetBoxOutline().MinimumPoint  # MinimumPoint
                c_Min = currentViewPort.GetBoxOutline().MinimumPoint
                delta = c_Min - P_Min
                newCenter = currentViewPort.GetBoxCenter().Subtract(delta)
                currentViewPort.SetBoxCenter(newCenter)

            elif alignmentPoint == ALIGN_POINT_BOTTOM_RIGHT:
                p_Max = primaryViewPort.GetBoxOutline().MaximumPoint  # MinimumPoint
                p_Min = primaryViewPort.GetBoxOutline().MinimumPoint  # MinimumPoint
                c_Max = currentViewPort.GetBoxOutline().MaximumPoint
                c_Min = currentViewPort.GetBoxOutline().MinimumPoint
                delta = c_Min - p_Min
                P_delta_X = abs(p_Max.X - p_Min.X)
                C_delta_X = abs(c_Max.X - c_Min.X)
                newCenter = currentViewPort.GetBoxCenter().Subtract(delta).Add(XYZ(P_delta_X - C_delta_X, 0, 0))
                currentViewPort.SetBoxCenter(newCenter)

            elif alignmentPoint == ALIGN_POINT_CENTER:
                p_Center = primaryViewPort.GetBoxCenter()
                c_Center = currentViewPort.GetBoxCenter()
                delta = c_Center - p_Center
                newCenter = currentViewPort.GetBoxCenter().Subtract(delta)
                currentViewPort.SetBoxCenter(newCenter)


script_execute()

