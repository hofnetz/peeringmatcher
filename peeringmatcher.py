#!/usr/bin/env python
#
# Peering matcher 0.69
#
#   Written by Job Snijders <job@instituut.net>
#
# With significant contributions from:
#
#       Jerome Vanhoutte <jerome@dev252.org>
#       Tobias Rosenstock <tobias.rosenstock@hofnetz.de>
#       Christian Kroeger <christian.kroeger@bcix.de>
#
# To the extent possible under law, Job Snijders has waived all copyright
# and related or neighboring rights to this piece of code.
# This work is published from: The Netherlands.
#
# Install Guide:
#
# shell$ pip install mysql-python
# shell$ pip install 'prettytable>0.6.1' # version 0.6.1 or later
#
#
# Do not hesitate to send me patches/bugfixes/love ;-)

default_asn = 8283

import sys
from time import strftime, gmtime
import socket
import logging

LOGFORMAT = '%(levelname)s: %(message)s'
# Set level=logging.ERROR to turn off warn/info/debug noise.
logging.basicConfig(stream=sys.stderr, format=LOGFORMAT, level=logging.DEBUG)

import requests
from collections import Counter
from pprint import pprint
from prettytable import *

time = strftime("%Y-%m-%d %H:%M:%S", gmtime())


def _is_ipv4(ip):
    """ Return true if given arg is a valid IPv4 address
    """
    try:
        socket.inet_aton(ip)
    except socket.error:
        return False
    except exceptions.UnicodeEncodeError:
        return False
    return True


def _is_ipv6(ip):
    """ Return true if given arg is a valid IPv6 address
    """
    try:
        socket.inet_pton(socket.AF_INET6, ip)
    except socket.error, UnicodeEncodeError:
        return False
    except exceptions.UnicodeEncodeError:
        return False
    return True


def usage():
    print """Peering Matcher 0.42
usage: peeringmatcher.py ASN1 [ ASN2 ] [ ASN3 ] [ etc.. ]

    example: ./peeringmatcher.py 8283 16509

    peeringmatcher.py will do a lookup against the PeeringDB-API.
    In case a single ASN is given as an argument, the program will match
    against the default_asn variable, set in the header of the script.

    This is Public Domain code, with contributions from:

        Job Snijders <job@instituut.net>
        Jerome Vanhoutte <jerome@dev252.org>
        Tobias Rosenstock <tobias.rosenstock@hofnetz.de>
        Christian Kroeger <christian.kroeger@bcix.de>
"""
    sys.exit(1)

class PeeringMatcher:
    def __init__(self):
        logging.info("Peering Matcher 0.69, at your service.")
        
    def get_asn_info(self, asn_list):
        """ Get ASN info and return as dict
        """
        asns = {}
        row = {}
        logging.debug("asn_list: %s" % (asn_list))

        # Fetch the ASN list

        req = requests.get("https://peeringdb.com/api/net?asn__in=%(asns)s" % {'asns': ','.join(map(str, asn_list))}).json()['data']

        for net in req:
            as_name = net['name']
            asns[net['asn']] = { 'name': net['name'] }
            
        for asnum in asn_list:
            if asnum not in asns:
                raise KeyError("Following AS does not have a PeeringDB entry: %s" % (asnum) )       

        logging.debug("asns: %s" % (asns))
        return asns


    def get_common_pops(self, asn_list):
        """ Return a dict with common PoPs between networks
        """

        pops = {}
        commonpops = [] 
        allpops = []
        netfac = requests.get("https://peeringdb.com/api/netfac?local_asn__in=%(asns)s&depth=0" % {'asns': ','.join(map(str, asn_list))}).json()['data']
        for fac in netfac:
            allpops.append(fac['name'])
        logging.debug("allpops: %s" % (allpops))
        
        commonpops = [key for key, count in Counter(allpops).iteritems() if count >= len(asn_list)]
        logging.debug("commonpops: %s" % (commonpops))

        for pop_name in commonpops:
            if pop_name not in pops:
                pops[pop_name] = {}
            for asn in asn_list:
                if asn not in pops[pop_name]:
                    pops[pop_name][asn] = []

        logging.debug("pops: %s" % (pops))
        return pops


    def get_common_ixes(self, asn_list):
        """ Return a dict with common IXes between networks
        """

        # Fetch common facilities
        sql_ixes = """
            SELECT ix.name,
                   netixlan.asn,
                   netixlan.ipaddr4,
                   netixlan.ipaddr6
            FROM peeringdb_ixlan ixlan
            JOIN peeringdb_network_ixlan netixlan ON ixlan.id = netixlan.ixlan_id
            JOIN peeringdb_ix ix ON ixlan.ix_id = ix.id
            JOIN peeringdb_network net ON net.id = netixlan.net_id
            WHERE netixlan.asn IN (%(asns)s)
            AND ixlan.id in (
              SELECT ixlan.id
              FROM peeringdb_ixlan ixlan
              JOIN peeringdb_network_ixlan netixlan ON ixlan.id = netixlan.ixlan_id
              WHERE netixlan.asn IN (%(asns)s)
              GROUP BY ixlan.id
              HAVING COUNT(DISTINCT netixlan.asn) >= %(num_asns)s
              )
            ORDER BY ixlan.id, netixlan.asn;
            """ % { 'num_asns': len(asn_list), 'asns': ', '.join(map(str, asn_list)) }

        ixes = {}
        commonixes = []
        allixes = []
        allixlans = requests.get("https://peeringdb.com/api/netixlan?asn__in=%(asns)s&depth=0" % {'asns': ','.join(map(str, asn_list))}).json()['data']
        logging.debug("allixlans: %s" % (allixlans))
        for ixlan in allixlans:
            allixes.append((ixlan['ix_id']))
        logging.debug("allixes: %s" % (allixes))
        
        commonixes = [key for key, count in Counter(allixes).iteritems() if count >= len(asn_list)]
        logging.debug("commonixes: %s" % (commonixes))

        for ix_id in commonixes:
            ixname = requests.get("https://peeringdb.com/api/ix?id=%s" % (ix_id)).json()['data'][0]['name']
            if ixname not in ixes:
                ixes[ixname] = {}
            for asn in asn_list:
                if asn not in ixes[ixname]:
                    ixes[ixname][asn] = []
