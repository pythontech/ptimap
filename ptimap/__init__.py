#!/usr/bin/env python
#=======================================================================
#	$Id: ptimap.py,v 1.1 2012/04/30 07:56:11 pythontech Exp pythontech $
#	Various actions on IMAP folders
#=======================================================================
import imaplib
from .lisp import Parser as LispParser
import time
import sys
import logging

IMAPError = imaplib.IMAP4.error

_log = logging.getLogger(__name__)

def _chk(resval):
    if resval[0] != 'OK':
        raise Exception(resval[1])
    return resval[1]

def _parse(text):
    '''Parse a lisp expression'''
    try:
        return LispParser(text).parse()
    except Exception as e:
        raise Exception('Error parsing %r: %s' % (text, e))

def _msglist(msgs):
    return ','.join([str(x) for x in msgs])

class Account(object):
    def __init__(self,host,user,password,
                 ssl=False,port=None,directory=''):
        self.host = host
        self.user = user
        self.password = password
        self.ssl = ssl
        if port is None:
            port = 993  if ssl  else 143
        self.port = port
        self.directory = directory
        self.uid = True # False

    @classmethod
    def from_file(cls, filename, acct):
        '''Instantiate an Account from a config file'''
        import ConfigParser, os
        cp = ConfigParser.ConfigParser()
        cp.read(os.path.expanduser(filename)) # No error if no such file
        return cls.from_config(cp, acct)

    @classmethod
    def from_config(cls, cp, acct):
        '''Instantiate an Account from a ConfigParser'''
        from ConfigParser import NoOptionError
        host = cp.get(acct,'host')
        user = cp.get(acct,'user')
        password = cp.get(acct,'password')
        try:
            ssl = cp.getboolean(acct,'ssl')
        except NoOptionError:
            ssl = False
        try:
            port = cp.getint(acct,'port')
        except NoOptionError:
            port = None
        try:
            directory = cp.get(acct,'directory')
        except NoOptionError:
            directory = ''
        return cls(host, user, password, ssl=ssl,port=port,directory=directory)

    def info(self,text):
        _log.info('%s', text)
    def debug(self,text):
        _log.debug('%s', text)

    def login(self):
        '''Connect to server and authenticate'''
        self.debug('connecting to %s:%d' % (self.host, self.port))
        if self.ssl:
            self._imap = imaplib.IMAP4_SSL(self.host, self.port)
        else:
            self._imap = imaplib.IMAP4(self.host, self.port)
        self.debug("Logging in to %s as %s" % (self.host, self.user))
        v = _chk(self._imap.login(self.user, self.password))
        self.debug('<<< '+v[0])
        return v

    def namespace(self):
        data = _chk(self._imap.namespace())
        self.debug(data)
        lst = _parse(data[0])
        return lst

    def folders(self,parent=None):
        if parent is None and self.directory=='':
            data = _chk(self._imap.list())
        else:
            path = []
            if self.directory != '':
                path.append(self.directory)
            if parent is not None:
                path.append(parent)
            data = _chk(self._imap.list('/'.join(path)))
        self.debug(data)
        return map(lambda x: _parse(x), data)

    def select(self, folder):
        if self.directory != '':
            folder = '%s/%s' % (self.directory, folder)
        data = _chk(self._imap.select(folder))
        self.debug(data)
        return _parse(data[0])[0]

    def search(self, *args):
        if self.uid:
            lst = _chk(self._imap.uid('search',None,*args))
        else:
            lst = _chk(self._imap.search(None,*args))
        self.debug(str(lst))
        return _parse(lst[0])

    def copy(self, msgs,dest):
        mspec = _msglist(msgs)
        if self.uid:
            lst = _chk(self._imap.uid('copy',mspec,dest))
        else:
            lst = _chk(self._imap.copy(mspec,dest))
        return

    def store(self, msgs,flags):
        mspec = _msglist(msgs)
        fspec = '('+' '.join(flags)+')'
        #print 'mspec',mspec,'fspec',fspec
        if self.uid:
            lst = _chk(self._imap.uid('store',mspec,'+FLAGS',fspec))
        else:
            lst = _chk(self._imap.store(mspec,'+FLAGS',fspec))
        self.debug(str(lst))
        return map(lambda x: _parse(x), lst)

