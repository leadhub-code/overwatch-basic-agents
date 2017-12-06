
def test_load_sample_configuration(project_dir):
    from overwatch_basic_agents.web_agent import Configuration
    assert Configuration(project_dir / 'sample_configuration.yaml')


def test_check_nonexisting_target():
    import requests
    from overwatch_basic_agents.web_agent import check_target
    class sample_target:
        name = 'Test'
        url = 'http://localhost:4/test'
    report_state = {}
    check_target(requests.session(), sample_target, report_state, timeout=0.001)
    print(report_state)
    assert report_state['name'] == 'Test'
    assert report_state['url'] == 'http://localhost:4/test'
    assert report_state['duration']
