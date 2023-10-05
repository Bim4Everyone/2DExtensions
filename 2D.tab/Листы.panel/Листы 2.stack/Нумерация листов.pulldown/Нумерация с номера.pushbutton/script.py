# -*- coding: utf-8 -*-

from pyrevit import forms
from pyrevit import script
from pyrevit import EXEC_PARAMS

from pySpeech.ViewSheets import *
from dosymep_libs.bim4everyone import *

@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    uiDocument = __revit__.ActiveUIDocument
    document = uiDocument.Document

    result = forms.ask_for_string(
        default='1',
        prompt='Введите число с которого требуется начать нумерацию.',
        title='Автонумерация'
    )

    if not result:
        script.exit()

    if not result.isdigit():
        forms.alert("Было введено не число.", exitscript=True)

    order_view = OrderViewSheetModel(DocumentRepository(__revit__), int(result))

    order_view.LoadSelectedViewSheets()
    order_view.CheckUniquesNames()

    order_view.OrderViewSheets()


script_execute()
