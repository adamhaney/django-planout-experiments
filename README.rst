=============================
django-planout-experiments
=============================

.. image:: https://badge.fury.io/py/django-planout-experiments.svg
    :target: https://badge.fury.io/py/django-planout-experiments

.. image:: https://travis-ci.org/adamhaney/django-planout-experiments.svg?branch=master
    :target: https://travis-ci.org/adamhaney/django-planout-experiments

.. image:: https://codecov.io/gh/adamhaney/django-planout-experiments/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/adamhaney/django-planout-experiments

A Django application that uses Facebook's Planout library to manage product experiments and track outcomes

Documentation
-------------

The full documentation is at https://django-planout-experiments.readthedocs.io.

Quickstart
----------

Install django-planout-experiments::

    pip install django-planout-experiments

Add it to your `INSTALLED_APPS`:

.. code-block:: python

    INSTALLED_APPS = (
        ...
        'planout_experiments.apps.PlanoutExperimentsConfig',
        ...
    )

Add django-planout-experiments's URL patterns:

.. code-block:: python

    from planout_experiments import urls as planout_experiments_urls


    urlpatterns = [
        ...
        url(r'^experiments/', include(planout_experiments_urls)),
        ...
    ]

Features
--------

* Allows creation of Experiment model with admin definable Goals
* Includes models for tracking events that take place related to users under test
* Allows designing experimental groups using Facebook's Planout Library[1]

  .. [1] https://facebook.github.io/planout/

  
Running Tests
-------------

Does the code actually work?

::

    source <YOURVIRTUALENV>/bin/activate
    (myenv) $ pip install tox
    (myenv) $ tox

Credits
-------

Tools used in rendering this package:

*  Cookiecutter_
*  `cookiecutter-djangopackage`_

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`cookiecutter-djangopackage`: https://github.com/pydanny/cookiecutter-djangopackage
