from __future__ import print_function

import os
import sys
import re

from twisted.internet import reactor, defer
from twisted.names import client, dns, error, server

class DynamicResolver(object):
    """
    A resolver which implements xip.io style IP resolution based on name.

    """


    def __init__(self, wildcard_domain, debug_level):
        pattern = (r'.*\.(?P<ipaddr>\d+\.\d+\.\d+\.\d+)\.%s' %
                re.escape(wildcard_domain))

        if debug_level > 0:
            print('pattern %s' % pattern, file=sys.stderr)

        self._pattern = re.compile(pattern)

        self._debug_level = debug_level

    def _dynamicResponseRequired(self, query):
        """
        Check the query to determine if a dynamic response is required.

        """

        return query.type == dns.A and self._pattern.match(query.name.name)

    def _doDynamicResponse(self, query):
        """
        Calculate the response to a query.

        """

        name = query.name.name
        match = self._pattern.match(name)
        ipaddr = match.group('ipaddr')

        if self._debug_level > 0:
            print('match %s --> %s' % (name, ipaddr), file=sys.stderr)

        payload=dns.Record_A(address=bytes(ipaddr))
        answer = dns.RRHeader(name=name, payload=payload)

        answers = [answer]
        authority = []
        additional = []

        return answers, authority, additional

    def query(self, query, timeout=None):
        """
	Check if the query should be answered dynamically, otherwise
	dispatch to the fallback resolver.

        """

        if self._debug_level > 1:
            print('query %s %s' % (query.type, query.name.name), file=sys.stderr)

        if self._dynamicResponseRequired(query):
            return defer.succeed(self._doDynamicResponse(query))
        else:
            return defer.fail(error.DomainError())

def main():
    """
    Run the server.

    """

    resolv_conf = os.environ.get('RESOLV_CONF', 'etc/resolv.conf')
    wildcard_domain = os.environ.get('WILDCARD_DOMAIN', 'xip.io')

    debug_level = int(os.environ.get('DEBUG_LEVEL', '0'))

    factory = server.DNSServerFactory(
        clients=[DynamicResolver(wildcard_domain=wildcard_domain,
            debug_level=debug_level), client.Resolver(resolv=resolv_conf)]
    )

    protocol = dns.DNSDatagramProtocol(controller=factory)

    reactor.listenUDP(10053, protocol)
    reactor.listenTCP(10053, factory)

    reactor.run()

if __name__ == '__main__':
    raise SystemExit(main())
