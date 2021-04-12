# -*- coding: utf-8 -*-

# pyxylookup

"""
pyxylookup library
~~~~~~~~~~~~~~~~~~~~~

pyxylookup is a Python client for the OBIS xylookup API.

Usage::

        # Import library
        import pyxylookup

        from pyxylookup import lookupxy
        lookup_xy([[0,0], [1,1]])
"""

__version__ = '0.2.0.0'
__title__ = 'pyxylookup'
__author__ = 'Samuel Bosch'
__license__ = 'MIT'

import msgpack
import numpy as np
import requests


def _lookup(data):
    msgdata = msgpack.dumps(data)
    headers = {'content-type': 'application/msgpack'}
    r = requests.post('https://api.obis.org/xylookup/', data=msgdata, headers=headers)
    if r.status_code == 200:
        return msgpack.loads(r.content, raw=False)
    else:
        raise Exception(r.content)


def lookup(points, shoredistance=True, grids=True, areas=False, areasdistancewithin=0, asdataframe=False):
    """Lookup data for a set of coordinates

    :param points: A set of longitude/latitude coordinates as a nested list, a 2d numpy array or a 2 column pandas DataFrame
    :param shoredistance: Indicate whether the shoredistance should be returned (default: True)
    :param grids: Indicate whether grid values such as temperature and bathymetry should be returned (default: True)
    :param areas: Indicate whether the area values should be returned (default: False)
    :param areasdistancewithin: Distance in meters within which areas have to be in order to be detected (default: 0 meters = intersect).
    :param asdataframe: Indicate whether a pandas DataFrame or a list of dictionaries should be returned (default: False).
    :return: A list of dictionaries with the values (default) or a pandas DataFrame if asdataframe is True.
    :raises: ValueError, TypeError
    """
    points = np.asarray(points)
    if len(points.shape) != 2 or points.shape[1] != 2:
        raise ValueError("Points should be a nested array of longitude latitude coordinates or a numpy.ndarray")
    try:
        points = points.astype(float)
    except ValueError:
        raise ValueError("Points should be numeric")

    if not shoredistance and not grids and not areas:
        raise TypeError("At least one of shoredistance, grids or areas should be True")

    points, duplicate_indices = np.unique(points, return_inverse=True, axis=0)

    nan = np.isnan(points)
    nan = (nan[:, 0] | nan[:, 1])
    points = points[~nan]

    if not all([-180 <= p[0] <= 180 and -90 <= p[1] <= 90 for p in points]):
        raise ValueError('Invalid coordinates (xmin: -180, ymin: -90, xmax: 180, ymax: 90)',
                         'x/y points')

    pointchunks = np.array_split(points, (len(points) // 25000) + 1)
    result = []
    for chunk in pointchunks:
        data = {
            'points': chunk.tolist(),
            'shoredistance': shoredistance,
            'grids': grids,
            'areas': areas,
            'areasdistancewithin': areasdistancewithin
        }
        result.extend(_lookup(data))

    for nani in np.where(nan)[0]:
        result.insert(nani, {})

    result = np.asarray(result)[duplicate_indices]
    if asdataframe:
        try:
            import pandas as pd
            df = pd.DataFrame.from_records(result)
            df_list = []
            if shoredistance:
                df_list.append(pd.DataFrame({'shoredistance': df['shoredistance']}))
            if grids:
                nan = nan[duplicate_indices]
                df.loc[nan, 'grids'] = [{}] * np.sum(nan)
                df_list.append(pd.DataFrame.from_records(df['grids']))
            if areas:
                df.loc[nan, 'areas'] = [{}] * np.sum(nan)
                df_list.append(pd.DataFrame({'areas': df['areas']}))
            result = pd.concat(df_list, axis=1)
            return result
        except ImportError:
            raise ImportError("pandas is required for the 'asdataframe' parameter in the lookup function")
    else:
        return list(result)
