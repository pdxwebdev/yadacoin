import os
import socket
import asyncio
import functools
import tornado
import dns.resolver
from ipaddress import IPv4Network, IPv4Address, AddressValueError, ip_address
from networkutil.addressing import get_my_addresses
from dns.message import from_wire, make_response
from tornado.iostream import IOStream
from yadacoin.core.config import get_config
from yadacoin.core.peer import User
from configurationutil import Configuration, cfg_params
from dns.rcode import NXDOMAIN


DEFAULT_FORWARDER = u'0.0.0.0'

def get_all_forwarders(interface=None):
    try:
        dns_forwarders = [
            "208.67.222.222"
        ]

    except KeyError as err:
        raise NoForwardersConfigured(err)

    else:
        if len(dns_forwarders) == 0:
            raise NoForwardersConfigured(u'No Forwarders have been configured for {int}'.format(int=interface))

    # logging.debug(dns_forwarders)

    # Return a copy so that modifications of the retrieved do not get modified in config unless explicitly requested!
    return dns_forwarders[:] if type(dns_forwarders) == list else dns_forwarders.copy()

def get_forwarders_by_interface(interface):
    return get_all_forwarders(interface=interface)

def get_default_forwarder():
    return get_all_forwarders(interface=DEFAULT_FORWARDER)

def get_active_redirect_record_for_host(host):

    host = host[:-1] if host.endswith('.') else host

    #logging.debug(u'lookup active redirect record for {h}'.format(h=host))

    if not host.endswith('yadaproxy'):
        raise NoActiveRecordForHost(host)

    return {
        "redirect_host": "default",
        "active": True
    }

def get_redirect_hostname_for_host(host):
    redirect_hostname = get_active_redirect_record_for_host(host)[REDIRECT_HOST]

    if not redirect_hostname:
        raise Exception(u'Active record, but no hostname redirection for {host}'.format(host=host))

    return redirect_hostname


class MultipleForwardersForInterface(Exception):
    pass


class DNSQueryFailed(Exception):
    pass


class NoActiveRecordForHost(Exception):
    pass


class NoForwardersConfigured(Exception):
    pass


class UDPServer(asyncio.DatagramProtocol):

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, address):
        try:

            # Try to narrow down interface from client address
            # We are assuming a /24 network as this is the most common for LAN's

            # Start with the server interface
            interface = '0.0.0.0'

            # Get the client network to test our interfaces against
            client_net = IPv4Network(u'{ip}/24'.format(ip=address[0]),
                                     strict=False)

            # Search for an interface address on the same network as the client
            for addr in get_my_addresses():
                try:
                    if IPv4Address(u'{ip}'.format(ip=addr)) in client_net:
                        interface = addr
                        break  # We found a matching address so no point looping through remaining addresses!

                except AddressValueError:
                    pass

            # Create query
            query = DNSQuery(data=data,
                             client_address=address,
                             interface=interface)
            get_config().app_log.debug(query.question.name)
            if query.question.name[-2].decode() == 'yadaproxy':
                UDPServer.inbound_streams[User.__name__][address[0]] = str(''.join([x.decode() for x in query.question.name[:2]]))
            # Make query & Respond to the client
            self.transport.sendto(query.resolve(), address)

            pass #logging.info(query.message)

        except DNSQueryFailed as err:
            pass #logging.error(err)

        except Exception as err:
            pass #logging.exception(err)

def move_address_to_another_network(address,
                                    network,
                                    netmask):

    address = ip_address(address.encode('utf-16', errors='surrogatepass'))
    target_network = IPv4Network(u'{ip}/{netmask}'.format(ip=network,
                                                          netmask=netmask),
                                 strict=False)

    network_bits = int(target_network.network_address)
    interface_bits = int(address) & int(target_network.hostmask)

    target_address = network_bits | interface_bits

    return ip_address(target_address)


