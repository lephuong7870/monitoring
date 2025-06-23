from prometheus_client import start_http_server, Gauge , Summary, Counter, Info
import requests
import time
import os
import json




nifi_address_metric = Gauge('nifi_address', 'NiFi Address', ['address'])
nifi_status_metric = Gauge('nifi_status', 'NiFi Status', ['address', 'status'])
nifi_active_thread_count_metric = Gauge('nifi_active_thread_count', 'NiFi Active Thread Count', ['address'])
nifi_queued_metric = Gauge('nifi_queued', 'NiFi Queued', ['address'])

##
nifi_status_invoke = Counter('nifi_status_invoke_api', 'NiFi Status Invoke', ['group_name' , 'id_processor' , 'link_url', 'status' , 'message' ]) 
nifi_status_processors = Counter('nifi_status_processors_api', 'NiFi Status Processor', [ 'group_name',  'id_processor' , 'nameType' , 'status' , 'message' ])  
nifi_status_kafka  =  Counter('nifi_status_kafka_connect', 'NiFi Status Kafka Connect', ['group_name',   'id_processor'  , 'topic' , 'broker' , 'nameType',  'status' ]) 

## nifi-http.default.svc.cluster.local


def get_nifi_down_or_up( nifi_svc  ):
    nifi_cluster_urls = [f'http://{nifi_svc}/nifi-api/controller/cluster']
    for url in nifi_cluster_urls:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            nodes = data['cluster']['nodes']

            nifi_status_metric.clear()
            nifi_address_metric.clear()
            nifi_active_thread_count_metric.clear()
            nifi_queued_metric.clear()

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
                queued_value =  queued_value.replace(',', '')
                nifi_queued_metric.labels(address).set(int(queued_value))
            break
    else:
        nifi_address_metric.labels('').set(0)
        nifi_status_metric.labels('', '').set(0)
        nifi_active_thread_count_metric.labels('').set(0)
        nifi_queued_metric.labels('').set(0)

def get_nifi_metrics_processor( group_ids ,nifi_svc  ):
    
    NIFI_API = f"http://{nifi_svc}/nifi-api/flow/process-groups"
    
    for id  in group_ids:
        url = f"{NIFI_API}/{id}" 
        response = requests.get(url)
        if response.status_code == 200:

            temp = response.json()
            nameGroup = temp['processGroupFlow']['breadcrumb']['breadcrumb']['name']
         

            temp = temp["processGroupFlow"]['flow']['connections']
            all_processors = set()

            for i in temp:
                all_processors.add( i['component']['source']['id'])
            all_processors = list(all_processors)

            processer_url = f'http://{nifi_svc}/nifi-api/processors'
            for i in all_processors:
                url = f'{processer_url}/{i}'
                response = requests.get(url)
                status = None
                message = ""
                temp = response.json()

                nameType = temp['status']['name']
                id_processor = i 

                if temp['bulletins'] == []:
                    status = 'SUCCESS'
                else:
                   
                    status = temp['bulletins'][0]['bulletin']['level']
                    message = temp['bulletins'][0]['bulletin']['message']
                

                if (status == 'ERROR' ) and ( nameType == "InvokeHTTP" ) :
                    link_url = temp['component']['config']['properties']['Remote URL'] 
                    nifi_status_invoke.labels( nameGroup , id_processor , link_url, status , message).inc()
                elif (status == 'SUCCESS' ) and ( nameType == "InvokeHTTP" ) : 
                    link_url = temp['component']['config']['properties']['Remote URL'] 
                    nifi_status_invoke.labels( nameGroup , id_processor , link_url , status , message).inc()
                elif 'Kafka' in nameType:
                    try:
                        nameTopic = temp['component']['config']['properties']['topic'] 
                        broker    = temp['component']['config']['properties']['bootstrap.servers']  
                    except:
                        nameTopic = ''
                        broker    = ''
                    nifi_status_kafka.labels( nameGroup , id_processor , nameTopic , broker , nameType , status ).inc()
       
                else:
                    pass  
                
                if status == 'ERROR' : 
                    nifi_status_processors.labels( nameGroup , id_processor , nameType , status , message   ).inc()
                else:
                    nifi_status_processors.labels( nameGroup , id_processor , nameType , status , message   ).inc()

        else:
            nifi_status_invoke.labels( '' , '' , '', '' , '').inc()
            nifi_status_processors.labels( '' , '' , '' , '' , ''   ).inc()
            nifi_status_kafka.labels( '' , '' , '' , '' , '', ''   ).inc()

#group_ids  =   os.environ.get("GROUP_IDS")
#nifi_svc   = os.environ.get("NIFI_SVC")
group_ids = [  "ddcb79b2-d5b3-3a72-8bad-32fa05636f81" , "c3b7a254-da30-3abb-9b58-318968ad5239" ]
nifi_svc = "127.0.0.1:52532"
start_http_server(8000)

while True:
    
    get_nifi_down_or_up(nifi_svc )
    #try:
    #  group_ids = json.loads( group_ids) 
    #except:
    #  group_ids = []
    get_nifi_metrics_processor( group_ids , nifi_svc )
    time.sleep(15) 
    