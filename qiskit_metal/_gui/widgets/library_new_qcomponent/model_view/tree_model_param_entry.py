# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""
Tree model for Param Entry Window
"""


from PySide2 import QtCore
from PySide2.QtGui import QFont
from PySide2.QtWidgets import QTreeView, QWidget
from PySide2.QtCore import QAbstractItemModel, QModelIndex, QTimer, Qt
import ast
from typing import Union, TYPE_CHECKING
import queue
from PySide2.QtCore import QAbstractItemModel, QModelIndex, QTimer, Qt
from PySide2.QtWidgets import (QAbstractItemView, QApplication, QFileDialog,
                               QWidget, QTreeView, QLabel, QMainWindow,
                               QMessageBox, QTabWidget, QComboBox)
from collections import OrderedDict
from addict import Dict

import numpy as np
import json
import builtins
from typing import TYPE_CHECKING
from qiskit_metal.designs.design_base import QDesign
import time

# List of children given as [(childname_0, childnode_0), (childname_1, childnode_1), ...]
# Where childname_i corresponds to KEY and childnode_i corresponds to NODE


def get_nested_dict_item(dic: dict, key_list: list):
    """
    Get a nested dictionary item.
    If key_list is empty, return dic itself.

    Args:
        dic (dict): dictionary of items
        key_list (list): list of keys

    Returns:
        dict: nested dictionary

    .. code-block:: python
        :linenos:

        myDict = Dict(aa=Dict(x1={'dda':34},y1='Y',z='10um'),
            bb=Dict(x2=5,y2='YYYsdg',z='100um'))
        key_list = ['aa', 'x1', 'dda']
        [get_dict_item](myDict, key_list)
        returns 34

    """
    if key_list:
        for k in key_list:
            if k not in dic:
                raise Exception(f"CANAOT FIND ERROR{k} not in {dic}!!! :( ")
            dic = dic[k]

    return dic


class Node:
    KEY, NODE = range(2)

    def update_name(self, new_name):
        self.name = new_name
        self.parent.update_child(self)


class BranchNode(Node):
    """
    A BranchNode object has a nonzero number of child nodes.
    These child nodes can be either BranchNodes or LeafNodes.

    It is uniquely defined by its name, parent node, and list of children.
    The list of children consists of tuple pairs of the form (nodename_i, node_i),
    where the former is the name of the child node and the latter is the child node itself.
    KEY (=0) and NODE (=1) identify their respective positions within each tuple pair.
    """

    def __init__(self, name: str, parent=None, cur_type=dict):
        """
        Args:
            name (str): Name of this branch
            parent ([type]): The parent (Default: None)
            data (dict): Node data (Default: None)
        """
        super(BranchNode, self).__init__()
        self.name = name
        self.parent = parent
        self.children = []
        self.type = cur_type.__name__

    def get_type_combobox(self, parent: QWidget):

        return self.BranchTypeComboBox(parent)

    class BranchTypeComboBox(QComboBox):
        orderedDict = OrderedDict.__name__
        rdict = dict.__name__
        addict = Dict.__name__

        branch_type_names = {orderedDict, rdict, addict}
        branch_types = {OrderedDict, dict, Dict}
        type_dictionary = {rdict: dict, orderedDict: OrderedDict, addict: Dict}
        """
        Contains all possible types for values in a DEB
        """

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAutoFillBackground(True)  # must be set for adding to tree
            for d in self.branch_type_names:
                self.addItem(d)

        def getType(self):
            if self.currentText() in self.type_dictionary:
                return self.type_dictionary[self.currentText()]

        def getTypeName(self):
            return self.currentText()

        def setCurrentText(self, text):

            new_ind = self.findText(text)
            if new_ind == -1:
                new_ind = 0
            self.setCurrentIndex(new_ind)
            return self.currentText()

    def get_empty_dictionary(self):
        if self.type == self.BranchTypeComboBox.orderedDict:
            return OrderedDict()
        return dict()

    def __len__(self):
        """
        Gets the number of children

        Returns:
            int: the number of children this node has
        """
        return len(self.children)

    def childAtRow(self, row: int):
        """Gets the child at the given row

        Args:
            row (int): the row

        Returns:
            Node: The node at the row
        """
        if 0 <= row < len(self.children):
            return self.children[row][self.NODE]

    def rowOfChild(self, child):
        """Gets the row of the given child

        Args:
            child (Node): the child

        Returns:
            int: Row of the given child.  -1 is returned if the child is not found.
        """
        for i, (_, childnode) in enumerate(self.children):
            if child == childnode:
                return i
        return -1

    def childWithKey(self, key):
        """Gets the child with the given key

        Args:
            key (str): the key

        Returns:
            Node: The child with the same name as the given key.
            None is returned if the child is not found
        """
        for childname, childnode in self.children:
            if key == childname:
                return childnode
        return None

    def insertChild(self, child):
        """
        Insert the given child

        Args:
            child (Node): the child
        """
        child.parent = self
        self.children.append((child.name, child))

    def update_child(self, child_node):
        row = self.rowOfChild(child_node)
        self.children[row] = (child_node.name, child_node)

    def hasLeaves(self):
        """Do I have leaves?

        Returns:
            bool: True is I have leaves, False otherwise
        """
        if not self.children:
            return False
        return isinstance(self.children[self.KEY][self.NODE], LeafNode)


class NpEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super().default(obj)


class LeafNode(Node):
    """
    A LeafNode object has no children but consists of a key-value pair, denoted by
    name and value, respectively.

    It is uniquely identified by its root-to-leaf path, which is a list of keys
    whose positions denote their nesting depth (shallow to deep).
    """

    def __init__(self, name: str, value, parent=None):
        """
        Args:
            name (str): Label for the leaf node
            parent (Node): The parent (Default: None)
            path (list): Node path (Default: None)
        """
        super(LeafNode, self).__init__()
        self.parent = parent
        self.name = name
        self.type = type(value).__name__
        self.value = self._get_display_value(value)

    def get_type_combobox(self, parent: QWidget):

        return self.LeafTypeComboBox(parent)

    class LeafTypeComboBox(QComboBox):
        """
        Contains all possible types for values in a DEB
        """
        npArr = "ndarray"
        pylist = "list"
        customFromStringItems = {
            npArr: lambda a: np.array(json.loads(a)),
            pylist: lambda a: json.loads(a),
        }
        customToStringItems = {
            npArr: lambda a: json.dumps(a, cls=NpEncoder),
            pylist: lambda a: json.dumps(a, cls=NpEncoder),
        }

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAutoFillBackground(True)  # must be set for adding to tree
            self.addItem("str")
            self.addItem("float")
            self.addItem("int")
            self.addItem("bool")

            self.addItem(self.npArr)
            self.addItem(self.pylist)
            self.npEnc = NpEncoder

        def getType(self):
            if self.currentText() in self.customFromStringItems:

                return self.customFromStringItems[self.currentText()]

            return getattr(builtins, self.currentText())

        def getTypeName(self):
            return self.currentText()

        def setCurrentText(self, text: str):
            new_ind = self.findText(text)
            if new_ind == -1:
                new_ind = 0
            self.setCurrentIndex(new_ind)
            return self.currentText()

    def _get_display_value(self, value):

        if self.type in self.LeafTypeComboBox.customToStringItems:
            # TODO ask Thomas is NpEncoder loses important sigfigs
            return self.LeafTypeComboBox.customToStringItems[self.type](value)
        return str(value)

    def get_real_value(self):
        if self.type in self.LeafTypeComboBox.customFromStringItems:
            val = self.LeafTypeComboBox.customFromStringItems[self.type](
                self.value)
            return val

        cur_type = getattr(builtins, self.type)
        if cur_type == bool:
            if self.value.lower() in "true":
                value = True
            else:
                value = False
        else:
            value = cur_type(self.value)
        return value


class TreeModelParamEntry(QAbstractItemModel):
    """
    Tree model for a general hierarchical dataset.

    This class extends the `QAbstractItemModel` class.
    It is part of the model-view-controller (MVC) architecture; see
    https://doc.qt.io/qt-5/qabstractitemmodel.html

    Access using ``gui.component_window.model``.
    """

    __refreshtime = 500  # 0.5 second refresh time
    NAME = 0
    VALUE = 1
    PARSED = 2
    TYPE = 3

    def __init__(self,
                 parent: QWidget,
                 view: QTreeView,
                 data_dict: OrderedDict = {},
                 design: 'QDesign' = None):
        """
        Editable table with drop-down rows for a generic qcomponent menu.
        Organized as a tree model where child nodes are more specific properties
        of a given parent node.

        Args:
            parent (QWidget): The parent widget
            view:  Model's related QTreeView
            data_dict: Data to be stored in the model's tree
            design: Current design using the model
        """
        super().__init__(parent=parent)
        self._rowCount = -1
        self.root = BranchNode('')
        self.view = view
        self._design = design
        self.headers = ['Name', 'Value']
        self._start_timer()
        self.headers = ['Name', 'Value', 'Parsed Value',
                        "Type"]  # 3 columns instead of 2
        self.init_load(data_dict)

    def add_new_leaf_node(self, cur_index: QModelIndex, key, value=None):
        """
        Add new leaf node to model's backing tree structure
        Args:
            cur_index: Index of parent of new leaf
            key: Key value in leaf node's key-value pair
            value: Value in lead node's key-value pair

        Returns:

        """
        parent_node = self.nodeFromIndex(cur_index)

        if isinstance(parent_node, LeafNode):
            return

        parent_node.insertChild(LeafNode(key, value, parent=parent_node))

        op = self.get_path_of_expanded_items()

        self.reload()
        self.expand_items_in_paths(op)

    def add_new_branch_node(self,
                            cur_index: QModelIndex,
                            key,
                            fake_key,
                            fake_value=None):
        """
        Adds new branch node to model's backing tree
        Args:
            cur_index: Index of parent of new branch
            key: Key value, aka, name of new branch
            fake_key: Placeholder leaf's key since QTreeView cannot display childless BranchNodes
            fake_value: Placeholder leaf's value since QTreeView cannot display childless BranchNodes

        """
        parent_node = self.nodeFromIndex(cur_index)
        if isinstance(parent_node, LeafNode):
            return

        new_node = BranchNode(key, parent_node)
        new_node.insertChild(LeafNode(fake_key, fake_value, new_node))
        parent_node.insertChild(new_node)
        op = self.get_path_of_expanded_items()

        self.reload()
        self.expand_items_in_paths(op)

    def delete_node(self, cur_index: QModelIndex):
        """
        Removes node from backing tree
        Args:
            cur_index: Index of node to be removed from backing tree

        Returns:

        """
        cur_node = self.nodeFromIndex(cur_index)

        if cur_node == self.root:

            raise Exception("Don't delete the everything pls")
        # remove from parent
        if (cur_node.name, cur_node) in cur_node.parent.children:

            cur_node.parent.children.remove((cur_node.name, cur_node))

        op = self.get_path_of_expanded_items()

        self.dataChanged.emit(cur_index, cur_index)
        self.reload()
        self.expand_items_in_paths(op)

    def _start_timer(self):
        """
        Start and continuously refresh timer in background to keep
        the total number of rows up to date.
        """
        self.timer = QTimer(self)
        self.timer.start(self.__refreshtime)
        self.timer.timeout.connect(self.auto_refresh)

    def auto_refresh(self):
        """
        Check to see if the total number of rows has been changed. If so,
        completely rebuild the model and tree.
        """
        # TODO: Check if new nodes have been added; if so, rebuild model.
        newRowCount = self.rowCount(self.createIndex(0, 0))
        if self._rowCount != newRowCount:
            self.modelReset.emit()
            self._rowCount = newRowCount

    def getPaths(self, curdict: OrderedDict, curpath: list):
        """Recursively finds and saves all root-to-leaf paths in model"""

        for k, v in curdict.items():
            if type(v) in BranchNode.BranchTypeComboBox.branch_types:
                self.getPaths(v, curpath + [k])
            else:
                self.paths.append(curpath + [k, v])

    def reload(self):
        """ Sends out a signal forcing QTreeView to completely refresh"""
        self.beginResetModel()
        self.endResetModel()

    def init_load(self, data_dict: dict):
        """Builds a tree from a dictionary (data_dict)"""

        if len(data_dict) < 1:
            return
        self.beginResetModel()

        # Clear existing tree paths if any
        self.root.children.clear()

        # Construct the paths -> sets self.paths
        self.paths = []
        try:
            self.getPaths(data_dict, [])
        except Exception as e:
            self._design.logger.error(
                f"Unable parse given parameters to make tree model: {e}")

        for path in self.paths:
            root = self.root
            branch = None
            # Combine final name and value for leaf node,
            # so stop at 2nd to last element of each path
            for key in path[:-2]:
                # Look for childnode with the name 'key'. If it's not found, create a new branch.
                branch = root.childWithKey(key)
                if not branch:
                    dict_type = type(
                        get_nested_dict_item(data_dict,
                                             path[:path.index(key) + 1]))

                    branch = BranchNode(key, parent=root, cur_type=dict_type)
                    root.insertChild(branch)
                root = branch
            # If a LeafNode resides in the outermost dictionary, the above for loop is bypassed.
            # [Note: This happens when the root-to-leaf path length is just 2.]
            # In this case, add the LeafNode right below the master root.
            # Otherwise, add the LeafNode below the final branch.
            root.insertChild(LeafNode(path[-2], path[-1], parent=root))

        # Emit a signal since the model's internal state
        # (e.g. persistent model indexes) has been invalidated.
        self.endResetModel()

    def rowCount(self, parent: QModelIndex):
        """Get the number of rows

        Args:
            parent (QModelIndex): The parent

        Returns:
            int: The number of rows
        """
        # If there is no component, then show placeholder text
        if len(self.root.children) < 1:
            return 0

        else:
            ###
            # Count number of child nodes belonging to the parent.
            node = self.nodeFromIndex(parent)
            if (node is None) or isinstance(node, LeafNode):
                return 0

            return len(node)

    def columnCount(self, parent: QModelIndex = None):
        """Get the number of columns

        Args:
            parent (QModelIndex): The parent

        Returns:
            int: The number of columns
        """
        return len(self.headers)

    def data(self, index: QModelIndex, role: Qt.ItemDataRole = Qt.DisplayRole):
        """Gets the node data

        Args:
            index (QModelIndex): index to get data for
            role (Qt.ItemDataRole): the role (Default: Qt.DisplayRole)

        Returns:
            object: fetched data
        """
        if not index.isValid():
            return None

        # The data in a form suitable for editing in an editor. (QString)
        if role == Qt.EditRole:
            return self.data(index, Qt.DisplayRole)

        # Bold the first
        if (role == Qt.FontRole) and (index.column() == self.NAME):
            font = QFont()
            font.setBold(True)
            return font

        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignTop | Qt.AlignLeft)

        if role == Qt.DisplayRole:
            node = self.nodeFromIndex(index)
            if node:
                # try:
                #
                # except Exception as e:
                #     pass
                # the first column is either a leaf key or a branch
                # the second column is always a leaf value or for a branch is ''.
                if isinstance(node, BranchNode):
                    # Handle a branch (which is a nested subdictionary, which can be expanded)
                    if index.column() == self.NAME:
                        return node.name
                    elif index.column() == self.TYPE:
                        return node.type
                    return ''
                # We have a leaf
                elif index.column() == self.NAME:
                    return str(node.name)  # key
                elif index.column() == self.VALUE:
                    return str(node.value)  # value
                elif index.column() == self.PARSED:
                    # TODO: If the parser fails, this can throw an error
                    return str(self._design.parse_value(node.value))
                elif index.column() == self.TYPE:
                    return node.type

                else:
                    return None

        return None

    def setData(self,
                index: QModelIndex,
                value,
                role: Qt.ItemDataRole = Qt.EditRole) -> bool:
        """Set the LeafNode value and corresponding data entry to value.
        Returns true if successful; otherwise returns false.
        The dataChanged() signal should be emitted if the data was successfully set.

        Args:
            index (QModelIndex): The index
            value: The value
            role (Qt.ItemDataRole): The role of the data (Default: Qt.EditRole)

        Returns:
            bool: True if successful, False otherwise
        """
        try:

            rootindex = self.index(0, 0, QModelIndex())

            root = self.nodeFromIndex(rootindex)

            if not index.isValid():

                return False

            elif role == QtCore.Qt.EditRole:

                if index.column(
                ) == self.VALUE:  # only want to edit col1 if it's a leafnode

                    node = self.nodeFromIndex(index)

                    if isinstance(node, LeafNode):

                        value = str(value)  # new value
                        old_value = node.value  # option value

                        if old_value == value:

                            return False

                        # Set the value of an option when the new value is different
                        else:
                            node.value = value
                            return True  # why doesn't this require a self.init_load()?

                elif index.column(
                ) == self.NAME:  # either editing BranchNode name or LeafNode name
                    node = self.nodeFromIndex(index)
                    if node.parent is None:
                        raise Exception(
                            "Trying to edit node without a parent. The root node should be uneditable."
                        )

                    old_value = node.name
                    if old_value == value:
                        self._design.logger.info(
                            f"No data changed in tree model because old value {old_value} == new value: {value}"
                        )
                        return False

                    node.update_name(value)

                    op = self.get_path_of_expanded_items()

                    self.reload()
                    self.expand_items_in_paths(op)

                    # update node
                    # at each parent:
                    # data.emit changed from 0,0 to len(children), lenCol
                    return True
                elif index.column() == self.TYPE:
                    # this is a type
                    node = self.nodeFromIndex(
                        self.index(index.row(), 0, index.parent()))
                    node.type = value

                    op = self.get_path_of_expanded_items()

                    self.reload()
                    self.expand_items_in_paths(op)
                    return True

            return False
        except Exception as e:
            self._design.logger.error(f"Unable to parse tree information: {e}")
            return False

    # persistentIndexList
    def get_path_of_expanded_items(self):
        """ Collect which nodes are currently expanded in order to re-expand them after refreshing the model"""
        expanded_nodes = []
        try:
            pil = self.persistentIndexList()
        except Exception as e:
            self._design.logger.error(f"EXCEPTED: {e}")
        for mi in pil:
            is_expanded = self.view.isExpanded(mi)
            if is_expanded:
                minode = self.nodeFromIndex(mi)
                expanded_nodes.append(minode)
        return expanded_nodes

    def expand_items_in_paths(self, expanded_nodes):
        """Expand all nodes that were previously saved in expanded_nodes"""
        INDEX = 0
        NODE = 1
        cur_index = QModelIndex()
        node = self.nodeFromIndex(cur_index)
        discovered_queue = queue.Queue()
        discovered_queue.put((cur_index, node))

        while discovered_queue.qsize() > 0:
            to_check = discovered_queue.get()
            if to_check[NODE] in expanded_nodes:

                self.view.setExpanded(to_check[INDEX], True)

            # find all children and add them to queue
            parent_index = to_check[INDEX]
            new_index = self.index(0, 0, parent_index)  # be valid
            row = 0
            while (new_index is not None and new_index.isValid()):

                new_index = self.index(row, 0, parent_index)
                if new_index is not None and new_index.isValid():

                    new_node = self.nodeFromIndex(new_index)
                    if isinstance(new_node, BranchNode):
                        discovered_queue.put((new_index, new_node))

                    row = row + 1

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: Qt.ItemDataRole):
        """ Set the headers to be displayed.

        Args:
            section (int): section number
            orientation (Qt.Orientation): the orientation
            role (Qt.ItemDataRole): the role

        Returns:
            object: header data
        """
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                if 0 <= section < len(self.headers):
                    return self.headers[section]

            elif role == Qt.FontRole:
                font = QFont()
                font.setBold(True)
                return font

        return None

    def index(self, row: int, column: int, parent: QModelIndex):
        """What is my index?

        Args:
            row (int): the row
            column (int): the column
            parent (QModelIndex): the parent

        Returns:
            int: internal index
        """
        assert self.root
        branch = self.nodeFromIndex(parent)
        assert branch is not None
        if isinstance(branch, BranchNode):
            # The third argument is the internal index.
            node_data = branch.childAtRow(row)
            if node_data is not None:
                return self.createIndex(row, column, node_data)

        return self.createIndex(
            -1, -1, QModelIndex())  # return invalid index which is Branch("")

    def parent(self, child):
        """Gets the parent index of the given node

        Args:
            child (node): the child

        Returns:
            int: the index
        """
        node = self.nodeFromIndex(child)

        if node is None:
            return QModelIndex()

        parent = node.parent
        if parent is None:
            return QModelIndex()

        grandparent = parent.parent
        if grandparent is None:
            return QModelIndex()
        row = grandparent.rowOfChild(parent)
        assert row != -1
        return self.createIndex(row, 0, parent)

    def nodeFromIndex(self, index: QModelIndex) -> Union[BranchNode, LeafNode]:
        """Utility method we define to get the node from the index.

        Args:
            index (QModelIndex): The model index

        Returns:
            Union[BranchNode, LeafNode]: Returns the node, which can either be
            a branch (for a dict) or a leaf (for an option key value pairs)
        """
        if index.isValid():
            # The internal pointer will return the leaf or branch node under the given parent.
            return index.internalPointer()
        return self.root

    def flags(self, index: QModelIndex):
        """
        Determine how user may interact with each cell in the table.

        Returns:
            list: flags
        """
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if index.column() == self.NAME or index.column() == self.TYPE:
            return flags | Qt.ItemIsEditable

        if index.column() == self.VALUE:
            node = self.nodeFromIndex(index)
            if isinstance(node, LeafNode):
                return flags | Qt.ItemIsEditable

        return flags
