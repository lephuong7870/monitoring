from prometheus_client import start_http_server, Gauge
import requests
import time



nifi_address_metric = Gauge('nifi_address', 'NiFi Address', ['address'])
nifi_status_metric = Gauge('nifi_status', 'NiFi Status', ['address', 'status'])
nifi_active_thread_count_metric = Gauge('nifi_active_thread_count', 'NiFi Active Thread Count', ['address'])
nifi_queued_metric = Gauge('nifi_queued', 'NiFi Queued', ['address'])

##
nifi_status_invoke = Gauge('nifi_status_invoke_api', 'NiFi Status Invoke', ['link_url', 'status' , 'message']) 
start_http_server(8000)


def get_nifi_down_or_up():
    nifi_cluster_urls = ['http://127.0.0.1:51567/nifi-api/controller/cluster']
    for url in nifi_cluster_urls:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            nodes = data['cluster']['nodes']
            nifi_status_metric.clear()
            for node in nodes:
                address = node.get('address')
                status = node.get('status')
                active_thread_count = node.get('activeThreadCount', 0)
                queued = node.get('queued')
                if queued:
                    queued_value = queued.split(' / ')[0]
                    queued_unit = queued.split(' / ')[1]
                else:
                    queued_value = 0
                    queued_unit = ''
                nifi_address_metric.labels(address).set(1)
                if status == "DISCONNECTED":
                    nifi_status_metric.labels(address, status).set(0)
                else:
                    nifi_status_metric.labels(address, status).set(1)
                nifi_active_thread_count_metric.labels(address).set(active_thread_count)
                nifi_queued_metric.labels(address).set(int(queued_value))
            break
    else:
        nifi_address_metric.labels('').set(0)
        nifi_status_metric.labels('', '').set(0)
        nifi_active_thread_count_metric.labels('').set(0)
        nifi_queued_metric.labels('').set(0)

def get_nifi_metrics_processor():
    group_ids = ['72b631e9-c19a-1e7d-0000-000015baeb37']
    NIFI_API = "http://127.0.0.1:51567/nifi-api/flow/process-groups"
    for id  in group_ids:
        url = f"{NIFI_API}/{id}" 
        response = requests.get(url)
        if response.status_code == 200:
            
            temp = response.json()["processGroupFlow"]['flow']['connections']
            all_processors = set()

            for i in temp:
                if i['component']['source']['name'] == 'InvokeHTTP' : 
                    all_processors.add( i['component']['source']['id'])
            all_processors = list(all_processors)

            processer_url = 'http://127.0.0.1:51567/nifi-api/processors'
            for i in all_processors:
                url = f'{processer_url}/{i}'
                response = requests.get(url)
                status = None
                message = ""
                temp = response.json()
                if temp['bulletins'] == []:
                    status = 'SUCCESS'
                else:
                    status = temp['bulletins'][0]['bulletin']['level']
                    message = temp['bulletins'][0]['bulletin']['message']
                link_url = temp['component']['config']['properties']['Remote URL'] 

                if status == 'ERROR':
                    nifi_status_invoke.labels(link_url, status , message).set(0)
                else:
                    nifi_status_invoke.labels(link_url , status , message).set(1)
        else:
            nifi_status_invoke.labels('', '' , '').set(0)

while True:
    get_nifi_down_or_up()
    get_nifi_metrics_processor()
    time.sleep(10)