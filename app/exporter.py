from prometheus_client import start_http_server, Gauge , Counter, generate_latest , REGISTRY , CollectorRegistry
import requests
import time
import os
import json
import logging
from flask import Flask, Response, jsonify



app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


registry=CollectorRegistry()

nifi_address_metric = Gauge('nifi_address', 'NiFi Address', ['address'] ,registry=registry)
nifi_status_metric = Gauge('nifi_status', 'NiFi Status', ['address', 'status'],registry=registry)
nifi_active_thread_count_metric = Gauge('nifi_active_thread_count', 'NiFi Active Thread Count', ['address'],registry=registry)
nifi_queued_metric = Gauge('nifi_queued', 'NiFi Queued', ['address'],registry=registry)

##

nifi_status_invoke = Counter('nifi_status_invoke_api', 'NiFi Status Invoke', ['group_name' , 'id_processor' , 'link_url', 'status' , 'message' , 'run_status' ] , registry=registry)  
nifi_status_processors = Counter('nifi_status_processors_api', 'NiFi Status Processor', [ 'group_name',  'id_processor' , 'nameType' , 'status' , 'message' , 'run_status' ] , registry=registry)  
nifi_status_kafka  =  Counter('nifi_status_kafka_connect', 'NiFi Status Kafka Connect', ['group_name',   'id_processor'  , 'topic' , 'broker' , 'nameType',  'status'  , 'run_status' ] ,  registry=registry) 

## 
nifi_running_count  = Gauge( 'nifi_running_count' , 'NiFi Running Count Metric' , [ 'group_name'] , registry=registry) 
nifi_stopped_count  = Gauge( 'nifi_stopped_count' , 'NiFi Stopped Count Metric' , [ 'group_name'] , registry=registry) 
nifi_invalid_count  = Gauge( 'nifi_invalid_count' , 'NiFi Invalid Count Metric' , [ 'group_name'] , registry=registry) 

nifi_error_count  = Gauge( 'nifi_error_count' , 'NiFi Error Count Metric' , [ 'group_name'] , registry=registry) 


## nifi-http.default.svc.cluster.local


def initial():
    nifi_url_api  = os.environ.get("NIFI_URL_API")
    group_ids  =   os.environ.get("GROUP_IDS")
    try:
        group_ids = json.loads( group_ids) 
    except:
        group_ids = []

    def get_all_processor( id : str ):
        all_process_element= []
        ## 
        url1 = f'{nifi_url_api}/nifi-api/process-groups/{id}/processors'
        response = requests.get(url1) 
        
        try:
            temp = response.json()
            temp  = temp['processors'] 
            for i in temp:
                info_id = i["component"]["id"]
                all_process_element.append( info_id )
        except:
            pass 
        ## 
        url2 = f'{nifi_url_api}/nifi-api/process-groups/{id}/process-groups'
        response = requests.get(url2) 
        try:
            temp = response.json()
            temp =  temp['processGroups']
            for element in temp:
                id_group  = element["component"]["id"]
                all_process_element += get_all_processor( id_group )

        except:
            pass 
        
        return all_process_element 
    

    ## Logging ##Number 1
    nifi_cluster_urls = [f'{nifi_url_api}/nifi-api/controller/cluster']
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


    ## Logging ##Number 2 
    NIFI_API = f"{nifi_url_api}/nifi-api/flow/process-groups"

    nifi_error_count.clear()
    nifi_running_count.clear()
    nifi_stopped_count.clear()
    nifi_invalid_count.clear()

    for id  in group_ids:
        running_count = 0 
        stopped_count = 0 
        invalid_count = 0 
        error_count = 0

        url = f"{NIFI_API}/{id}" 
        response = requests.get(url)
        if response.status_code == 200:
            temp = response.json()
            nameGroup = temp['processGroupFlow']['breadcrumb']['breadcrumb']['name']

            all_processors = get_all_processor( id )

            processer_url = f'{nifi_url_api}/nifi-api/processors'
            for i in all_processors:
                url = f'{processer_url}/{i}'
                response = requests.get(url)
                status = None
                message = ""
                temp = response.json()

                nameType = temp['status']['name']
                runStatus = temp['status']['runStatus'] 
                
                if runStatus == 'Running' :
                    running_count +=1 
                elif runStatus == 'Stopped' :
                    stopped_count +=1 
                else:
                    invalid_count +=1 

                id_processor = i 

                if temp['bulletins'] == []:
                    status = 'SUCCESS'
                else:
                    status = temp['bulletins'][0]['bulletin']['level']
                    message = temp['bulletins'][0]['bulletin']['message']

                if (status == 'ERROR' ) and ( nameType == "InvokeHTTP" ) :
                    link_url = temp['component']['config']['properties']['Remote URL'] 
                    nifi_status_invoke.labels( nameGroup , id_processor , link_url, status , message , runStatus ).inc()
                elif (status == 'SUCCESS' ) and ( nameType == "InvokeHTTP" ) : 
                    link_url = temp['component']['config']['properties']['Remote URL'] 
                    nifi_status_invoke.labels( nameGroup , id_processor , link_url , status , message , runStatus ).inc()
                elif 'Kafka' in nameType:
                    try:
                        nameTopic = temp['component']['config']['properties']['topic'] 
                        broker    = temp['component']['config']['properties']['bootstrap.servers']  
                    except:
                        nameTopic = ''
                        broker    = ''
                    nifi_status_kafka.labels( nameGroup , id_processor , nameTopic , broker , nameType , status , runStatus ).inc()
       
                else:
                    pass  
                
                if status == 'ERROR' and runStatus == 'Running' : 
                    error_count += 1 
                    nifi_status_processors.labels( nameGroup , id_processor , nameType , status , message , runStatus   ).inc()
                else:
                    nifi_status_processors.labels( nameGroup , id_processor , nameType , status , message , runStatus  ).inc()

            
            nifi_error_count.labels(nameGroup ).set(error_count)
            nifi_running_count.labels(nameGroup ).set(running_count)
            nifi_stopped_count.labels(nameGroup ).set(stopped_count)
            nifi_invalid_count.labels(nameGroup ).set(invalid_count)         
        else:
            nifi_status_invoke.labels( '' , '' , '', '' , '').inc()
            nifi_status_processors.labels( '' , '' , '' , '' , ''   ).inc()
            nifi_status_kafka.labels( '' , '' , '' , '' , '', ''   ).inc()

    logger.info('Received request on root endpoint')
    return 'Logging App!'


@app.route('/metrics')
def metrics():
    initial()
    data = generate_latest(registry)
    return Response(data, mimetype='text/plain')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