#                if _is_ipv4(allixlans['ipaddr4']):
#                    ixes[ixname][asn].append(ipaddr4)
#                if _is_ipv6(ipaddr6):
#                    ixes[ixname][asn].append(ipaddr6)


        logging.debug("ixes: %s" % (ixes))
        return ixes


#        for row in cursor.fetchall():
#            logging.debug(row)
#            ix_name = row[0]
#            asn = row[1]
#            local_ipaddr = row[2].strip().split('/')[0]
#
#            if ix_name not in ixes:
#                ixes[ix_name] = {}
#            if asn not in ixes[ix_name]:
#                ixes[ix_name][asn] = []

            # Peeringdb is unfortunately filled with crappy IP data. Filter the
            # shit from the database.
        
        
        logging.debug("ixes: %s" % (ixes))
        return ixes



def main(asn_list):
    # If no ASN is defined on the commandline, the default_asn is used
    if (default_asn not in asn_list) and (len(asn_list) == 1):
        asn_list.append(default_asn)

    pm = PeeringMatcher()
    asns = pm.get_asn_info(asn_list)

    # IXPs
    ixes = pm.get_common_ixes(asn_list)
    if (int(len(ixes)) > 0):
        ixes_header = ['IXP']
        for asn in asns:
            ixes_header.append("AS%s - %s" % (int(asn), asns[asn]['name']))
        ixes_table = PrettyTable(ixes_header)

        for ix_name in sorted(ixes):
            row = [ix_name]
            for asn in asns:
                row.append('\n'.join(ixes[ix_name][asn]))
            ixes_table.add_row(row)

        ixes_table.hrules = ALL
        print "Common IXPs according to PeeringDB - time of generation: %s" % (time)
        print ixes_table
    else:
        print "No common IXPs between ASNs %(asns)s according to PeeringDB - time of generation: %(time)s" % { 'asns': ', '.join(map(str, asn_list)), 'time': time }
    print ""

    # PoPs
    pops = pm.get_common_pops(asn_list)
    if (int(len(pops)) > 0):
        pops_header = ['Facility']
        for asn in asns:
            pops_header.append("AS%s - %s" % (int(asn), asns[asn]['name']))
        pops_table = PrettyTable(pops_header)

        for pop_name in sorted(pops):
            row = [pop_name]
            for asn in sorted(asns):
                row.append('\n'.join(pops[pop_name][asn]))
            pops_table.add_row(row)

        pops_table.hrules = ALL
        print "Common facilities according to PeeringDB - time of generation: %s" % (time)
        print pops_table
    else:
        print "No common facilities between ASNs %(asns)s according to PeeringDB - time of generation: %(time)s" % { 'asns': ', '.join(map(str, asn_list)), 'time': time }


if __name__ == '__main__':
    import optparse
    parser = optparse.OptionParser()

    options, args = parser.parse_args()

    # we need at least one ASN
    if len(args) < 1:
        usage()

    # Go through all the argument passed via the command line and look if these are integer
    for asn in args:
        try:
            asn = int(asn)
        except:
            logging.error('Please enter a valid ASN: %s' % (asn))
            sys.exit(1)

    # convert string to integer to be used after as key
    asn_list = map(int, args)

    # print pretty table
    main(asn_list)