class DNSQuery(object):

    def __init__(self,
                 data,
                 client_address=None,
                 interface=None):

        self.data = data
        self.decoded = from_wire(data)
        self.question = self.decoded.question[0]
        # .question[0].rdtype=
        #   covers=0
        #   deleting=None
        #   items=[]
        #   name=www.google.com ['www','google','com','']
        #   rdclass=1
        #   rdtype=28
        #   ttl=0

        self.client_address = client_address
        self.interface = interface if interface is not None else u'default'
        self.message = u''
        self._ip = None
        self.error = u''
        # TODO: Handle IPV6, or at least throw an appropriate error if AAAA is received.

    @property
    def ip(self):
        return self._ip

    @ip.setter
    def ip(self,
           ip):
        self._ip = IPv4Address(u'{ip}'.format(ip=ip))

    def resolve(self):

        name = self.question.name
        self.message = u'DNS ({dns}): {name}: ?.?.?.?. '.format(dns=self.interface,
                                                                name=self.question.name)

        # Handle reverse lookups
        if u'.in-addr.arpa.' in name:
            # TODO: Can we not just forward these?  No will return host not IP?
            self.error = u'Cannot handle reverse lookups yet!'
            return self._bad_reply()

        #logging.debug(u'resolve name: {h}'.format(h=name))

        # Check if we have a locally configured record for requested name
        try:
            redirect_record = get_active_redirect_record_for_host(name.to_text())
            pass #logging.debug(u'redirect record: {r}'.format(r=redirect_record))

        except NoActiveRecordForHost:
            # Forward request
            self.message += u'Forwarding request. '
            answer = self._forward_request(name)
            try:
                answer.response.id = self.decoded.id
            except AttributeError:
                ip = 'NXDOMAIN'  # Don't know this for sure
                encoded = answer.to_wire()
            else:
                ip = answer.response.answer[0].items[0]
                encoded = answer.response.to_wire()
        else:
            # Attempt to resolve locally
            answer = self._resolve_request_locally(redirect_record)
            ip = answer.answer[0].items[0]
            encoded = answer.to_wire()

        self.message = self.message.replace(u'?.?.?.?', str(ip))

        return encoded

    def _resolve_request_locally(self,
                                 redirect_host):

        redirection = redirect_host['redirect_host']

        if redirection.lower() == u'default':
            if self.interface == u'0.0.0.0':  # This string is the DEFAULT_INTERFACE constant of DNSServer object!
                self.error = u'Cannot resolve default as client interface could not be determined!'
                return self._bad_reply()

            redirection = self.interface
            self.message += (u'Redirecting to default address. ({address}) '.format(address=redirection))

        elif '/' in redirection:
            if self.interface == u'0.0.0.0':  # This string is the DEFAULT_INTERFACE constant of DNSServer object!
                self.error = (u'Cannot resolve {redirection} as client interface could not be determined!'
                              .format(redirection=redirection))
                return self._bad_reply()

            address, netmask = redirection.split('/')
            redirection = move_address_to_another_network(address=address,
                                                          network=self.interface,
                                                          netmask=netmask)
            self.message += (u'Redirecting to {address}. '.format(address=redirection))

        # Check whether we already have an IP (A record)
        # Note: For now we only support IPv4
        try:
            IPv4Address(u'{ip}'.format(ip=redirection))

        except AddressValueError:
            # Attempt to resolve CNAME
            redirected_address = self._forward_request(redirection)

        else:
            # We already have the A record
            redirected_address = redirection

        self.message += (u'Redirecting to {redirection} '.format(redirection=redirection))

        self.ip = redirected_address

        # Use of make_response and appending rrset taken from
        # https://programtalk.com/python-examples/dns.message.make_response/
        response = make_response(self.decoded)
        answer = dns.rrset.from_text(str(self.decoded.question[0].name),  # name
                                     600,                                 # ttl
                                     self.decoded.question[0].rdclass,    # rdclass
                                     self.decoded.question[0].rdtype,     # rdtype
                                     redirected_address)                  # *text_rdatas
        response.answer.append(answer)

        return response

    def _forward_request(self,
                         name):

        try:
            response = self._resolve_name_using_dns_resolver(name)

        except (NoForwardersConfigured, DNSQueryFailed) as err:
            self.message += u'No forwarders found for request. '
            response = dns.message.make_response(self.decoded)
            response.set_rcode(NXDOMAIN)

        return response

    def _resolve_name_using_socket(self,
                                   name):

        # TODO: Ought to add some basic checking of name here

        try:
            address = socket.gethostbyname(str(name))
            self.message += u"(socket). "

        except socket.gaierror as err:
            raise DNSQueryFailed(u'Resolve name ({name}) using socket failed: {err} '
                                 .format(name=name,
                                         err=err))

        else:
            return address

    def _resolve_name_using_dns_resolver(self,
                                         name):

        try:
            network = IPv4Network(u'{ip}/24'.format(ip=self.interface),
                                  strict=False)

            forwarders = get_forwarders_by_interface(network.with_prefixlen)
            pass #logging.debug(u'Using forwarder config: {fwd} '.format(fwd=forwarders))

        except (NoForwardersConfigured,
                MultipleForwardersForInterface,
                AddressValueError,
                ValueError):
            forwarders = get_default_forwarder()
            pass #logging.debug(u'Using default forwarder config: {fwd} '.format(fwd=forwarders))

        resolver = dns.resolver.Resolver()
        resolver.timeout = 1
        resolver.lifetime = 3
        resolver.nameservers = forwarders

        try:
            result = resolver.query(qname=name,
                                    rdtype=self.question.rdtype,
                                    rdclass=self.question.rdclass,
                                    source='0.0.0.0')

            address = result[0].address

            self.message += u'(dns.resolver). '

            pass #logging.debug(u'Address for {name} via dns.resolver from nameservers - {source} '
            pass #              u'on interface {interface}: {address}'.format(name=name,
            pass #                                                            source=u', '.join(forwarders),
            pass #                                                            interface=self.interface,
            pass #                                                            address=address))

        except (IndexError, dns.exception.DNSException, dns.exception.Timeout, AttributeError) as err:
            self.message += u'(dns.resolver failed). '
            raise DNSQueryFailed(u'dns.resolver failed: {err}'.format(err=err))

        else:
            return result

    def _reply(self):

        packet = b''
        packet += self.data[:2] + b"\x81\x80"
        packet += self.data[4:6] + self.data[4:6] + b'\x00\x00\x00\x00'     # Questions and Answers Counts
        packet += self.data[12:]                                            # Original Domain Name Question
        packet += b'\xc0\x0c'                                               # Pointer to domain name
        packet += b'\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04'               # Response type, ttl and resource data length -> 4 bytes
        packet += self.ip.packed                                            # 4 bytes of IP

        return packet

    def _bad_reply(self):
            # TODO: Figure out how to return rcode 2 or 3
            # DNS Response Code | Meaning
            # ------------------+-----------------------------------------
            # RCODE:2           | Server failed to complete the DNS request
            # RCODE:3           | this code signifies that the domain name
            #                   | referenced in the query does not exist.
            #logging.warning(self.error)
            # For now, return localhost,
            # which should fail on the calling machine
            self.ip = u'127.0.0.1'

            return self._reply()