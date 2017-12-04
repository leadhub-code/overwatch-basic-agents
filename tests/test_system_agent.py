
def test_load_sample_configuration(project_dir):
    from overwatch_basic_agents.system_agent import Configuration
    assert Configuration(project_dir / 'sample_configuration.yaml')


def test_gather_state():
    from overwatch_basic_agents.system_agent import gather_state
    assert gather_state(conf=None)
