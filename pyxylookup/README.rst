pyxylookup
==========

|travis| |coverage|

Python client for the `OBIS xylookup API <http://github.com/iobis/xylookup>`_

`Source on GitHub at iobis/pyxylookup <https://github.com/iobis/pyxylookup>`_

`Documentation at Read the Docs <http://pyxylookup.readthedocs.io/>`_

Other OBIS xylookup clients:

* R: `obistools`, `iobis/obistools <https://github.com/iobis/obistools>`_

Installation
============

.. code-block:: shell

    pip install git+git://github.com/iobis/pyxylookup.git

Example usage
=============

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


Development environment installation
====================================

.. code-block:: shell

    pipenv --three
    pipenv install vcrpy
    pipenv install tox
    pipenv install nose
    pipenv install requests
    pipenv install u-msgpack-python
    pipenv install pandas
    pipenv install sphinx sphinx-autobuild sphinx_rtd_theme
    # enter virtual evironment
    pipenv shell
    # run tests
    pipenv run tox

Meta
====

* License: MIT, see `LICENSE file <LICENSE>`_

.. |travis| image:: https://travis-ci.org/iobis/pyxylookup.svg
   :target: https://travis-ci.org/iobis/pyxylookup

.. |coverage| image:: https://coveralls.io/repos/iobis/pyxylookup/badge.svg?branch=master&service=github
   :target: https://coveralls.io/github/iobis/pyxylookup?branch=master