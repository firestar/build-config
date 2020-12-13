from kubernetes import client, config
from functools import reduce
from mergedeep import merge
import csv
from jinja2 import Environment, FileSystemLoader, select_autoescape
env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=select_autoescape(['conf'])
)

print("Loading service mapping")

template = None
with open('templates/nginx.conf', 'r') as nginx:
    template = env.get_template('nginx.conf')

with open("services.csv", 'r') as csv_data:
    service_mapping = csv.reader(csv_data, delimiter=',')
    next(service_mapping, None)  # ignore header
    service_mapping = list(map(lambda p: dict(
        {
            p[0]: {  # namespace
                p[1]: {  # service name
                    'service_port': p[2],
                    'nginx_domain': p[3],
                    'nginx_port': p[4]
                }
            }
        }
    ), service_mapping))
    service_mapping = reduce(merge, service_mapping)

    config.load_kube_config("kube/config")

    hosts = []

    v1 = client.CoreV1Api()

    print("Fetching node ips for active nodes")
    nodes = v1.list_node()
    for n in nodes.items:
        for c in n.status.conditions:
            if c.type == 'Ready':
                if c.status == 'True':
                    for a in n.status.addresses:
                        hosts.append(a.address)

    ret = v1.list_service_for_all_namespaces(watch=False)
    for i in ret.items:
        if i.metadata.namespace in service_mapping.keys() and i.metadata.name in service_mapping[i.metadata.namespace].keys():
            item = service_mapping[i.metadata.namespace][i.metadata.name]
            print("======================================================")
            print('%s / %s' % (i.metadata.namespace, i.metadata.name))
            backends = []
            if i.spec.type == 'LoadBalancer':
                item_hosts = []
                for g in i.status.load_balancer.ingress:
                    item_hosts.append(g.ip)
                for port in i.spec.ports:
                    if str(port.port) == item['service_port']:
                        for ip in item_hosts:
                            backends.append('%s:%s' % (ip, port.port))
                #print(i.spec.load_balancer_ip)
            elif i.spec.type == 'NodePort':
                item_hosts = hosts
                for port in i.spec.ports:
                    if str(port.port) == item['service_port']:
                        for ip in item_hosts:
                            backends.append('%s:%s' % (ip, port.node_port))
            print('%s => %s:%s' % (backends, item['nginx_domain'], item['nginx_port']))
            with open('output/%s-%s.conf' % (i.metadata.name, i.metadata.namespace), 'w') as nginx_config:
                nginx_config.write(
                    template.render({
                        'name': i.metadata.name,
                        'namespace': i.metadata.namespace,
                        'nginx_domain': item['nginx_domain'],
                        'nginx_port': item['nginx_port'],
                        'backends': backends
                    })
                )
                nginx_config.close()
        # print(vars(i.load_balancer_ip))
        # print(vars(i.ports[0].port))
