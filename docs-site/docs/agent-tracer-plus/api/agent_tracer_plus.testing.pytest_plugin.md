# Module: `agent_tracer_plus.testing.pytest_plugin`

Pytest plugin for agent-tracer-plus trace regression testing.

When enabled with --atp-regression &lt;dir&gt;, this plugin dynamically generates
test cases for every golden trace found in the directory.

## Function `pytest_addoption(parser)`
Add custom command line options to pytest.

## Function `pytest_generate_tests(metafunc)`
Dynamically generate tests if the flag is provided and the fixture is requested.

## Function `atp_update_baselines(request)`
Fixture to check if the update flag was passed.

## Function `atp_eval_runner()`
Fixture providing the concurrent AsyncEvalRunner for prompt testing.

