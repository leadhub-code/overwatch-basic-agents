Overwatch monitoring: basic agents
==================================

This is a collection of basic agents that monitor some resources and report to [Overwatch Hub](https://github.com/leadhub-code/overwatch-hub):

- **system agent** - reports CPU, memory and disk utilization
- **web agent** - checks HTTP(S) endpoints and reports status
- **log agent** - watches a log (for example nginx.log) and reports occurrences of given regular expression patterns (for example responses with status 500)

See [Overwatch monitoring overview](https://github.com/leadhub-code/overwatch-monitoring/blob/master/README.md).


Installation
------------

From Github master branch:

```shell
$ pip install https://github.com/leadhub-code/overwatch-basic-agents/archive/master.zip
```

Configuration
-------------

Configuration is stored in an YAML file. Each agent uses its own section - for example configuration of the system agent would be:

```yaml
# contents of file overwatch_system_agent.yaml
overwatch_system_agent:
    report_url: http://overwatch.example.com/report
    report_token: secret_report_token
```

For a more complete reference see [sample_configuration.yaml](https://github.com/leadhub-code/overwatch-basic-agents/blob/master/sample_configuration.yaml).


Usage
-----

Run on command line:

```shell
$ overwatch-system-agent overwatch_system_agent.yaml
```

Or install using Systemd:

```
# file /etc/systemd/system/overwatch-system-agent.service - example
[Unit]
Description=Overwatch basic agents - System agent
After=network.target
[Service]
Type=simple
ExecStart=/srv/overwatch-basic-agents/venv/bin/overwatch-system-agent /srv/overwatch-basic-agents/conf/system_agent.yaml
Restart=always
[Install]
WantedBy=multi-user.target
```

```shell
$ sudo systemctl enable overwatch-system-agent.service
$ sudo systemctl start overwatch-system-agent.service
```

