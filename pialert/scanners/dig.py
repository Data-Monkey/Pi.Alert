""" use DIG to resolve IP addresses """
import subprocess

import conf
from logger import mylog
from helper import check_ip_format
from scanners.pholusscan import clean_result

#-------------------------------------------------------------------------------

def resolve_device_name_dig (ip_address):
    """
    use DIG to resolve IP address
    https://linux.die.net/man/1/dig
    """

    new_name = ""

    try :
        dig_args = ['dig', '+short', '-x', ip_address]

        # Execute command
        try:
            # try runnning a subprocess
            new_name = subprocess.check_output (dig_args, universal_newlines=True)
        except subprocess.CalledProcessError as exception:
            # An error occured, handle it
            mylog('none', ['[device_name_dig] ', exception.output])
            # newName = "Error - check logs"
            return -1

        # Check returns
        new_name = new_name.strip()

        if len(new_name) == 0 :
            return -1

        # Cleanup
        new_name = clean_result(new_name)

        if new_name == "" or  len(new_name) == 0:
            return -1

        # Return newName
        return new_name

    # not Found
    except subprocess.CalledProcessError :
        return -1


#-------------------------------------------------------------------------------
def get_internet_ip ():
    """ use DIG to find the public IP of the modem """

    # BUGFIX #46 - curl http://ipv4.icanhazip.com repeatedly is very slow
    # Using 'dig'
    dig_args = ['dig', '+short'] + conf.DIG_GET_IP_ARG.strip().split()
    try:
        cmd_output = subprocess.check_output (dig_args,
                                              universal_newlines=True)
    except subprocess.CalledProcessError as exception:
        mylog('none', ['[DIG Get Internet IP] Error: ', exception.output])
        cmd_output = '' # no internet

    # Check result is an IP
    ip_address = check_ip_format (cmd_output)

    # Handle invalid response
    if ip_address == '':
        ip_address = '0.0.0.0'

    return ip_address

#-------------------------------------------------------------------------------
def get_dynamic_dns_ip ():
    """ use DIG to resolve the IP of the DDNS """

    # Using OpenDNS server
        # dig_args = ['dig', '+short', DDNS_DOMAIN, '@resolver1.opendns.com']

    # Using default DNS server
    dig_args = ['dig', '+short', conf.DDNS_DOMAIN]

    try:
        # try runnning a subprocess
        dig_output = subprocess.check_output (dig_args,
                                              universal_newlines=True)
    except subprocess.CalledProcessError as exception:
        # An error occured, handle it
        mylog('none', ['[DDNS] ERROR - ', exception.output])
        dig_output = '' # probably no internet

    # Check result is an IP
    ip_address = check_ip_format (dig_output)

    # Handle invalid response
    if ip_address == '':
        ip_address = '0.0.0.0'

    return ip_address
