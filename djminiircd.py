#! /usr/bin/env python
# Hey, Emacs! This is -*-python-*-.
#
# Copyright (C) 2003-2014 Joel Rosdahl
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA
#
# Joel Rosdahl <joel@rosdahl.net>

VERSION = "0.4"

import os
import re
import sys
from optparse import OptionParser
from miniircd import Client, Server
from django.contrib.auth import authenticate

class DjangoClient(Client):
    def __init__(self, server, socket):
        super(DjangoClient, self).__init__(server, socket)
        self._Client__handle_command = self.__registration_handler

    def __registration_handler(self, command, arguments):

        server = self.server
        if command == "PASS":
            if len(arguments) == 0:
                self.reply_461("PASS")
            else:
                self.password = arguments[0]
        elif command == "NICK":
            if len(arguments) < 1:
                self.reply("431 :No nickname given")
                return
            nick = arguments[0]
            if server.get_client(nick):
                self.reply("433 * %s :Nickname is already in use" % nick)
            elif not self._Client__valid_nickname_regexp.match(nick):
                self.reply("432 * %s :Erroneous nickname" % nick)
            else:
                user = authenticate(username=nick, password=self.password)
                print "User: ", user
                if not user:
                    server.print_debug('Wrong password')
                    self.reply("464 :Password incorrect")
                else:
                    server.print_debug('User %s authenticated' % nick)
                    self.nickname = nick
                    server.client_changed_nickname(self, None)
        elif command == "USER":
            if len(arguments) < 4:
                self.reply_461("USER")
                return
            self.user = arguments[0]
            self.realname = arguments[3]
        elif command == "QUIT":
            self.disconnect("Client quit")
            return
        if self.nickname and self.user:
            self.reply("001 %s :Hi, welcome to IRC" % self.nickname)
            self.reply("002 %s :Your host is %s, running version miniircd-%s"
                       % (self.nickname, server.name, VERSION))
            self.reply("003 %s :This server was created sometime"
                       % self.nickname)
            self.reply("004 %s :%s miniircd-%s o o"
                       % (self.nickname, server.name, VERSION))
            self.send_lusers()
            self.send_motd()
            self._Client__handle_command = self._Client__command_handler

class DjangoServer(Server):
    def client_factory(self, conn):
        return DjangoClient(self, conn)


def main(argv):
    op = OptionParser(
        version=VERSION,
        description="miniircd is a small and limited IRC server.")
    op.add_option(
        "-d", "--daemon",
        action="store_true",
        help="fork and become a daemon")
    op.add_option(
        "--debug",
        action="store_true",
        help="print debug messages to stdout")
    op.add_option(
        "--logdir",
        metavar="X",
        help="store channel log in directory X")
    op.add_option(
        "--motd",
        metavar="X",
        help="display file X as message of the day")
    op.add_option(
        "-s", "--ssl-pem-file",
        metavar="FILE",
        help="enable SSL and use FILE as the .pem certificate+key")
    op.add_option(
        "--ports",
        metavar="X",
        help="listen to ports X (a list separated by comma or whitespace);"
             " default: 6667 or 6697 if SSL is enabled")
    op.add_option(
        "--statedir",
        metavar="X",
        help="save persistent channel state (topic, key) in directory X")
    op.add_option(
        "--verbose",
        action="store_true",
        help="be verbose (print some progress messages to stdout)")
    if os.name == "posix":
        op.add_option(
            "--chroot",
            metavar="X",
            help="change filesystem root to directory X after startup"
                 " (requires root)")
        op.add_option(
            "--setuid",
            metavar="U[:G]",
            help="change process user (and optionally group) after startup"
                 " (requires root)")

    (options, args) = op.parse_args(argv[1:])
    options.password = None
    if options.debug:
        options.verbose = True
    if options.ports is None:
        if options.ssl_pem_file is None:
            options.ports = "6667"
        else:
            options.ports = "6697"
    if options.chroot:
        if os.getuid() != 0:
            op.error("Must be root to use --chroot")
    if options.setuid:
        from pwd import getpwnam
        from grp import getgrnam
        if os.getuid() != 0:
            op.error("Must be root to use --setuid")
        match = re.findall(r"([a-z_][a-z0-9_-]*\$?)", options.setuid)
        if len(match) > 1:
            options.setuid = (int(getpwnam(match[0]).pw_uid),
                              int(getgrnam(match[1]).gr_gid))
        elif len(match) == 1:
            options.setuid = (int(getpwnam(match[0]).pw_uid),
                              int(getpwnam(match[0]).pw_gid))
        else:
            op.error("Specify a user, or user and group separated by a colon,"
                     " e.g. --setuid daemon, --setuid nobody:nobody")
    if (os.getuid() == 0 or os.getgid() == 0) and not options.setuid:
        op.error("Running this service as root is not recommended. Use the"
                 " --setuid option to switch to an unprivileged account after"
                 " startup. If you really intend to run as root, use \"--setuid"
                 " root\".")

    ports = []
    for port in re.split(r"[,\s]+", options.ports):
        try:
            ports.append(int(port))
        except ValueError:
            op.error("bad port: %r" % port)
    options.ports = ports
    server = DjangoServer(options)
    if options.daemon:
        server.daemonize()
    try:
        server.start()
    except KeyboardInterrupt:
        server.print_error("Interrupted.")


if __name__ == '__main__':
    main(sys.argv)
