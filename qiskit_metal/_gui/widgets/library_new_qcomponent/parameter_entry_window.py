## dockify
# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Main edit source code window,
based on pyqode.python: https://github.com/pyQode/pyqode.python

@author: Zlatko Minev 2020
"""

from typing import TYPE_CHECKING, Union
from PySide2.QtWidgets import QPushButton
from PySide2.QtWidgets import (QScrollArea, QVBoxLayout, QLabel, QWidget,
                               QHBoxLayout, QLineEdit, QLayout, QComboBox,
                               QMessageBox)
from PySide2.QtCore import Qt
from addict.addict import Dict
from .collapsable_widget import CollapsibleWidget
from collections import OrderedDict
import numpy as np
from inspect import signature
import inspect
from collections import Callable
from ....designs.design_base import QDesign
import importlib
import builtins
import logging
import traceback
import json
import os
import numpy as np
import random
from PySide2 import QtCore, QtGui, QtWidgets
from PySide2.QtCore import Qt
from PySide2.QtWidgets import QDockWidget
from PySide2.QtWidgets import (QAbstractItemView, QApplication, QFileDialog,
                               QLabel, QMainWindow, QMessageBox, QTabWidget)
from pathlib import Path
from ..edit_component.tree_view_options import QTreeView_Options
from .model_view.tree_model_param_entry import TreeModelParamEntry, BranchNode, LeafNode, Node
from .model_view.tree_delegate_param_entry import ParamDelegate
from .parameter_entry_window_ui import Ui_MainWindow
from ...edit_source_ui import Ui_EditSource
import os
import copy
from ..edit_component.component_widget import ComponentWidget
from qiskit_metal.toolbox_python.attr_dict import Dict
from qiskit_metal import designs
if TYPE_CHECKING:
    from ...main_window import MetalGUI


class ParameterEntryWindow(QMainWindow):

    def __init__(self,
                 qcomp_class,
                 design: designs.DesignPlanar,
                 parent=None,
                 gui=None):

        super().__init__(parent)
        self.qcomp_class = qcomp_class
        self._design = design
        self._gui = gui
        self.setWindowTitle("New " + self.qcomp_class.__name__)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.param_dictionary = {}
        self.reset_param_dictionary = {
        }  # set during generate_model_data as a backup in case tree need be reloaded

        self.model = TreeModelParamEntry(self,
                                         self.ui.qcomponent_param_tree_view,
                                         design=self._design)

        self.ui.qcomponent_param_tree_view.setModel(self.model)
        self.ui.qcomponent_param_tree_view.setItemDelegate(ParamDelegate(self))

        # self.ui.qcomponent_param_tree_view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        # self.ui.qcomponent_param_tree_view.setHorizontalScrollMode(
        # QAbstractItemView.ScrollPerPixel)
        self.statusBar().hide()

        ## should be moved to qt designer
        self.ui.create_qcomp_button.clicked.connect(self.instantiate_qcomponent)
        self.ui.add_k_v_row_button.pressed.connect(self.add_k_v_row)
        self.ui.nest_dictionary_button.pressed.connect(self.add_k_dict_row)
        self.ui.remove_button.pressed.connect(self.delete_row)

    def setup_pew(self):
        self.generate_model_data()
        self._setup_help()
        self._setup_source()

    @property
    def qcomponent_file_path(self):
        """Get file path to qcomponent
        """
        component = self.qcomp_class
        module = inspect.getmodule(component)
        filepath = inspect.getfile(module)
        # TypeError
        return filepath

    ## Exception Handling
    class QComponentParameterEntryExceptionDecorators(object):
        """
        All exceptions in QComponentParameterEntry should result in a pop-up window.
        This class contains the decorators that control exception handling for all functions in QComponentParameterEntry
        """
        #
        # @classmethod
        # def log_error(cls, log_owner, exception: Exception, wrapper: Callable,
        #               args, kwargs):
        #     """
        #     Log error manually with whatever logger is currently available. Only used by other QComponentParameterEntryExceptionDecorators decorators
        #     Args:
        #         log_owner: Owner of current logger
        #         exception: exception
        #         wrapper: wrapper function of other QComponentParameterEntryExceptionDecorators decoraters
        #         args: current args for function causing the exception
        #         kwargs: current kwargs for function causing the exception
        #
        #     """
        #     message = traceback.format_exc()
        #     message += '\n\nERROR in QCPE\n' \
        #                + f"\n{' module   :':12s} {wrapper.__module__}" \
        #                + f"\n{' function :':12s} {wrapper.__qualname__}" \
        #                + f"\n{' err msg  :':12s} {exception.__repr__()}" \
        #                + f"\n{' args; kws:':12s} {args}; {kwargs}" \
        #                + "\nTill now I always got by on my own........ (I never really cared until I met you)"
        #     log_owner.logger.error(message)

        @classmethod
        def entry_exception_pop_up_warning(cls, func: Callable):
            """
            Throws up critical QMessageBox with current exception in the event an exception is thrown by func
            Args:
                func: current function causing exceptions - should  be ONLY  qcpe instance methods because decoraters
                assumes arg[0] is a self who has a valid logger

            """

            def wrapper(*args, **kwargs):
                try:

                    return func(*args, **kwargs)
                # if anticipated Exception throw up error window
                except (Exception) as lqce:

                    #cls.log_error(args[0], lqce, func, args, kwargs)
                    args[0].error_pop_up = QMessageBox()

                    error_message = "In function, " + str(
                        func.__name__) + "\n" + str(
                            lqce.__class__.__name__) + ":\n" + str(lqce)

                    args[0].error_pop_up.critical(
                        args[0], "", error_message
                    )  #modality set by critical, Don't set Title -- will NOT show up on MacOs

            return wrapper

    @QComponentParameterEntryExceptionDecorators.entry_exception_pop_up_warning
    def _setup_help(self):
        """Called when we need to set a new help"""

        component = self.qcomp_class
        if component is None:

            raise Exception("No Component found.")

        filepath = self.qcomponent_file_path
        doc_class = self.format_docstr(inspect.getdoc(component))
        doc_init = self.format_docstr(inspect.getdoc(component.__init__))

        text = """<body style="color:white;">"""
        text += f'''
        <div class="h1">Summary:</div>
        <table class="table ComponentHeader">
            <tbody>
                <tr> <th>Name</th> <td>{component.name}</td></tr>
                <tr> <th>Class</th><td>{component.__class__.__name__}</td></tr>
                <tr> <th>Module</th><td>{component.__class__.__module__}</td></tr>
                <tr> <th>Path </th> <td style="text-color=#BBBBBB;"> {filepath}</td></tr>
            </tbody>
        </table>
        '''
        text += f'''
            <div class="h1">Class docstring:</div>
            {doc_class}
            <div class="h1">Init docstring:</div>
            {doc_init}
        '''
        text += "</body>"

        help = QtWidgets.QTextEdit()
        help.setReadOnly(True)
        help.setHtml(text)
        self.ui.tab_help.layout().addWidget(help)

    @QComponentParameterEntryExceptionDecorators.entry_exception_pop_up_warning
    def format_docstr(self, doc: Union[str, None]) -> str:
        """Format a docstring

        Args:
            doc (Union[str, None]): string to format

        Returns:
            str: formatted string
        """

        if doc is None:
            return ''
        doc = doc.strip()
        text = f"""
    <pre>
    <code class="DocString">{doc}</code>
    </pre>
        """
        return text

    @QComponentParameterEntryExceptionDecorators.entry_exception_pop_up_warning
    def _setup_source(self):

        filepath = self.qcomponent_file_path

        text_source = QtWidgets.QTextEdit(self.ui.tab_source)
        text_source.setReadOnly(True)

        text_doc = QtGui.QTextDocument(text_source)
        try:  # For source doc
            import pygments
            from pygments import highlight
            from pygments.formatters import HtmlFormatter
            from pygments.lexers import get_lexer_by_name
        except ImportError as e:
            self._design.logger.error(
                f'Error: Could not load python package \'pygments\'; Error: {e}'
            )
            highlight = None
            HtmlFormatter = None
            get_lexer_by_name = None

        text = Path(filepath).read_text()
        if highlight is None:
            text_doc.setPlainText(text)
        else:
            lexer = get_lexer_by_name("python", stripall=True)
            formatter = HtmlFormatter(linenos='inline')
            self._html_css_lex = formatter.get_style_defs('.highlight')
            text_doc.setDefaultStyleSheet(self._html_css_lex)
            text_html = highlight(text, lexer, formatter)
            text_doc.setHtml(text_html)
        text_source.moveCursor(QtGui.QTextCursor.Start)
        text_source.ensureCursorVisible()
        text_source.setDocument(text_doc)

        self.ui.tab_source.layout().addWidget(text_source)

    @QComponentParameterEntryExceptionDecorators.entry_exception_pop_up_warning
    def add_k_v_row(self):
        #based on what row is highlighed in treeview
        cur_index = self.ui.qcomponent_param_tree_view.currentIndex()

        key = "fake-param" + str(random.randint(0, 1000))

        value = "Cheese"
        self.model.add_new_leaf_node(cur_index, key, value)

    @QComponentParameterEntryExceptionDecorators.entry_exception_pop_up_warning
    def add_k_dict_row(self):
        cur_index = self.ui.qcomponent_param_tree_view.currentIndex()

        fake_dict = "fake-dict" + str(random.randint(0, 1000))
        fakekey = "key"
        fakevalue = "value"
        self.model.add_new_branch_node(cur_index, fake_dict, fakekey, fakevalue)

    @QComponentParameterEntryExceptionDecorators.entry_exception_pop_up_warning
    def delete_row(self):
        cur_index = self.ui.qcomponent_param_tree_view.currentIndex()
        self.model.delete_node(cur_index)

    @QComponentParameterEntryExceptionDecorators.entry_exception_pop_up_warning
    def generate_model_data(self):

        # GET ARGS dict
        param_dict = {}
        class_signature = signature(self.qcomp_class.__init__)

        for _, param in class_signature.parameters.items():
            if param.name != 'self' and param.name != 'design' and param.name != 'kwargs' and param.name != 'args':
                if param.default:
                    param_dict[param.name] = param.default
                else:
                    param_dict[param.name] = create_default_from_type(
                        param.annotation)

        # ADD in DEFAULT OPTIONS

        if 'default_options' in self.qcomp_class.__dict__:
            options = self.qcomp_class.default_options

            if options is not None:
                copied_options = copy.deepcopy(options)
                param_dict['options'] = copied_options

        self.param_dictionary = param_dict
        self.reset_param_dictionary = copy.deepcopy(param_dict)
        self.model.init_load(param_dict)

    @QComponentParameterEntryExceptionDecorators.entry_exception_pop_up_warning
    def instantiate_qcomponent(self):

        self.traverse_model_to_create_dictionary()

        mine = self.qcomp_class(self._design, **self.current_dict)

        if self._gui is not None:  #for the sake of testing, we won't have gui
            self._gui.refresh()
            self._gui.autoscale()

        self.close()

    def traverse_model_to_create_dictionary(self):
        parameter_dict = {}
        r = self.model.root
        self.recursively_get_params(parameter_dict, r)

        self.current_dict = parameter_dict[""]

    def recursively_get_params(self, parent_dict, curNode):

        if isinstance(curNode, LeafNode):

            parent_dict[curNode.name] = curNode.get_real_value()

            return

        c_dict = curNode.get_empty_dictionary()
        parent_dict[curNode.name] = c_dict
        for child in curNode.children:

            self.recursively_get_params(c_dict, child[Node.NODE])


