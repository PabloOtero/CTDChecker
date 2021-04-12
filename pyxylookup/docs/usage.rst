.. _usage:

=====
Usage
=====

The `lookup` function supports 3 different inputs for the points parameter.
A nested list of longitude/latitude values, a 2D numpy array or a pandas DataFrame with 2 columns.

.. code-block:: python

    # nested list of longitude/latitude
    import pyxylookup as xy
    xy.lookup([[120,0], [-170,1]])

    # numpy 2d array
    import numpy as np
    points = np.asarray([[120,0], [-170,1]])
    xy.lookup(points)

    ## pandas DataFrame
    import pandas as pd
    points = pd.DataFrame({'x': [120,-170], 'y': [0,1]})
    ## retrieve results as a pandas DataFrame
    xy.lookup(points, asdataframe = True)


Additional parameters allow you to specify the data returned by the service:

.. code-block:: python

    import pyxylookup as xy
    points = [[120,0], [-170,1]]
    # only distance to the shore
    xy.lookup(points, shoredistance=True, grids=False, areas=False, asdataframe=False)
    # only grids (bathymetry, sea surface temperature, ...)
    xy.lookup(points, shoredistance=False, grids=True, areas=False, asdataframe=False)
    # all data
    xy.lookup(points, shoredistance=True, grids=True, areas=True, asdataframe=False)

For those using the pandas package, a pandas.DataFrame can be used for the points parameter and can be returned by the `lookup` function:

.. code-block:: python

    import pandas as pd
    points = pd.DataFrame({'x': [120,-170], 'y': [0,1]})
    ## retrieve results as a pandas DataFrame
    xy.lookup(points, shoredistance=True, grids=True, areas=True, asdataframe = True)

Please report bugs, questions and suggestions in our `issue tracker`_.

.. _issue tracker: https://github.com/iobis/pyxylookup/issues