#!/usr/bin/env python3

import boto3
from utility import get_time
from time import sleep
import subprocess
import sys
from sshslot import *

# Returns true if an instance exists
def instance_exists(instance, ec2):
    status = ec2.describe_instance_status(InstanceIds=[instance])

    return len(status['InstanceStatuses']) > 0

# These status inquiries return huge dictionaries which must be almost entirely ignored.
# They provide a filter but I couldn't get it to work (and it required an extra 6 lines
# to use it).
def state_name_of(instance, ec2):
    status = ec2.describe_instance_status(InstanceIds=[instance])

    # Returns one of the values in the previous call.
    return status['InstanceStatuses'][0]['InstanceState']['Name']

# This is similar to `state_name_of()` which also ignores almost all values from the
# given dictionary.
def status_of(instance, ec2):
    status = ec2.describe_instance_status(InstanceIds=[instance])

    # Returns one of the values in the previous call.
    return status['InstanceStatuses'][0]['InstanceStatus']['Status']

# Again, similar to `state_name_of()`
def ip_address_of(instance, ec2):
    address = ec2.describe_instances(InstanceIds=[instance])

    if len(address['Reservations']) < 1 or len(address['Reservations'][0]['Instances']) < 1:
        print('There is no public IP address available for instance', instance)
        sys.exit(1)
    else:
        # Returns one of the values in the previous call.
        return address['Reservations'][0]['Instances'][0]['PublicIpAddress']

def get_instances_in_group(autoscale, aws_group_name):
    all_instances = autoscale.describe_auto_scaling_instances()['AutoScalingInstances']
    instances = []
    for instance in all_instances:
        if instance['AutoScalingGroupName'] == aws_group_name:
            instances.append(instance)
    return instances

def stop_machines(aws_group_name):
    try:
        ec2 = boto3.client('ec2');
        autoscale = boto3.client('autoscaling');
        autoscale.set_desired_capacity(
            AutoScalingGroupName = aws_group_name,
            DesiredCapacity = 0
        )
    except Exception as e:
        print(get_time(),e)

def get_machines(num_instances_to_use, aws_group_name):
    machines = []
    #connect to AWS
    ec2 = boto3.client('ec2');
    autoscale = boto3.client('autoscaling');

    #how many machines are currently running?
    instances = get_instances_in_group(autoscale, aws_group_name)
    num_instances = len(instances)
    print(get_time(),'Number of instances online:', num_instances)

    #switch on more machines if we need them
    if num_instances < num_instances_to_use:
        print(get_time(),'Launching instances...')
        autoscale.set_desired_capacity(
            AutoScalingGroupName = aws_group_name,
            DesiredCapacity = num_instances_to_use
        )

        #tell us status every few seconds
        while num_instances < num_instances_to_use:
            instances = get_instances_in_group(autoscale, aws_group_name)
            num_instances = len(instances)
            print(get_time(),'Number of instances online:', num_instances)
            sleep(3)

    #grab instance IDs
    instance_ids = [i['InstanceId'] for i in instances]
    print(get_time(),"These instances are online:",instance_ids)

    for instance_id in instance_ids:
        print(get_time(),'Waiting for instance',instance_id,'to boot...')
        while True:
            try:
                state = state_name_of(instance_id, ec2)
                if state == 'running':
                    print(get_time(),instance_id, 'is running!')
                    break
                elif state == 'pending':
                    pass
                else:
                    print(instance_id, 'in state',state,', not usable')
                    return []
            except IndexError:
                print(instance_id, 'not queryable yet')
                return []
            sleep(3)
    for instance_id in instance_ids:
        print(get_time(),'Waiting for instance',instance_id,'to report OK...')
        while True:
            try:
                if status_of(instance_id, ec2) == 'ok':
                    print(get_time(),instance_id,'reported OK!')
                    break
            except IndexError:
                print(get_time(),'Instance',instance_id,'disappeared!')
                return []
            sleep(3)
    for instance_id in instance_ids:
        machines.append(Machine(ip_address_of(instance_id, ec2)))
    return machines

def get_slots(machines):
    slots = []
    #by doing the machines in the inner loop,
    #we end up with heavy jobs split across machines better
    for i in range(0,32):
        for machine in machines:
            slots.append(Slot(machine))
    return slots