def create_parameter_entry_window(gui: 'MetalGUI',
                                  abs_file_path: str,
                                  parent=None) -> QtWidgets.QWidget:
    """Creates the spawned window that has the edit source
    """
    # GET CLASS

    cur_class = get_class_from_abs_file_path(abs_file_path)
    if cur_class is None:
        gui.logger.error("Unable to get class from abs file: ", abs_file_path)
        return None

    #CREATE TREE

    if not parent:
        parent = gui.main_window  # gui.component_window.ui.tabHelp

    #TODO gui log

    param_window = ParameterEntryWindow(cur_class, gui.design, parent, gui)

    param_window.dock = dockify(param_window, "New " + cur_class.__name__, gui)
    param_window.setup_pew()

    #
    # param_window.ui.textEditHelp.setStyleSheet("""
    # background-color: #f9f9f9;
    # color: #000000;
    #         """)

    param_window.dock.show()
    param_window.dock.raise_()
    param_window.dock.activateWindow()

    return param_window


def dockify(main_window, docked_title, gui):
    """Dockify the given GUI

    Args:
        gui (MetalGUI): the GUI

    Returns:
        QDockWidget: the widget
    """
    ### Dockify
    main_window.dock_widget = QDockWidget(docked_title, gui.main_window)
    dock = main_window.dock_widget
    dock.setWidget(main_window)

    dock.setAllowedAreas(Qt.RightDockWidgetArea)
    dock.setFloating(True)
    dock.resize(1200, 700)

    # Doesnt work
    # dock_gui = self.dock_widget
    # dock_gui.setWindowFlags(dock_gui.windowFlags() & ~QtCore.Qt.WindowStaysOnTopHint)
    gui.logger.info("dockified window: " + docked_title)
    return dock


