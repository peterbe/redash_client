import math
import mock
import json
import time
import statistics

from src.tests.base import AppTest
from src.dashboards.ActivityStreamExperimentDashboard import (
    ActivityStreamExperimentDashboard)


class TestActivityStreamExperimentDashboard(AppTest):

  ADDON_VERSIONS = ["1.8.0", "1.9.0"]
  START_DATE = "02/17/2017"
  END_DATE = time.strftime("%m/%d/%y")
  DASH_NAME = "Screenshots Long Cache"
  EXPERIMENT_ID = "exp-014-screenshotsasync"

  def get_dashboard(self, api_key):
    self.mock_requests_get.return_value = self.get_mock_response()
    self.mock_requests_post.return_value = self.get_mock_response()

    dashboard = ActivityStreamExperimentDashboard(
        self.redash,
        self.DASH_NAME,
        self.EXPERIMENT_ID,
        self.ADDON_VERSIONS,
        self.START_DATE,
    )
    return dashboard

  def test_correct_values_at_initialization(self):
    self.assertEqual(self.dash._experiment_id, self.EXPERIMENT_ID)
    self.assertEqual(
        self.dash._dash_name,
        self.dash.DASH_PREFIX.format(name=self.DASH_NAME))
    self.assertEqual(self.dash._start_date, self.START_DATE)
    self.assertEqual(self.dash._end_date, self.END_DATE)
    self.assertEqual(self.dash._addon_versions, "'1.8.0', '1.9.0'")

    # 2 posts to create the dashboard and make it public
    self.assertEqual(self.mock_requests_post.call_count, 2)
    self.assertEqual(self.mock_requests_get.call_count, 1)
    self.assertEqual(self.mock_requests_delete.call_count, 0)

  def test_pooled_stddev(self):
    exp_vals = [1, 2, 3]
    control_vals = [4, 6, 8]
    EXPECTED_POOLED_STDDEV = math.sqrt(10 / float(4))

    exp_std = statistics.stdev(exp_vals)
    control_std = statistics.stdev(control_vals)

    pooled_stddev = self.dash._compute_pooled_stddev(
        control_std, exp_std, control_vals, exp_vals)

    self.assertEqual(pooled_stddev, EXPECTED_POOLED_STDDEV)

  def test_power_and_ttest_negative_results(self):
    exp_vals = [1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3]
    control_vals = [4, 6, 8, 4, 6, 8, 4, 6, 8, 4, 6, 8]
    MEAN_DIFFERENCE = -4

    results = self.dash._power_and_ttest(
        control_vals, exp_vals)

    self.assertEqual(results["mean_diff"], MEAN_DIFFERENCE)
    self.assertEqual(results["significance"], "Negative")
    self.assertTrue(0 <= results["p_val"] <= 0.05)
    self.assertTrue(0.5 <= results["power"] <= 1)

  def test_power_and_ttest_positive_results(self):
    exp_vals = [4, 6, 8, 4, 6, 8, 4, 6, 8, 4, 6, 8]
    control_vals = [1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3]
    MEAN_DIFFERENCE = 4

    results = self.dash._power_and_ttest(
        control_vals, exp_vals)

    self.assertEqual(results["mean_diff"], MEAN_DIFFERENCE)
    self.assertEqual(results["significance"], "Positive")
    self.assertTrue(0 <= results["p_val"] <= 0.05)
    self.assertTrue(0.5 <= results["power"] <= 1)

  def test_power_and_ttest_neutral_results(self):
    exp_vals = [4, 6, 8, 4, 6, 8, 4, 6, 8, 4, 6, 8]
    control_vals = [4, 6, 8, 4, 6, 8, 4, 6, 8, 4, 6, 8]
    MEAN_DIFFERENCE = 0

    results = self.dash._power_and_ttest(
        control_vals, exp_vals)

    self.assertEqual(results["mean_diff"], MEAN_DIFFERENCE)
    self.assertEqual(results["significance"], "Neutral")
    self.assertEqual(results["p_val"], 1)
    self.assertTrue(0 <= results["power"] <= 0.1)

  def test_get_ttable_data_for_non_existent_query(self):
    QUERY_RESULTS_RESPONSE = {}

    self.mock_requests_post.return_value = self.get_mock_response(
        content=json.dumps(QUERY_RESULTS_RESPONSE))

    ttable_row = self.dash._get_ttable_data_for_query(
        "beep", "meep", "boop")

    self.assertEqual(ttable_row, {})

  def test_ttable_not_made_for_non_matching_graph(self):
    BAD_ROW = []
    for i in xrange(5):
        BAD_ROW.append({
            "some_weird_row": "beep",
            "event_rate": 5
        })

    QUERY_RESULTS_RESPONSE = {
        "query_result": {
            "data": {
                "rows": BAD_ROW
            }
        }
    }

    self.mock_requests_post.return_value = self.get_mock_response(
        content=json.dumps(QUERY_RESULTS_RESPONSE))

    ttable_row = self.dash._get_ttable_data_for_query(
        "beep", "meep", "event_rate")

    self.assertEqual(len(ttable_row), 0)

  def test_ttable_row_data_is_correct(self):
    EXPECTED_LABEL = "beep"
    EXPECTED_ROWS = []
    EXPECTED_MEAN_DIFFERENCE = -4

    for i in xrange(12):
      EXPECTED_ROWS.append({
          "date": 123,
          "event_rate": (i % 3) + 1,
          "type": "experiment"
      })
      EXPECTED_ROWS.append({
          "date": 123,
          "event_rate": ((i * 2) % 6) + 4,  # 4, 6, 8
          "type": "control"
      })

    QUERY_RESULTS_RESPONSE = {
        "query_result": {
            "data": {
                "rows": EXPECTED_ROWS
            }
        }
    }

    self.mock_requests_post.return_value = self.get_mock_response(
        content=json.dumps(QUERY_RESULTS_RESPONSE))

    ttable_row = self.dash._get_ttable_data_for_query(
        EXPECTED_LABEL, "meep", "event_rate")

    self.assertEqual(len(ttable_row), 6)
    self.assertEqual(ttable_row["Metric"], EXPECTED_LABEL)
    self.assertEqual(ttable_row["Alpha Error"], self.dash.ALPHA_ERROR)
    self.assertTrue(0.5 <= ttable_row["Power"] <= 1)
    self.assertTrue(0 <= ttable_row["Two-Tailed P-value (ttest)"] <= 0.05)
    self.assertEqual(
        ttable_row["Experiment Mean - Control Mean"], EXPECTED_MEAN_DIFFERENCE)

  def test_add_disable_graph_makes_correct_calls(self):
    self.server_calls = 0

    self.mock_requests_get.return_value = self.get_mock_response()
    self.mock_requests_post.side_effect = self.post_server

    self.dash.add_disable_graph()

    # GET calls:
    #     1) Create dashboard
    #     2) Get dashboard widgets
    #     3) Get table ID
    # POST calls:
    #     1) Create dashboard
    #     2) Create query
    #     3) Refresh query
    #     4) Create visualization
    #     5) Append visualization to dashboard
    #     6) Make dashboard public
    self.assertEqual(self.mock_requests_post.call_count, 6)
    self.assertEqual(self.mock_requests_get.call_count, 3)
    self.assertEqual(self.mock_requests_delete.call_count, 0)

  def test_disable_graph_exist_makes_no_request(self):
    WIDGETS_RESPONSE = {
        "widgets": [[{
            "visualization": {
                "query": {
                    "name": self.dash.DISABLE_TITLE,
                },
            },
        }]]
    }

    self.mock_requests_get.return_value = self.get_mock_response(
        content=json.dumps(WIDGETS_RESPONSE))

    self.dash.add_disable_graph()

    # 2 posts to create the dashboard and make it public
    # 2 gets for creating the dashboard and looking up chart names
    self.assertEqual(self.mock_requests_post.call_count, 2)
    self.assertEqual(self.mock_requests_get.call_count, 2)
    self.assertEqual(self.mock_requests_delete.call_count, 0)

  def test_add_retention_diff_makes_correct_calls(self):
    self.server_calls = 0

    self.mock_requests_get.return_value = self.get_mock_response()
    self.mock_requests_post.side_effect = self.post_server

    self.dash.add_retention_diff()

    # GET calls:
    #     1) Create dashboard
    #     2) Get dashboard widgets
    #     3) Get table ID
    # POST calls:
    #     1) Create dashboard
    #     2) Create query
    #     3) Refresh query
    #     4) Create visualization
    #     5) Append visualization to dashboard
    #     6) Make dashboard public
    self.assertEqual(self.mock_requests_post.call_count, 6)
    self.assertEqual(self.mock_requests_get.call_count, 3)
    self.assertEqual(self.mock_requests_delete.call_count, 0)

  def test_retention_diff_graph_exist_makes_no_request(self):
    WIDGETS_RESPONSE = {
        "widgets": [[{
            "visualization": {
                "query": {
                    "name": self.dash.RETENTION_DIFF_TITLE,
                },
            },
        }]]
    }

    self.mock_requests_get.return_value = self.get_mock_response(
        content=json.dumps(WIDGETS_RESPONSE))

    self.dash.add_retention_diff()

    # 2 posts to create the dashboard and make it public
    # 2 gets for creating the dashboard and looking up chart names
    self.assertEqual(self.mock_requests_post.call_count, 2)
    self.assertEqual(self.mock_requests_get.call_count, 2)
    self.assertEqual(self.mock_requests_delete.call_count, 0)

  def test_add_templates_makes_correct_calls(self):
    self.get_calls = 0
    QUERIES_IN_SEARCH = [{
        "id": 5,
        "description": "SomeQuery",
        "name": "AS Template: Query Title Event",
        "data_source_id": 5
    }, {
        "id": 6,
        "description": "SomeQuery2",
        "name": "AS Template: Query Title",
        "data_source_id": 5
    }]
    VISUALIZATIONS_FOR_QUERY = {
        "visualizations": [
            {"options": {}},
            {"options": {}}
        ]
    }
    WIDGETS_RESPONSE = {
        "widgets": [[{
            "id": "the_widget_id",
            "visualization": {
                "query": {
                    "id": "some_id",
                    "name": "Query Title Click"
                },
            },
        }]]
    }

    def get_server(url):
      response = self.get_mock_response()
      if self.get_calls == 0:
        response = self.get_mock_response(
            content=json.dumps(QUERIES_IN_SEARCH))
      elif self.get_calls <= 2:
        response = self.get_mock_response(
            content=json.dumps(VISUALIZATIONS_FOR_QUERY))
      else:
        response = self.get_mock_response(
            content=json.dumps(WIDGETS_RESPONSE))

      self.get_calls += 1
      return response

    self.server_calls = 0
    self.mock_requests_delete.return_value = self.get_mock_response()
    self.mock_requests_post.side_effect = self.post_server
    self.mock_requests_get.side_effect = get_server

    self.dash.add_templates()

    # GET calls:
    #     1) Create dashboard
    #     2) Get dashboard widgets
    #     3) Search queries
    #     4) Get two existing visualizations
    # POST calls:
    #     1) Create dashboard
    #     2) Search queries
    #     3) Fork query
    #     4) Update query
    #     5) Create visualization
    #     6) Append visualization to dashboard
    #     7) Repeat 2-6 eleven times
    #     8) Make dashboard public
    # DELETE calls:
    #     One existing graph is removed from dashboard
    #     and deleted (2 calls)
    self.assertEqual(self.mock_requests_post.call_count, 57)
    self.assertEqual(self.mock_requests_get.call_count, 5)
    self.assertEqual(self.mock_requests_delete.call_count, 2)

  def test_add_ttable_makes_correct_calls(self):
    WIDGETS_RESPONSE = {
        "widgets": [[{
            "visualization": {
                "query": {
                    "name": "Some table",
                },
            },
        }]]
    }

    EXPECTED_ROWS = [{
        "event_rate": 123,
        "type": "experiment",
    }, {
        "event_rate": 789,
        "type": "control",
    }, {
        "event_rate": 1233,
        "type": "experiment",
    }, {
        "event_rate": 7819,
        "type": "control",
    }]

    QUERY_RESULTS_RESPONSE = {
        "query_result": {
            "data": {
                "rows": EXPECTED_ROWS
            }
        }
    }

    mock_boto_transfer_patcher = mock.patch("src.utils.transfer.upload_file")
    mock_boto_transfer_patcher.start()

    self.server_calls = 0

    self.mock_requests_get.return_value = self.get_mock_response(
        content=json.dumps(WIDGETS_RESPONSE))
    self.mock_requests_post.return_value = self.get_mock_response(
        content=json.dumps(QUERY_RESULTS_RESPONSE))

    self.dash.add_ttable()

    # GET calls:
    #     1) Create dashboard
    #     2) Get dashboard widgets
    # POST calls:
    #     1) Create dashboard
    #     2) Get Ttable data for 1 row
    #     3) Create query
    #     4) Append visualization to dashboard
    #     5) Make dashboard public
    self.assertEqual(self.mock_requests_post.call_count, 5)
    self.assertEqual(self.mock_requests_get.call_count, 2)
    self.assertEqual(self.mock_requests_delete.call_count, 0)

    mock_boto_transfer_patcher.stop()

  def test_ttable_with_no_rows(self):
    WIDGETS_RESPONSE = {
        "widgets": [[{
            "visualization": {
                "query": {
                    "name": "Some Graph",
                },
            },
        }]]
    }

    mock_json_uploader = mock.patch(
        "src.dashboards.ActivityStreamExperimentDashboard.upload_as_json")
    upload_file_patch = mock_json_uploader.start()
    upload_file_patch.return_value = ""

    self.server_calls = 0

    self.mock_requests_get.return_value = self.get_mock_response(
        content=json.dumps(WIDGETS_RESPONSE))
    self.mock_requests_post.side_effect = self.post_server

    self.dash.add_ttable()

    # GET calls:
    #     1) Create dashboard
    #     2) Get dashboard widgets
    # POST calls:
    #     1) Create dashboard
    #     2) Create new query (Create + Refresh)
    #     3) Append visualization to dashboard
    #     4) Make dashboard public
    self.assertEqual(self.mock_requests_post.call_count, 5)
    self.assertEqual(self.mock_requests_get.call_count, 2)
    self.assertEqual(self.mock_requests_delete.call_count, 0)

    # The ttable has no rows
    args, kwargs = upload_file_patch.call_args
    self.assertEqual(len(args[2]["rows"]), 0)

    mock_json_uploader.stop()

  def test_statistical_analysis_graph_exist_deletes_and_creates_new(self):
    WIDGETS_RESPONSE = {
        "widgets": [[{
            "id": "123",
            "visualization": {
                "query": {
                    "name": self.dash.T_TABLE_TITLE,
                    "id": "abc"
                },
            },
        }]]
    }

    mock_json_uploader = mock.patch(
        "src.dashboards.ActivityStreamExperimentDashboard.upload_as_json")
    upload_file_patch = mock_json_uploader.start()
    upload_file_patch.return_value = ""

    self.mock_requests_delete.return_value = self.get_mock_response()
    self.mock_requests_get.return_value = self.get_mock_response(
        content=json.dumps(WIDGETS_RESPONSE))

    self.dash.add_ttable()

    # GET calls:
    #     1) Create dashboard
    #     2) Get dashboard widgets
    # POST calls:
    #     1) Create dashboard
    #     2) Create new query (Create + Refresh)
    #     3) Append visualization to dashboard
    #     4) Make dashboard public
    self.assertEqual(self.mock_requests_post.call_count, 5)
    self.assertEqual(self.mock_requests_get.call_count, 2)
    self.assertEqual(self.mock_requests_delete.call_count, 2)

    mock_json_uploader.stop()
