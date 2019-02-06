from unittest import skip

from django.test import TestCase
from django.contrib.auth.models import User

from planout_experiments.models import Experiment, Exposure, Variation, Goal, GoalAchievement


EXAMPLE_EXPERIMENT_JSON = """
{
 "op": "seq",
 "seq": [
  {
   "op": "set",
   "var": "group_size",
   "value": {
    "choices": {
     "op": "array",
     "values": [
      1,
      10
     ]
    },
    "unit": {
     "op": "get",
     "var": "user_id"
    },
    "op": "uniformChoice"
   }
  },
  {
   "op": "set",
   "var": "specific_goal",
   "value": {
    "p": 0.8,
    "unit": {
     "op": "get",
     "var": "user_id"
    },
    "op": "bernoulliTrial"
   }
  },
  {
   "op": "cond",
   "cond": [
    {
     "if": {
      "op": "get",
      "var": "specific_goal"
     },
     "then": {
      "op": "seq",
      "seq": [
       {
        "op": "set",
        "var": "ratings_per_user_goal",
        "value": {
         "choices": {
          "op": "array",
          "values": [
           8,
           16,
           32,
           64
          ]
         },
         "unit": {
          "op": "get",
          "var": "user_id"
         },
         "op": "uniformChoice"
        }
       },
       {
        "op": "set",
        "var": "ratings_goal",
        "value": {
         "op": "product",
         "values": [
          {
           "op": "get",
           "var": "group_size"
          },
          {
           "op": "get",
           "var": "ratings_per_user_goal"
          }
         ]
        }
       }
      ]
     }
    }
   ]
  },
  {
   "op": "set",
   "var": "button_text",
   "value": "blue"
  }
 ]
}
"""


class ExperimentBaseTests(TestCase):
    def setUp(self):
        self.experiment = Experiment.objects.create(name='Test Experiment', planout_json=EXAMPLE_EXPERIMENT_JSON)
        self.assertEqual(Exposure.objects.count(), 0)
        self.assertEqual(Variation.objects.count(), 0)
        self.trial = self.experiment.get_experiment_trial()

    def test_experiment_params(self):
        self.assertEqual(self.trial.get('button_text'), 'blue')

    def test_experiment_output_variables_property(self):
        self.assertEqual(
            set(self.experiment.output_variables),
            set(['group_size', 'specific_goal', 'ratings_goal', 'ratings_per_user_goal', 'button_text'])
        )

    def test_experiment_get_planout_dict(self):
        self.assertEqual(list(self.experiment.get_planout_dict().keys()), ['op', 'seq'])


class ExperimentMutationTests(TestCase):
    def setUp(self):
        self.empty_experiment = Experiment.objects.create(name='default_experiment')

    def test_default_planout_json(self):
        self.assertEqual(
            list(self.empty_experiment.get_planout_dict().keys()),
            ['op', 'seq']
        )

    def test_empty_output_variables(self):
        self.assertEqual(
            self.empty_experiment.output_variables,
            []
        )

    def test_add_planout_variable(self):
        self.empty_experiment.add_planout_variable('the_lime', 'The Coconut')
        self.assertEqual(self.empty_experiment.get_planout_params(), {'the_lime': 'The Coconut'})


class ExperimentUserTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test_user', password='pwpw')

        self.experiment = Experiment.objects.create(name='Test Experiment', planout_json=EXAMPLE_EXPERIMENT_JSON)
        self.assertEqual(Exposure.objects.count(), 0)
        self.assertEqual(Variation.objects.count(), 0)
        self.trial = self.experiment.get_trial_for_user(self.user)

        self.visit_goal = Goal.objects.create(
            name='visit_establishment',
            description='User visits an establishment, good because it assumes they spent money at the restaurant'
        )

        self.share_goal = Goal.objects.create(
            name='shared_offer',
            description="User shared the offer"
        )

    def test_experiment_params(self):
        self.assertEqual(self.trial.get('button_text'), 'blue')

    def test_experiment_exposure(self):
        self.assertEqual(self.trial.get('button_text'), 'blue')

        self.assertEqual(Variation.objects.filter(key='button_text').count(), 1)
        self.assertEqual(Exposure.objects.filter(variation__key='button_text').count(), 1)

        exposure = Exposure.objects.get(variation__key='button_text')

        self.assertEqual(exposure.experiment, self.experiment)
        self.assertEqual(exposure.event_user, self.user)

        self.assertEqual(exposure.variation.experiment, self.experiment)
        self.assertEqual(exposure.variation.key, 'button_text')
        self.assertEqual(exposure.variation.value, 'blue')

        self.assertEqual(exposure.variation.num_exposures, 1)

        Exposure.objects.all().delete()
        Variation.objects.all().delete()

    @skip
    def test_goal_tracking(self):
        self.assertEqual(self.trial.get('button_text'), 'blue')

        self.assertEqual(GoalAchievement.objects.count(), 0)

        button_variation = self.experiment.variations.get(key='button_text')

        self.assertEqual(button_variation.num_exposures, 1)
        self.assertEqual(button_variation.success_value(self.visit_goal), 0)
        self.assertEqual(button_variation.success_rate(self.visit_goal), 0)
        self.assertEqual(button_variation.success_percentage(self.visit_goal), 0.0)

        GoalAchievement.objects.create(
            event_user=self.user,
            goal=self.visit_goal
        )

        button_variation = self.experiment.variations.get(key='button_text')

        self.assertEqual(button_variation.num_exposures, 1)
        self.assertEqual(button_variation.success_value(self.visit_goal), 1.0)
        self.assertEqual(button_variation.success_rate(self.visit_goal), 1.0)
        self.assertEqual(button_variation.success_percentage(self.visit_goal), 100.0)


class DynamicExperimentValueTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test_user')

    def test_get_experiment_value_creates_experiment(self):
        self.assertEqual(Experiment.objects.count(), 0)
        self.assertEqual(Exposure.objects.count(), 0)
        result = Experiment.get_experiment_value(
            'dynamic_experiment',
            'strategy',
            user=self.user,
            control_value='vanilla'
        )
        self.assertEqual(result, 'vanilla')
        self.assertEqual(Experiment.objects.count(), 1)

        experiment = Experiment.objects.all()[0]

        self.assertEqual(experiment.name, 'dynamic_experiment')

        self.assertEqual(Exposure.objects.count(), 1)

    def test_get_experiment_creates_experiment(self):
        self.assertEqual(Experiment.objects.count(), 0)
        experiment = Experiment.get_experiment('gettable_experiment', {'strategy': 'chocolate'})
        self.assertEqual(experiment.name, 'gettable_experiment')
        planout = experiment.get_planout_dict()

        self.assertEqual(planout['op'], 'seq')
        self.assertEqual(len(planout['seq']), 1)
        self.assertEqual(planout['seq'][0], {"op": "set", "var": "strategy", "value": "chocolate"})

        self.assertEqual(Experiment.objects.count(), 1)


WEIGHTED_CHOICE_JSON = """
{
 "op": "seq",
 "seq": [
  {
   "op": "set",
   "var": "user_is_participating",
   "value": {
    "choices": {
     "op": "array",
     "values": [
      "true",
      "false"
     ]
    },
    "weights": {
     "op": "array",
     "values": [
      0.1,
      0.9
     ]
    },
    "unit": {
     "op": "get",
     "var": "user_id"
    },
    "op": "weightedChoice"
   }
  }
 ]
}
"""


class WeightedChoiceExperimentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test_user', password='pwpw')
        self.weighted_experiment = Experiment.objects.create(
            name='weighted_choice_experiment',
            planout_json=WEIGHTED_CHOICE_JSON
        )

    def test_weighted_choice_output_variables(self):
        self.assertEqual(self.weighted_experiment.output_variables, ['user_is_participating'])

    def test_outputs_true_or_false_string(self):
        trial = self.weighted_experiment.get_trial_for_user(self.user)

        result = trial.get('user_is_participating')

        # Handling it this way because even though experiments are salted and reliable
        # for the same user the db environments change and I don't want a flaky test
        self.assertTrue(result == 'false' or result == 'true')
