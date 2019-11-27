# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""
Main module for shapely and basic geometric utility functions used in drawing.


@date: 2019
@author: Zlatko Minev (IBM)
"""
# pylint: disable=ungrouped-imports

from collections.abc import Iterable, Mapping

import numpy as np
import shapely
import shapely.wkt
from numpy import array
from numpy.linalg import norm
from shapely.affinity import rotate, scale, translate
from shapely.geometry import (CAP_STYLE, JOIN_STYLE, MultiPolygon, Point,
                              Polygon)

from .. import logger, is_component, is_element
from ..toolbox_mpl.mpl_interaction import figure_pz

# TODO: define rotate, scale, translate to operate on shapely, element, component, and itterable, mappable

__all__ = ['get_poly_pts', 'get_all_component_bounds', 'get_all_geoms', 'flatten_all_filter']

#########################################################################
# Shapely Geometry Basic Coordinates


def get_poly_pts(poly: Polygon):
    """
    Return the coordinates of a Shapely polygon with the last repeating point removed

    Arguments:
        poly {[shapely.Polygon]} -- Shapely polygin

    Returns:
        [np.array] -- Sequence of coorindates.
    """
    return np.array(poly.exterior.coords)[:-1]


def get_all_geoms(obj, func=lambda x: x, root_name='components'):
    """Get a dict of dict of all shapely objects, from components, dict, etc.

    Used to compute the bounding box.

    Arguments:
        components {[dict,list,element,component]} --

    Keyword Arguments:
        func {[function]} -- [description] (default: {lambdax:x})
        root_name {str} -- Name to prepend in the flattening (default: {'components'})

    Returns:
        [dict] -- [description]
    """

    # Prelim
    # Calculate the new name
    def new_name(name): return root_name + '.' + \
        name if not (root_name == '') else name

    # Check what we have

    if is_component(obj):
        # Is it a metal component? Then traverse its components
        return obj.get_all_geom()  # dict of shapely geoms

    elif is_element(obj):
        # is it a metal element?
        return {obj.name: obj.geom}  # shapely geom

    elif isinstance(obj, shapely.geometry.base.BaseGeometry):
        # Is it the shapely object? This is the bottom of the search tree, then return
        return obj

    elif isinstance(obj, Mapping):
        return {get_all_geoms(sub_obj, root_name=new_name(name)) for name, sub_obj in obj.items()}
        '''
        RES = {}
        for name, sub_obj in obj.items():
            if is_component(obj):
                RES[name] = get_all_geoms(
                    sub_obj.components, root_name=new_name(name))
            elif isinstance(sub_obj, dict):
                # if name.startswith('components'): # old school to remove eventually TODO
                #    RES[name] = func(obj) # allow transofmraiton of components
                # else:
                RES[name] = get_all_geoms(sub_obj, root_name=new_name(name))
            elif isinstance(sub_obj, shapely.geometry.base.BaseGeometry):
                RES[name] = func(obj)
        return RES
        '''

    else:
        logger.debug(
            f'warning: {root_name} was not an object or dict or the right handle')
        return None


def flatten_all_filter(components : dict, filter_obj=None):
    """Internal function to flatten a dict of shapely objects.

    Arguments:
        components {dict} -- [description]

    Keyword Arguments:
        filter_obj {[class]} -- Filter based on this calss (default: {None})
    """
    assert isinstance(components, dict)

    RES = []
    for name, obj in components.items():
        if isinstance(obj, dict):
            RES += flatten_all_filter(obj, filter_obj)
        else:
            if filter_obj is None:
                RES += [obj] # add whatever we have in here
            else:
                if isinstance(obj, filter_obj):
                    RES += [obj]
                else:
                    print('flatten_all_filter: ', name)

    return RES


def get_all_component_bounds(components: dict, filter_obj=shapely.geometry.Polygon):
    """
    Pass in a dict of components to calcualte the total bounding box.

    Arguments:
        components {dict} -- [description]
        filter_obj {shapely.geometry.Polygon} -- only use instances of this object to
                             calcualte the bounds

    Returns:
        (x_min, y_min, x_max, y_max)
    """
    assert isinstance(components, dict)

    components = get_all_geoms(components)
    components = flatten_all_filter(components, filter_obj=filter_obj)

    (x_min, y_min, x_max, y_max) = MultiPolygon(components).bounds

    return (x_min, y_min, x_max, y_max)




#########################################################################
# POINT LIST FUNCTIONS

def check_duplicate_list(your_list):
    return len(your_list) != len(set(your_list))


def unit_vector(vector):
    """ Return a vector where is XY components now make a unit vector

    Normalizes only in the XY plane, leaves the Z plane alone
    """
    vector = array_chop(vector)  # get rid of near zero crap
    if len(vector) == 2:
        _norm = norm(vector)
        if not bool(_norm):  # zero length vector
            logger.debug(f'Warning: zero vector length')
            return vector
        return vector / _norm
    elif len(vector) == 3:
        v2 = unit_vector(vector[:2])
        return np.append(v2, vector[2])
    else:
        raise Exception('You did not give a 2 or 3 vec')


def get_unit_vec(two_points):
    assert len(two_points) == 2
    two_points = np.array(two_points)
    two_points = two_points[1] - two_points[0]               # distance vector
    return two_points / norm(two_points)


def vec_angle(v1, v2):
    """
    Returns the angle in radians between vectors 'v1' and 'v2'::
    """
    v1_u = unit_vector(v1)
    v2_u = unit_vector(v2)
    return np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0))


def get_vec_unit_norm(points,
                      normal_z=np.array([0, 0, 1])):
    '''
        Get the unit and the normal vector

        .. codeblock python
            vec_D, vec_d, vec_n = get_vec_unit_norm(points)
    '''
    assert len(points) == 2
    points = list(map(np.array, points))         # enforce numpy array
    vec_D = points[1] - points[0]               # distance vector
    vec_d = vec_D / norm(vec_D)                 # unit dist. vector
    vec_n = np.cross(normal_z, vec_d)           # normal unit vector
    vec_n = vec_n[:len(vec_d)]
    return vec_D, vec_d, vec_n


def to_Vec3Dz(vec2D, z=0):
    '''
    Used for darwing in HFSS only.
    For the given design, get the z values in HFSS UNITS!

    Manually specify z dimension.
    '''
    if isinstance(vec2D[0], Iterable):
        return array([to_Vec3Dz(vec, z=z) for vec in vec2D])
    else:
        return array(list(vec2D)+[z])


"""
#DEPRICATED: MOVED TO RENDER FOR HFSS. Just pass in the right arguments to to_Vec3Dz

