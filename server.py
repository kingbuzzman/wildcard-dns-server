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


    def __init__(self, resolv, wildcard_domain, mapping_table=None,
            debug_level=0):

        client.Resolver.__init__(self, resolv=resolv)

        self._debug_level = debug_level

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

        if mapping_table:
            for inbound, outbound in mapping_table.items():
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

            if self._debug_level > 2:
                print('wildcard %s --> %s' % (name, ipaddr), file=sys.stderr)

            return ipaddr

        # Next try and map conventional glob style wildcard mapping.

        if self._mapping is None:
            return

        match = self._mapping.match(name)

        if match:
            label = [k for k, v in match.groupdict().items() if v].pop()

            result = self._mapping_results[label]

            if self._debug_level > 2:
                print('mapping %s --> %s' % (name, result), file=sys.stderr)

            return result

    def lookupAddress(self, name, timeout=None):
        if self._debug_level > 1:
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
                if self._debug_level > 2:
                    print('cname %s' % result, file=sys.stderr)

                return client.Resolver.lookupAddress(self, result, timeout)

            payload=dns.Record_A(address=bytes(result))
            answer = dns.RRHeader(name=name, payload=payload)

            answers = [answer]
            authority = []
            additional = []

            return defer.succeed((answers, authority, additional))

        else:
            return client.Resolver.lookupAddress(self, name, timeout)

def main():
    resolv_conf = os.environ.get('RESOLV_CONF', 'etc/resolv.conf')

    wildcard_domain = os.environ.get('WILDCARD_DOMAIN', 'xip.io')

    mapping_json = os.environ.get('MAPPING_JSON', 'etc/mapping.json')

    if mapping_json and os.path.exists(mapping_json):
        with open(mapping_json) as fp:
            mapping_table = json.load(fp)

    debug_level = int(os.environ.get('DEBUG_LEVEL', '0'))

    factory = server.DNSServerFactory(
        clients=[DynamicResolver(resolv=resolv_conf,
            wildcard_domain=wildcard_domain,
            mapping_table=mapping_table,
            debug_level=debug_level)]
    )

    protocol = dns.DNSDatagramProtocol(controller=factory)

    reactor.listenUDP(10053, protocol)
    reactor.listenTCP(10053, factory)

    reactor.run()

if __name__ == '__main__':
    raise SystemExit(main())
