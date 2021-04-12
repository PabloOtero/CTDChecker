import pyxylookup as xy
import pandas as pd
import numpy as np
import vcr
from nose.tools import raises

test_points = [[120, 0], [-170, 1], [0, 5]]


@vcr.use_cassette('tests/vcr_cassettes/lookup_points_array.yaml')
def test_lookup_points_array():
    """lookup - points array"""
    r = xy.lookup(test_points)
    assert len(r) == len(test_points)


@vcr.use_cassette('tests/vcr_cassettes/lookup_numpy_points.yaml')
def test_lookup_numpy_points():
    """lookup - numpy points"""
    points = np.asarray(test_points)
    r = xy.lookup(points)
    assert len(r) == len(test_points)


@vcr.use_cassette('tests/vcr_cassettes/lookup_pandas_points.yaml')
def test_lookup_pandas_points():
    """lookup - numpy points"""
    points = np.asarray(test_points)
    r = xy.lookup(points)
    assert len(r) == len(test_points)


@vcr.use_cassette('tests/vcr_cassettes/lookup_points_tuples_list.yaml')
def test_lookup_points_tuples_list():
    """lookup - points tuples list"""
    test_points_tuples = [(4, 5), (6, 7)]
    r = xy.lookup(test_points_tuples)
    assert len(r) == 2


@vcr.use_cassette('tests/vcr_cassettes/lookup_asdataframe.yaml')
def test_lookup_asdataframe():
    """lookup - asdataframe"""
    r = xy.lookup(test_points, asdataframe=True)
    assert r.shape[0] == len(test_points)
    assert r.shape[1] >= 4
    assert 'DataFrame' in str(type(r))
    assert isinstance(r, pd.DataFrame)
    r = xy.lookup(test_points, shoredistance=True, grids=False, areas=False, asdataframe=True)
    assert r.shape[0] == len(test_points)
    assert r.shape[1] == 1
    r = xy.lookup(test_points, shoredistance=False, grids=True, areas=False, asdataframe=True)
    assert r.shape[0] == len(test_points)
    assert r.shape[1] >= 3
    r = xy.lookup(test_points, shoredistance=False, grids=False, areas=True, asdataframe=True)
    assert r.shape[0] == len(test_points)
    assert r.shape[1] == 1
    r = xy.lookup(test_points, shoredistance=True, grids=True, areas=True, asdataframe=True)
    assert r.shape[0] == len(test_points)
    assert r.shape[1] >= 5


def test_lookup_all_false():
    """Expect error when all parameters are False"""
    @raises(TypeError)
    def check_lookup_all_false_error(asdataframe):
        xy.lookup(test_points, shoredistance=False, grids=False, areas=False, asdataframe=asdataframe)
    for asdf in [True, False]:
        check_lookup_all_false_error(asdf)


def test_lookup_wrong_points():
    """Expect error when all parameters are False"""
    @raises(ValueError)
    def test_lookup_wrong_points_error(points):
        xy.lookup(points)
    test_lookup_wrong_points_error(None)
    test_lookup_wrong_points_error([])
    test_lookup_wrong_points_error([[]])
    test_lookup_wrong_points_error("[[0,0]]")


@vcr.use_cassette('tests/vcr_cassettes/lookup_many_points.yaml')
def test_lookup_many_points():
    """Lookup many points"""
    import random
    random.seed(42)
    points = [[random.uniform(-180, 180), random.uniform(-90,90)] for _ in range(50000)]
    r = xy.lookup(points, shoredistance=True, grids=True, areas=True, asdataframe=True)
    assert r.shape[0] == len(points)
    assert r.shape[1] >= 5

@vcr.use_cassette('tests/vcr_cassettes/lookup_use_areas_distance.yaml')
def test_lookup_many_points():
    """Lookup many points"""
    import random
    random.seed(42)
    points = [[random.uniform(-180, 180), random.uniform(-90,90)] for _ in range(10)]
    r = xy.lookup(points, shoredistance=False, grids=False, areas=True, areasdistancewithin=1000000, asdataframe=True)
    assert r.shape[0] == len(points)
    assert r.shape[1] >= 1

@vcr.use_cassette('tests/vcr_cassettes/lookup_duplicate_points.yaml')
def test_lookup_duplicate_points():
    """Lookup duplicate points"""
    points = test_points * 10000
    r = xy.lookup(points, shoredistance=True, grids=False, areas=False, asdataframe=False)
    assert len(r) == len(points)
    r = xy.lookup(points, shoredistance=True, grids=False, areas=False, asdataframe=True)
    assert r.shape[0] == len(points)
    assert r.shape[1] >= 1


@vcr.use_cassette('tests/vcr_cassettes/lookup_na_points.yaml')
def test_lookup_na_points():
    """Lookup NA points"""
    import math
    points = [[0,1], [float('nan'), 3], [4, float('nan')], [5, 6]]
    r = xy.lookup(points, shoredistance=True, grids=False, areas=False, asdataframe=False)
    assert len(r) == len(points)
    assert r[1] == {}
    assert r[2] == {}
    r = xy.lookup(points, shoredistance=True, grids=True, areas=True, asdataframe=True)
    assert r.shape[0] == len(points)
    assert r.shape[1] >= 1
    assert math.isnan(r["shoredistance"][1])
    assert math.isnan(r["shoredistance"][2])


@vcr.use_cassette('tests/vcr_cassettes/lookup_duplicate_points.yaml')
def test_lookup_duplicate_points():
    """Lookup duplicate points"""
    points = test_points * 10000
    r = xy.lookup(points, shoredistance=True, grids=False, areas=False, asdataframe=False)
    assert len(r) == len(points)
    r = xy.lookup(points, shoredistance=True, grids=False, areas=False, asdataframe=True)
    assert r.shape[0] == len(points)
    assert r.shape[1] >= 1


@vcr.use_cassette('tests/vcr_cassettes/lookup_duplicate_na_points.yaml')
def test_lookup_na_points():
    """Lookup NA points with duplicates"""
    import math
    points = [[0,1], [float('nan'), 3], [4, float('nan')], [5, 6]] * 3
    r = xy.lookup(points, shoredistance=True, grids=False, areas=False, asdataframe=False)
    assert len(r) == len(points)
    for i in [1,2,5,6,9,10]:
        assert r[i] == {}
    r = xy.lookup(points, shoredistance=True, grids=True, areas=True, asdataframe=True)
    assert r.shape[0] == len(points)
    assert r.shape[1] >= 1
    for i in [1,2,5,6,9,10]:
        assert math.isnan(r["shoredistance"][i])
