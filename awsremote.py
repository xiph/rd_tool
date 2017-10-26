#!/usr/bin/env python3

import boto3
from utility import *
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
        rd_print(None,e)

def start_machines(num_instances_to_use, aws_group_name):
    #switch on more machines if we need them
    if num_instances < num_instances_to_use:
        rd_print(None,'Launching instances...')
        autoscale.set_desired_capacity(
            AutoScalingGroupName = aws_group_name,
            DesiredCapacity = num_instances_to_use
        )

        #tell us status every few seconds
        while num_instances < num_instances_to_use:
            instances = get_instances_in_group(autoscale, aws_group_name)
            num_instances = len(instances)
            rd_print(None,'Number of instances online:', num_instances)
            sleep(3)

def get_machines(num_instances_to_use, aws_group_name):
    machines = []
    #connect to AWS
    ec2 = boto3.client('ec2');
    autoscale = boto3.client('autoscaling');

    #how many machines are currently running?
    instances = get_instances_in_group(autoscale, aws_group_name)
    num_instances = len(instances)
    rd_print(None,'Number of instances online:', num_instances)

    #grab instance IDs
    instance_ids = [i['InstanceId'] for i in instances]
    rd_print(None,"These instances are online:",instance_ids)
    running_instance_ids = []
    for instance_id in instance_ids:
        try:
            state = state_name_of(instance_id, ec2)
            if state == 'running':
                rd_print(None,instance_id, 'is running!')
                running_instance_ids.append(instance_id)
        except IndexError:
            print(instance_id, 'not queryable yet')
    ok_instance_ids = []
    for instance_id in running_instance_ids:
        try:
            if status_of(instance_id, ec2) == 'ok':
                rd_print(None,instance_id,'reported OK!')
                ok_instance_ids.append(instance_id)
        except IndexError:
            rd_print(None,'Instance',instance_id,'disappeared!')
    for instance_id in ok_instance_ids:
        machines.append(Machine(ip_address_of(instance_id, ec2)))
    return machines
