"""
Module to manage MQTT as a publisher
"""
# pylint: disable=line-too-long

import time
import re
from paho.mqtt import client as mqtt_client

import conf
from logger import mylog
from database import get_all_devices, get_device_stats
from helper import bytes_to_string, sanitize_string



#-------------------------------------------------------------------------------
# MQTT
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
def check_config():
    """"
    check that all the required configuration parameters are set
    """
    if ( conf.MQTT_BROKER == '' or conf.MQTT_PORT == '' or
         conf.MQTT_USER == '' or conf.MQTT_PASSWORD == ''):
        mylog('none', ['[Check Config] Error: MQTT service not set up correctly. Check your pialert.conf MQTT_* variables.'])
        return False
    else:
        return True


#-------------------------------------------------------------------------------
class SensorConfig:
    """ class to hold a home assistant MQTT sensor configuration """
    def __init__(self, device_id, device_name, sensor_type, sensor_name, icon):
        self.device_id = device_id
        self.device_name = device_name
        self.sensor_type = sensor_type
        self.sensor_name = sensor_name
        self.icon = icon
        self.hash = str(hash(str(device_id) +
                             str(device_name)+
                             str(sensor_type)+
                             str(sensor_name)+
                             str(icon)))

#-------------------------------------------------------------------------------

def publish_mqtt(client, topic, message):
    """ publishing the devices to MQTT """
    status = 1
    while status != 0:
        result = client.publish(
                topic=topic,
                payload=message,
                qos=conf.MQTT_QOS,
                retain=True,
            )

        status = result[0]

        if status != 0:
            mylog('info', ["Waiting to reconnect to MQTT broker"])
            time.sleep(0.1)
    return True

#-------------------------------------------------------------------------------
def create_generic_device(client):
    """ generic device for PiAlert as a platform """

    device_name = 'PiAlert'
    device_id = 'pialert'

    create_sensor(client, device_id, device_name, 'sensor', 'online', 'wifi-check')
    create_sensor(client, device_id, device_name, 'sensor', 'down', 'wifi-cancel')
    create_sensor(client, device_id, device_name, 'sensor', 'all', 'wifi')
    create_sensor(client, device_id, device_name, 'sensor', 'archived', 'wifi-lock')
    create_sensor(client, device_id, device_name, 'sensor', 'new', 'wifi-plus')
    create_sensor(client, device_id, device_name, 'sensor', 'unknown', 'wifi-alert')


#-------------------------------------------------------------------------------
def create_sensor(client, device_id, device_name, sensor_type, sensor_name, icon):
    """ create and publish new sensors """

    new_sensor_config = SensorConfig(device_id, device_name, sensor_type, sensor_name, icon)

    # check if config already in list and if not, add it, otherwise skip
    is_unique = True

    for sensor in conf.mqtt_sensors:
        if sensor.hash == new_sensor_config.hash:
            is_unique = False
            break

    # save if unique
    if is_unique:
        publish_sensor(client, new_sensor_config)




#-------------------------------------------------------------------------------
def publish_sensor(client, sensor_conf: SensorConfig ):
    """ publish the sensor to MQTT """
    message = '{ \
                "name":"'+ sensor_conf.device_name +' '+sensor_conf.sensor_name+'", \
                "state_topic":"system-sensors/'+sensor_conf.sensor_type+'/'+sensor_conf.device_id+'/state", \
                "value_template":"{{value_json.'+sensor_conf.sensor_name+'}}", \
                "unique_id":"'+sensor_conf.device_id+'_sensor_'+sensor_conf.sensor_name+'", \
                "device": \
                    { \
                        "identifiers": ["'+sensor_conf.device_id+'_sensor"], \
                        "manufacturer": "PiAlert", \
                        "name":"'+sensor_conf.device_name+'" \
                    }, \
                "icon":"mdi:'+sensor_conf.icon+'" \
                }'

    topic='homeassistant/'+sensor_conf.sensor_type+'/'+sensor_conf.device_id+'/'+sensor_conf.sensor_name+'/config'

    # add the sensor to the global list to keep track of succesfully added sensors
    if publish_mqtt(client, topic, message):
                                     # hack - delay adding to the queue in case the process is
        time.sleep(conf.MQTT_DELAY_SEC)   # restarted and previous publish processes aborted
                                     # (it takes ~2s to update a sensor config on the broker)
        conf.mqtt_sensors.append(sensor_conf)