def get_class_from_abs_file_path(abs_file_path):
    """
    Gets the corresponding class object for the absolute file path to the file containing that class definition
    Args:
        abs_file_path: absolute file path to the file containing the QComponent class definition

    getting class from absolute file path - https://stackoverflow.com/questions/452969/does-python-have-an-equivalent-to-java-class-forname

    """
    qis_abs_path = abs_file_path[abs_file_path.index(__name__.split('.')[0]):]
    qis_mod_path = qis_abs_path.replace(os.sep, '.')[:-len('.py')]

    mymodule = importlib.import_module(qis_mod_path)
    members = inspect.getmembers(mymodule, inspect.isclass)
    class_owner = qis_mod_path.split('.')[-1]
    for memtup in members:
        if len(memtup) > 1:
            if str(memtup[1].__module__).endswith(class_owner):
                return memtup[1]


def create_default_from_type(t: type):
    #yes this is hardcoded - we're all sad about it
    if t == int:
        return 0
    elif t == float:
        return 0.0
    elif t == str:
        return "fake-param-" + str(random.randint(0, 1000))
    elif t == bool:
        return True
    elif t == dict:
        return {
            "false-param":
                "Did you think I wouldn't hear all the things you said about me? \n This is why we can't have! nice  things ~ "
        }  # can't have empty branch nodes
    elif t == OrderedDict:
        return OrderedDict({0: "zeroth"})
    elif t == Dict:
        return Dict(falseparam1=Dict(falseparam2="false-param",
                                     falseparam3="false-param"))

    else:
        return np.ndarray(1)