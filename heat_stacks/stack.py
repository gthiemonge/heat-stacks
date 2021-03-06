#!/usr/bin/env python3

from __future__ import print_function
import sys
import os
import time
import yaml
import openstack
from heatclient.common import template_utils

def config_from_env():
    config = {}
    for k in ('auth_url', 'project_name', 'username',
              'password', 'region_name'):
        v = os.environ.get('OS_%s' % (k.upper()))
        config[k] = v
    return config


def stack_down(conn, stack_name):
    cur_stack = conn.orchestration.find_stack(stack_name)
    if cur_stack:
        print("Deleting stack %s" % (stack_name))
        conn.orchestration.delete_stack(stack_name)

        while conn.orchestration.find_stack(stack_name) is not None:
            time.sleep(1)

        print("Stack %s deleted" % (stack_name))

def _stack_dir():
    yield os.path.join(
        os.path.dirname(os.path.realpath(sys.argv[0])),
        "stacks")
    yield os.path.join(
        os.path.dirname(sys.modules[__name__].__file__),
        "..", "stacks")
    yield os.path.join(sys.prefix, "share/heat-stacks/stacks")

def stack_up(conn, stack_name):
    for stack_dir in _stack_dir():
        stack_file = os.path.join(stack_dir, "%s.yaml" % (stack_name))
        if os.path.exists(stack_file):
            break
    else:
        raise Exception("Cannot find '%s' stack." % (stack_name))

    dependencies = []

    with open(stack_file) as fp:
        for l in fp:
            l = l.strip()
            if len(l) > 2 and l[0] == '#':
                if l[2:].startswith('Depends-On: '):
                    dependencies.append(l[14:])

    for dep in dependencies:
        stack_up(conn, dep)

    with open(stack_file) as fp:
        config = yaml.safe_load(fp)

        if 'heat_template_version' in config:
            d = config['heat_template_version'].strftime('%Y-%m-%d')
            config['heat_template_version'] = d

    has_image = config.get('parameters', {}).get('image', None) is not None
    has_key_pair_path = config.get('parameters', {}).get('key_pair_path', None) is not None
    has_key_pair = config.get('parameters', {}).get('key_pair', None) is not None

    files, template = template_utils.process_template_path(stack_file)

    args = {
        'files': files,
        'template': template,
        'parameters': {},
        'name': stack_name,
        'tags': 'stack',
    }
    if has_image:
        args['parameters']['image'] = 'cirros-0.4.0-x86_64-disk'

    if has_key_pair_path:
        key_filename = os.path.expanduser('~/.ssh/id_rsa.pub')
        args['parameters']['key_pair_path'] = 'keys/id_rsa.pub'
        with open(key_filename) as fp:
            files['keys/id_rsa.pub'] = fp.read()

    if has_key_pair:
        args['parameters']['key_pair'] = 'keypair0'

    cur_stack = conn.orchestration.find_stack(stack_name)
    if cur_stack is None:
        print("Creating stack %s" % (stack_name))
        conn.orchestration.create_stack(**args)
    else:
        print("Updating stack %s" % (stack_name))
        conn.orchestration.update_stack(cur_stack.id, **args)

    while True:
        stack = conn.orchestration.get_stack(stack_name)
        if stack.status not in ('CREATE_IN_PROGRESS', 'UPDATE_IN_PROGRESS'):
            break

        time.sleep(1)

    print("Stack %s %s (%s)" % (stack_name, stack.status, stack.status_reason))

    print(yaml.safe_dump(stack.outputs,
                         default_flow_style=False,
                         explicit_start=True))

def stack_list(conn):
    for stack in conn.orchestration.stacks():
        if 'stack' in stack.tags:
            print(stack.name)

def main():
    try:
        action = sys.argv[1]
    except IndexError:
        print("usage: %s [list|up|down] <stack>" % (sys.argv[0]))
        sys.exit(1)

    try:
        stack_name = sys.argv[2]
    except IndexError:
        stack_name = "main"

    down = False
    up = False
    update = False
    list_stacks = False
    if action == "restart":
        down = True
        up = True
    elif action == "up":
        up = True
    elif action == "down":
        down = True
    elif action == "list":
        list_stacks = True
    else:
        print("Unknown action `%s'" % (action))
        sys.exit(1)

    openstack.enable_logging()

    conn = openstack.connect(**config_from_env())

    if list_stacks:
        stack_list(conn)
    if down:
        stack_down(conn, stack_name)
    if up:
        stack_up(conn, stack_name)

if __name__ == "__main__":
    main()