#-------------------------------------------------------------------------------
def mqtt_create_client():
    """create MQTT client"""

    def on_disconnect(client, userdata, rc):
        conf.mqtt_connected_to_broker = False

        # not sure is below line is correct / necessary
        # client = mqtt_create_client()

    def on_connect(client, userdata, flags, rc):

        if rc == 0:
            mylog('verbose', ["        Connected to broker"])
            conf.mqtt_connected_to_broker = True     # Signal connection
        else:
            mylog('none', ["        Connection failed"])
            conf.mqtt_connected_to_broker = False


    client = mqtt_client.Client('PiAlert')   # Set Connecting Client ID
    client.username_pw_set(conf.MQTT_USER, conf.MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect(conf.MQTT_BROKER, conf.MQTT_PORT)
    client.loop_start()

    return client

#-------------------------------------------------------------------------------
def mqtt_start(db):
    """ 
    starting the MQTT connection
    this is the main part of the MQTT publisher
    """

    #global client

    if conf.mqtt_connected_to_broker is False:
        conf.mqtt_connected_to_broker = True
        conf.client = mqtt_create_client()

    client = conf.client
    # General stats

    # Create a generic device for overal stats
    create_generic_device(client)

    # Get the data
    row = get_device_stats(db)

    columns = ["online","down","all","archived","new","unknown"]

    payload = ""

    # Update the values
    for column in columns:
        payload += '"'+column+'": ' + str(row[column]) +','

    # Publish (warap into {} and remove last ',' from above)
    publish_mqtt(client, "system-sensors/sensor/pialert/state",
            '{ \
                '+ payload[:-1] +'\
            }'
        )


    # Specific devices

    # Get all devices
    devices = get_all_devices(db)

    sec_delay = len(devices) * int(conf.MQTT_DELAY_SEC)*5

    mylog('info', ["        Estimated delay: ", (sec_delay), 's ', '(', round(sec_delay/60,1) , 'min)' ])

    for device in devices:
        # Create devices in Home Assistant - send config messages
        device_id = 'mac_' + device["dev_MAC"].replace(" ", "").replace(":", "_").lower()
        device_name_display = re.sub('[^a-zA-Z0-9-_\s]', '', device["dev_Name"])

        create_sensor(client, device_id, device_name_display, 'sensor', 'last_ip', 'ip-network')
        create_sensor(client, device_id, device_name_display, 'binary_sensor', 'is_present', 'wifi')
        create_sensor(client, device_id, device_name_display, 'sensor', 'mac_address', 'folder-key-network')
        create_sensor(client, device_id, device_name_display, 'sensor', 'is_new', 'bell-alert-outline')
        create_sensor(client, device_id, device_name_display, 'sensor', 'vendor', 'cog')

        # update device sensors in home assistant

        publish_mqtt(client, 'system-sensors/sensor/'+device_id+'/state',
            '{ \
                "last_ip": "' + device["dev_LastIP"] +'", \
                "is_new": "' + str(device["dev_NewDevice"]) +'", \
                "vendor": "' + sanitize_string(device["dev_Vendor"]) +'", \
                "mac_address": "' + str(device["dev_MAC"]) +'" \
            }'
        )

        publish_mqtt(client, 'system-sensors/binary_sensor/'+device_id+'/state',
            '{ \
                "is_present": "' + to_binary_sensor(str(device["dev_PresentLastScan"])) +'"\
            }'
        )

        # delete device / topic
        #  homeassistant/sensor/mac_44_ef_bf_c4_b1_af/is_present/config
        # client.publish(
        #     topic="homeassistant/sensor/"+deviceId+"/is_present/config",
        #     payload="",
        #     qos=1,
        #     retain=True,
        # )
    # time.sleep(10)


#===============================================================================
# Home Assistant UTILs
#===============================================================================
def to_binary_sensor(value):
    """ convert charcter to binary on/off that home assistant understands """

    # In HA a binary sensor returns ON or OFF
    result = "OFF"

    # bytestring
    if isinstance(value, str):
        if value == "1":
            result = "ON"
    elif isinstance(value, int):
        if value == 1:
            result = "ON"
    elif isinstance(value, bool):
        if value is True:
            result = "ON"
    elif isinstance(value, bytes):
        if bytes_to_string(value) == "1":
            result = "ON"
    return result
