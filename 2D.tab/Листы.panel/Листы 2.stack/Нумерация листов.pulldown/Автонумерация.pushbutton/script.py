# -*- coding: utf-8 -*-

from pySpeech.ViewSheets import *

from pyrevit import EXEC_PARAMS
from dosymep_libs.bim4everyone import *

@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    order_view = OrderViewSheetModel(DocumentRepository(__revit__))

    order_view.load_view_sheets()
    order_view.check_uniques_names()
    order_view.order_view_sheets()


script_execute()
