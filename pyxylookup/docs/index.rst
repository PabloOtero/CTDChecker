==================================
pyxylookup |version| documentation
==================================

|travis| |coverage|

Python client for the `OBIS xylookup API <http://github.com/iobis/xylookup>`_

`Source on GitHub at iobis/pyxylookup <https://github.com/iobis/pyxylookup>`_

Other OBIS xylookup clients:

* R: `obistools`, `iobis/obistools <https://github.com/iobis/obistools>`_

Getting help
============

Having trouble? Or want to know how to get started?

* Looking for specific information? Try the :ref:`genindex`
* Report bugs with pyxylookup in our `issue tracker`_.

.. _issue tracker: https://github.com/iobis/pyxylookup/issues


Getting started
===============

The main function in this package is the lookup function:

.. autofunction:: pyxylookup.lookup

.. code-block:: python

    import pyxylookup as xy

    xy.lookup([[120,0], [-170,1]])

:doc:`usage`
   More examples
:doc:`license`
   The pyxylookup license.

.. toctree::
   :maxdepth: 2
   :caption: Table of contents:

   usage
   license

.. |travis| image:: https://travis-ci.org/iobis/pyxylookup.svg
   :target: https://travis-ci.org/iobis/pyxylookup

.. |coverage| image:: https://coveralls.io/repos/iobis/pyxylookup/badge.svg?branch=master&service=github
   :target: https://coveralls.io/github/iobis/pyxylookup?branch=master