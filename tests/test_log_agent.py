
def test_load_sample_configuration(project_dir):
    from overwatch_basic_agents.log_agent import Configuration
    assert Configuration(project_dir / 'sample_configuration.yaml')
