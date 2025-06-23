from prometheus_client import start_http_server, Gauge
import requests
import time
import json
import requests

NIFI_API = "http://127.0.0.1:57214/nifi-api/process-groups/root/"

def get_all_processors():

    ## 
    url = f"{NIFI_API}" 
    group_ids = set()
    response = requests.get(url)
    process_groups = (response.json()["bulletins"])
    for process in process_groups:
        group_ids.add(process['groupId'])
    group_ids = list(group_ids)
    print(group_ids ) 
get_all_processors()