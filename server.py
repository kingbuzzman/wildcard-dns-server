from __future__ import print_function

import os
import sys
import re
import json
import string

from twisted.internet import reactor, defer
from twisted.names import client, dns, error, server

class DynamicResolver(client.Resolver):
    """
    A resolver which implements xip.io style IP resolution based on name.
    as well as more conventional glob style DNS wildcard mapping. If no
    match will fallback to specified DNS server for lookup.

    """


    def __init__(self, servers, wildcard_domain, mapped_hosts=None,
            debug_level=0):

        client.Resolver.__init__(self, servers=servers)

        self._debug_level = debug_level

        if self._debug_level > 0:
            print('nameservers %s' % servers, file=sys.stderr)

        # Create regex pattern corresponding to xip.io style DNS
        # wilcard domain.

        pattern = (r'.*\.(?P<ipaddr>\d+\.\d+\.\d+\.\d+)\.%s' %
                re.escape(wildcard_domain))

        if self._debug_level > 0:
            print('wildcard %s' % pattern, file=sys.stderr)

        self._wildcard = re.compile(pattern)

        # Create regex pattern corresponding to conventional glob
        # style DNS wildcard mapping.

        self._mapping = None

        count = 1
        patterns = []
        results = {}

        if mapped_hosts:
            for inbound, outbound in mapped_hosts.items():
                label = 'RULE%s' % count
                inbound = re.escape(inbound).replace('\\*', '.*') 
                patterns.append('(?P<%s>%s)' % (label, inbound))
                results[label] = outbound
                count += 1

            pattern = '|'.join(patterns)

            if self._debug_level > 0:
                print('mapping %s' % pattern, file=sys.stderr)
                print('results %s' % results, file=sys.stderr)

            self._mapping = re.compile(pattern)
            self._mapping_results = results

    def _localLookup(self, name):
        if self._debug_level > 2:
            print('lookup %s' % name, file=sys.stderr)

        # First try and map xip.io style DNS wildcard.

        match = self._wildcard.match(name)

        if match:
            ipaddr = match.group('ipaddr')

            if self._debug_level > 1:
                print('wildcard %s --> %s' % (name, ipaddr), file=sys.stderr)

            return ipaddr

        # Next try and map conventional glob style wildcard mapping.

        if self._mapping is None:
            return

        match = self._mapping.match(name)

        if match:
            label = [k for k, v in match.groupdict().items() if v].pop()

            result = self._mapping_results[label]

            if self._debug_level > 1:
                print('mapping %s --> %s' % (name, result), file=sys.stderr)

            return result

    def lookupAddress(self, name, timeout=None):
        if self._debug_level > 2:
            print('address %s' % name, file=sys.stderr)

        result = self._localLookup(name)

        # If doesn't look like an IP address, try and look it up again
        # locally. Do this as many times as need to. Note there is no
        # protection against loops here.

        while result and result[0] not in string.digits:
            mapped = self._localLookup(result)
            if mapped is not None:
                result = mapped
            else:
                break

        if result:
            # Check if looks like IP address. If still not treat it like
            # a CNAME and lookup name using normal DNS lookup.

            if result[0] not in string.digits:
                if self._debug_level > 1:
                    print('cname %s' % result, file=sys.stderr)

                return client.Resolver.lookupAddress(self, result, timeout)

            payload=dns.Record_A(address=bytes(result))
            answer = dns.RRHeader(name=name, payload=payload)

            answers = [answer]
            authority = []
            additional = []

            return defer.succeed((answers, authority, additional))

        else:
            if self._debug_level > 2:
                print('fallback %s' % name, file=sys.stderr)

            return client.Resolver.lookupAddress(self, name, timeout)

def main():
    name_servers = os.environ.get('NAME_SERVERS', '8.8.8.8,8.8.4.4')

    server_list = []

    for address in name_servers.split(','):
        parts = address.strip().split(':')
        if len(parts) > 1:
            server_list.append((parts[0], int(parts[1])))
        elif parts:
            server_list.append((parts[0], 53))

    wildcard_domain = os.environ.get('WILDCARD_DOMAIN', 'xip.io')

    mapped_hosts = {}

    mapping_json = os.environ.get('MAPPED_HOSTS')

    if mapping_json and os.path.exists(mapping_json):
        with open(mapping_json) as fp:
            mapped_hosts = json.load(fp)

    debug_level = int(os.environ.get('DEBUG_LEVEL', '0'))

    factory = server.DNSServerFactory(
        clients=[DynamicResolver(servers=server_list,
            wildcard_domain=wildcard_domain,
            mapped_hosts=mapped_hosts,
            debug_level=debug_level)]
    )

    protocol = dns.DNSDatagramProtocol(controller=factory)

    reactor.listenUDP(53, protocol)
    reactor.listenTCP(53, factory)

    reactor.run()

if __name__ == '__main__':
    raise SystemExit(main())