def to_Vec3D(design, options, vec2D):
    '''
    Used for darwing in HFSS only.
    For the given design, get the z values in HFSS UNITS!

    get z dimension from the design chip params
    '''
    if isinstance(vec2D[0], Iterable):
        return array([to_Vec3D(design, options, vec) for vec in vec2D])
    else:
        # if not isinstance(options,dict):
        #    options={'chip':options}
        z = parse_value_hfss(design.get_chip_z(
            options.get('chip', draw.functions.DEFAULT['chip'])))
        return array(list(vec2D)+[z])
"""


def array_chop(vec, zero=0, rtol=0, machine_tol=100):
    '''
    Chop array entires close to zero.
    Zlatko quick solution.
    '''
    vec = np.array(vec)
    mask = np.isclose(vec, zero, rtol=rtol,
                      atol=machine_tol*np.finfo(float).eps)
    vec[mask] = 0
    return vec


def same_vectors(v1, v2, tol=100):
    '''
    Check if two vectors are within an infentesmimal distance set
    by `tol` and machine epsilon
    '''
    v1, v2 = list(map(np.array, [v1, v2]))         # enforce numpy array
    return float(norm(v1-v2)) < tol*np.finfo(float).eps


def remove_co_linear_points(points):
    '''
    remove colinear points and identical consequtive points
    '''
    remove_idx = []
    for i in range(2, len(points)):
        v1 = array(points[i-2])-array(points[i-1])
        v2 = array(points[i-1])-array(points[i-0])
        if same_vectors(v1, v2):
            remove_idx += [i-1]
        elif vec_angle(v1, v2) == 0:
            remove_idx += [i-1]
    points = np.delete(points, remove_idx, axis=0)

    # remove  consequtive duplicates
    remove_idx = []
    for i in range(1, len(points)):
        if norm(points[i]-points[i-1]) == 0:
            remove_idx += [i]
    points = np.delete(points, remove_idx, axis=0)

    return points
