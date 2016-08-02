#!/usr/bin/env python3

import aiohttp
import asyncio
import datetime
import gzip
import json
import shellish

loop = asyncio.get_event_loop()


class GelfServerProtocol(object):

    def connection_made(self, transport):
        pass

    def datagram_received(self, data, addr):
        log = json.loads(gzip.decompress(data).decode())
        dt = datetime.datetime.utcfromtimestamp(log['timestamp'])
        log['timestamp'] = dt.isoformat()
        log['message'] = log['short_message']
        del log['short_message']
        log['host_addr'] = addr[0]
        if self.verbose:
            shellish.vtmlprint('<b>LOG:<b>', log)
        asyncio.ensure_future(self.relaylog(log))

    async def relaylog(self, log):
        data = json.dumps(log)
        try:
            with aiohttp.Timeout(60):
                async with self.es_session.post(self.es_url, data=data) as r:
                    if r.status != 201:
                        shellish.vtmlprint('<b><red>ES POST ERROR:</red> %s</b>' %
                                           (await r.text()))
                    elif self.verbose:
                        shellish.vtmlprint('<b>ES INDEX:</b>', await r.text())
        except asyncio.TimeoutError:
            shellish.vtmlprint('<b><red>ES POST TIMEOUT</red></b>')


@shellish.autocommand
def gelf_es_relay(elasticsearch_url, listen_addr='0.0.0.0', listen_port=12201,
                  verbose=False, es_conn_limit=100):
    """ A Gelf server relay to elasticsearch.

    The URL should contain the /index/type args as per the elasticsearch API.

    E.g. https://elasticsearch/logs/docker
    """
    addr = listen_addr, listen_port
    listen = loop.create_datagram_endpoint(GelfServerProtocol, local_addr=addr)
    transport, protocol = loop.run_until_complete(listen)
    protocol.verbose = verbose
    conn = aiohttp.TCPConnector(limit=es_conn_limit)
    protocol.es_session = aiohttp.ClientSession(loop=loop, connector=conn)
    protocol.es_url = elasticsearch_url
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    transport.close()
    loop.close()

gelf_es_relay()
