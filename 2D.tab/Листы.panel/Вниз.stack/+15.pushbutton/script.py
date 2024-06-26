# -*- coding: utf-8 -*-

import clr
clr.AddReference("dosymep.Revit.dll")

import dosymep
clr.ImportExtensions(dosymep.Revit)

from pyrevit import EXEC_PARAMS
from dosymep_libs.bim4everyone import *

from pySpeech.ViewSheets import renumber

@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    doc = __revit__.ActiveUIDocument.Document
    uidoc = __revit__.ActiveUIDocument
    selection = list(__revit__.ActiveUIDocument.GetSelectedElements())

    renumber(15, -1, len(selection), "+15")


script_execute()
