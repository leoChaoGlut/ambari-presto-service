# -*- coding: utf-8 -*-
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os.path as path
import uuid

from common import PRESTO_TAR_URL, PRESTO_TAR_NAME, PRESTO_HOME, create_connectors, \
    delete_connectors
from resource_management.core.exceptions import ExecutionFailed, ComponentIsNotRunning
from resource_management.core.resources.system import Execute
from resource_management.libraries.script.script import Script


class Worker(Script):
    def install(self, env):
        from params import java_home
        Execute('wget --no-check-certificate {0} -O /tmp/{1}'.format(PRESTO_TAR_URL, PRESTO_TAR_NAME))
        Execute('export JAVA8_HOME={0} && tar -xf /tmp/{1} -C {2} --strip-components 1'.format(java_home, PRESTO_TAR_NAME, PRESTO_HOME))
        Execute('mkdir {0}/etc || echo "true"'.format(PRESTO_HOME))
        self.configure(env)

    def stop(self, env):
        from params import daemon_control_script
        Execute('{0} stop'.format(daemon_control_script))

    def start(self, env):
        from params import daemon_control_script
        self.configure(self)
        Execute('{0} start'.format(daemon_control_script))
        Execute('echo worker - $?')

    def status(self, env):
        from params import daemon_control_script
        try:
            Execute('{0} status'.format(daemon_control_script))
        except ExecutionFailed as ef:
            if ef.code == 3:
                raise ComponentIsNotRunning("ComponentIsNotRunning")
            else:
                raise ef

    def configure(self, env):
        from params import node_properties, jvm_config, config_properties, \
            config_directory, memory_configs, connectors_to_add, connectors_to_delete
        key_val_template = '{0}={1}\n'

        with open(path.join(config_directory, 'node.properties'), 'w') as f:
            for key, value in node_properties.iteritems():
                f.write(key_val_template.format(key, value))
            f.write(key_val_template.format('node.id', str(uuid.uuid4())))
            f.write(key_val_template.format('node.data-dir', '/var/lib/presto'))

        with open(path.join(config_directory, 'jvm.config'), 'w') as f:
            f.write(jvm_config['jvm.config'])

        with open(path.join(config_directory, 'config.properties'), 'w') as f:
            for key, value in config_properties.iteritems():
                if key == 'query.queue-config-file' and value.strip() == '':
                    continue
                if key in memory_configs:
                    value += 'GB'
                f.write(key_val_template.format(key, value))
            f.write(key_val_template.format('coordinator', 'false'))

        create_connectors(node_properties, connectors_to_add)
        delete_connectors(node_properties, connectors_to_delete)
        # This is a separate call because we always want the tpch connector to
        # be available because it is used to smoketest the installation.
        create_connectors(node_properties, '{"tpch": ["connector.name=tpch"]}')


if __name__ == '__main__':
    Worker().execute()
