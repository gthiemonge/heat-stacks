#!/bin/sh

curl http://download.cirros-cloud.net/0.4.0/cirros-0.4.0-x86_64-disk.img > cirros-0.4.0-x86_64-disk.img

openstack image create --disk-format qcow2 --container-format bare --file cirros-0.4.0-x86_64-disk.img cirros-0.4.0-x86_64-disk
