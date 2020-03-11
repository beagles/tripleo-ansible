#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (c) 2018 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import yaml

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.openstack import openstack_full_argument_spec
from ansible.module_utils.openstack import openstack_module_kwargs
from ansible.module_utils.openstack import openstack_cloud_from_module

# NOTE: This is still using the legacy clients. We've not
#       changed to using the OpenStackSDK fully because
#       tripleo-common expects the legacy clients. Once
#       we've updated tripleo-common to use the SDK we
#       should revise this.
from heatclient.v1 import client as heatclient
from mistralclient.api import client as mistral_client
from swiftclient import client as swift_client

from tripleo_common.utils import plan as plan_utils

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: tripleo_passwords_rotate

short_description: Rotate Passwords

version_added: "2.8"

description:
    - "Rotate Passwords."

options:
    container:
        description:
            - Overcloud plan container name
        default: overcloud
    password_list:
        description:
            - Password list to be rotated
        type: list
        default: []
        no_log: true
author:
    - Rabi Mishra (@ramishra)
'''

EXAMPLES = '''
- name: Rotate passwords and update plan
  tripleo_password_rotate:
      container: overcloud
      password_list: []
'''

RETURN = '''
passwords:
    description: Rotated passwords
    returned: always
    type: dict
    no_log: true
'''


def run_module():
    result = dict(
        success=False,
        error="",
        passwords={}
    )

    argument_spec = openstack_full_argument_spec(
        **yaml.safe_load(DOCUMENTATION)['options']
    )

    module = AnsibleModule(
        argument_spec,
        supports_check_mode=True,
        **openstack_module_kwargs()
    )

    def get_object_client(session):
        return swift_client.Connection(
            session=session,
            retries=10,
            starting_backoff=3,
            max_backoff=120)

    def get_orchestration_client(session):
        return heatclient.Client(
            session=session)

    def get_workflow_client(mistral_url, session):
        return mistral_client.client(
            mistral_url=mistral_url, session=session)

    try:
        container = module.params.get('container')
        password_list = module.params.get('password_list')
        _, conn = openstack_cloud_from_module(module)
        session = conn.session
        mistral_url = conn.workflow.get_endpoint()

        # if the user is working with this module in only check mode we do not
        # want to make any changes to the environment, just return the current
        # state with no modifications
        if module.check_mode:
            module.exit_json(**result)
        swift = get_object_client(session)
        heat = get_orchestration_client(session)
        mistral = get_workflow_client(mistral_url, session)
        rotated_passwords = plan_utils.generate_passwords(
            swift, heat, mistral, container,
            rotate_passwords=True,
            rotate_pw_list=password_list)
        result['success'] = True
        result['passwords'] = rotated_passwords
    except Exception as err:
        result['error'] = str(err)
        result['msg'] = ("Error rotating fernet keys for plan %s: %s" % (
            container, err))
        module.fail_json(**result)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
