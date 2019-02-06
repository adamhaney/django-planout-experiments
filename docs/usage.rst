=====
Usage
=====

To use django-planout-experiments in a project, add it to your `INSTALLED_APPS`:

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
        url(r'^', include(planout_experiments_urls)),
        ...
    ]
