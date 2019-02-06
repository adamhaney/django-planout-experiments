from django.conf.urls import url

from .views import ExperimentBreakdownView

app_name = "planout_experiments"

urlpatterns = [
    url(
        'breakdown/(?P<pk>.*?)/',
        ExperimentBreakdownView.as_view(),
        name='experiment-breakdown'
    ),
]
