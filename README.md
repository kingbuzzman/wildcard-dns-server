# Wildcard DNS server

Experimental Docker image for a DNS server implementing ``xip.io`` style
DNS wildcards, more conventional glob style DNS wildcard mappings, as well
as pass through for all other lookups.

This could be done using a very lightweight Docker image, but I am using
the Twisted framework from Python as it more easily allows me to experiment
with intercepting DNS lookups for other purposes.

## Building the image

To build the image yourself, first determine if you are happy with using
Google DNS servers as a fallback for pass through DNS queries.

If you do not want to use Google DNS and want to use whatever is your
existing DNS provider, then copy the ``/etc/resolv.conf`` file from your
local system into this directory as ``etc/resolv.conf``. This should be
done before modifying any DNS settings to send queries via an instance of
this image as you will otherwise get an infinite loop.

```
cp /etc/resolv.conf etc/resolv.conf
```

Alternatively, leave the default ``etc/resolv.conf`` as being for Google
and you can provide a replacement using Docker volume mounting.

If you want to provide a mapping table for glob style DNS wildcards,
replace ``etc/mapping.json`` with your own file, where the format is a JSON
style dictionary.

```
{
    "*.foo.com": "127.0.0.1",
    "www.bar.com": "bar.com",
    "bar.com": "127.0.0.1"
}
```

The target of the match should be an IP address, or a host name. Where it
maps to a host name, that should be resolvable via subsequent applications
of the mapping table, or via a public DNS lookup.

As with the ``/etc/resolv.conf`` file, you can instead provide a
replacement using Docker volume mounting.

Now build the image:

```
docker build -t wildcard-dns-server .
```

## Running the image

Use Docker to run the image. When doing this you should map ports for both
TCP and UDP ports of the DNS server.

```
docker run -e --rm -p 53:10053/tcp -p 53:10053/udp wildcard-dns-server
```

By default the IP wildcards will use the ``xip.io`` domain as the default.
To override the domain use the ``WILDCARD_DOMAIN`` environment variable.

```
docker run -e WILDCARD_DOMAIN=wildcard.dev --rm -p 53:10053/tcp -p 53:10053/udp wildcard-dns-server
```

To test that the latter works, use the command:

```
dig @$(docker-machine ip default) myapp.10.2.2.2.wildcard.dev A +short
```

In this example, you should get the result ``10.2.2.2``. Also try with other
valid public addresses such as ``www.google.com`` and you should get back a
list of the IPs for that service.

If you want to provide a ``resolv.conf`` file when the image is being run,
place it in a directory, and then use volume mounting to add that directory
at the location ``/usr/src/app/etc`` in the container.

```
docker run -e --rm -p 53:10053/tcp -p 53:10053/udp -v /somepath/etc:/usr/src/app/etc wildcard-dns-server
```

You can use mounting to also provide a mapping file for glob style DNS
wildcard matches. Just be aware that if providing a mapping file, you
must also provide a ``resolv.conf`` at the same time even if not
overriding the default of using Google DNS as a fallback.

## Using registry image

If you don't want to build the image yourself and are happy to trust an
automated build image from Docker Hub Registry, then you can pull it down
from there.

```
docker pull grahamdumpleton/wildcard-dns-server
```

The image uses the official Docker ``python:2.7-onbuild`` image as the base
image. As per best practice security measures, the image is set up not to
run as root, using the default ``www-data`` user.

## Update your DNS settings

Once you are happy that the image is running okay, then update the DNS
settings of your system to point at the IP address of the Docker service
host. You can get the IP address of the Docker service host by running:

```
docker-machine ip default
```

Note that for some systems, eg., MacOS X, there is no DNS active at all
when you have no active WiFi or Ethernet connection. You cannot therefore
readily still use this to allow local offline development for ``xip.io``
style addresses. You would in this case still need to be connected to an
ethernet router, or need something like a physical ethernet loop back
dongle to trick the operating system into thinking you have an actual
connection.

## Debugging DNS lookups

To debug DNS lookups as they pass through the DNS server implemented by
the image, you can set the ``DEBUG_LEVEL`` environment variable. The highest
level of debug is ``2``.

```
docker run -e DEBUG_LEVEL=2 -e WILDCARD_DOMAIN=wildcard.dev --rm -p 53:10053/tcp -p 53:10053/udp wildcard-dns-server
```

At the highest level you can see wildcard DNS name matches, as well as pass
through requests.

```
wildcard .*\.(?P<ipaddr>\d+\.\d+\.\d+\.\d+)\.wildcard\.dev
query 1 myapp.10.2.2.2.wildcard.dev
lookup myapp.10.2.2.2.wildcard.dev
wildcard myapp.10.2.2.2.wildcard.dev --> 10.2.2.2
query 1 www.google.com
lookup www.google.com
```
