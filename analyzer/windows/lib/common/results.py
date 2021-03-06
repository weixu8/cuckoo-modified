# Copyright (C) 2010-2015 Cuckoo Foundation.
# This file is part of Cuckoo Sandbox - http://www.cuckoosandbox.org
# See the file 'docs/LICENSE' for copying permission.

import logging
import socket
import time

from lib.core.config import Config

log = logging.getLogger(__name__)

BUFSIZE = 1024*1024

def upload_to_host(file_path, dump_path, duplicate):
    nc = infd = None
    try:
        nc = NetlogBinary(file_path, dump_path, duplicate)
        if not duplicate:
            infd = open(file_path, "rb")
            buf = infd.read(BUFSIZE)
            while buf:
                nc.send(buf, retry=False)
                buf = infd.read(BUFSIZE)
    except Exception as e:
        log.error("Exception uploading file %s to host: %s", file_path, e)
    finally:
        if infd:
            infd.close()
        if nc:
            nc.close()

class NetlogConnection(object):
    def __init__(self, proto=""):
        config = Config(cfg="analysis.conf")
        self.hostip, self.hostport = config.ip, config.port
        self.sock, self.file = None, None
        self.proto = proto

    def connect(self):
        i = 1
        # this can loop forever, if we can't connect the whole analysis is useless anyways
        while True:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.connect((self.hostip, self.hostport))
                s.sendall(self.proto)
            except:
                time.sleep(i)
                i = min(i + 1, 60)
            else:
                self.sock = s
                self.file = s.makefile()
                break

    def send(self, data, retry=True):
        if not self.sock: self.connect()

        try:
            self.sock.sendall(data)
        except socket.error as e:
            if retry:
                self.connect()
                self.send(data, retry=False)
            else:
                raise
        except Exception as e:
            log.error("Unhandled exception in NetlogConnection: %s", str(e))
            # We really have nowhere to log this, if the netlog connection
            # does not work, we can assume that any logging won't work either.
            # So we just fail silently.
            self.close()

    def close(self):
        try:
            self.file.close()
            self.sock.close()
        except Exception:
            pass

class NetlogBinary(NetlogConnection):
    def __init__(self, guest_path, uploaded_path, duplicated):
        if duplicated:
            NetlogConnection.__init__(self, proto="DUPLICATEBINARY\n{0}\n{1}\n".format(uploaded_path, guest_path))
        else:
            NetlogConnection.__init__(self, proto="BINARY\n{0}\n{1}\n".format(uploaded_path, guest_path))
        self.connect()

class NetlogFile(NetlogConnection):
    def __init__(self, filepath):
        NetlogConnection.__init__(self, proto="FILE\n{0}\n".format(filepath))
        self.connect()

class NetlogHandler(logging.Handler, NetlogConnection):
    def __init__(self):
        logging.Handler.__init__(self)
        NetlogConnection.__init__(self, proto="LOG\n")
        self.connect()

    def emit(self, record):
        msg = self.format(record)
        self.send("{0}\n".format(msg))
