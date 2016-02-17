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
    """Check result of command."""
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
    def __init__(self, host, user, password,
                 ssl=False, port=None, directory=''):
        self.host = host
        self.user = user
        self.password = password
        self.ssl = ssl
        if port is None:
            port = 993  if ssl  else 143
        self.port = port
        self.directory = directory
        self.uid = True # False
        self.logged_in = False
        self.selected = None    # folder name

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
        self.logged_in = True
        return v

    def _ensure_logged_in(self):
        if not self.logged_in:
            self.login()

    def namespace(self):
        data = _chk(self._imap.namespace())
        self.debug(data)
        lst = _parse(data[0])
        return lst

    def iterfolders(self, parent=None):
        """Iterate over all folders in the account."""
        self._ensure_logged_in()
        for flags, sep, path in self._folders(parent):
            # flags, sep, path
            folder = Folder(self, flags, sep, path)
            yield folder

    def folders(self, parent=None):
        """Get list of all folders."""
        return list(self.iterfolders(parent))

    def _folders(self, parent=None):
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
        return [_parse(x)  for x in data]

    def select(self, foldername):
        if self.directory != '':
            foldername = '%s/%s' % (self.directory, foldername)
        data = _chk(self._imap.select(foldername))
        # number of messages
        self.debug(data)
        self.selected = foldername
        return _parse(data[0])[0]

    def search(self, *args):
        if self.uid:
            lst = _chk(self._imap.uid('search',None,*args))
        else:
            lst = _chk(self._imap.search(None,*args))
        self.debug(str(lst))
        uids = _parse(lst[0])
        return uids

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

class Folder(object):
    def __init__(self, account, flags, sep, path):
        self.account = account
        self.flags = flags
        self.sep = sep
        self.path = path

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.path)

    def _ensure_selected(self):
        if self.account.selected is not self.path:
            self.account.select(self.path)

    def iteremails(self):
        self._ensure_selected()
        for uid in self.account.search('UNDELETED'):
            yield Email(self, uid)

    def emails(self):
        return list(self.iteremails())

    def get_fields(self, uids, fields):
        """Get set of fields for set of emails.
        E.g. uids=(2,3) fields=('ENVELOPE','RFC822.TEXT')
        return {2: {'ENVELOPE': env2, 'RFC822.TEXT': text2}
        3: {'ENVELOPE': env3, 'RFC822.TEXT': text3}}
        """
        self._ensure_selected()
        uexpr = ','.join([str(u) for u in uids])
        fexpr = '(' + ' '.join(fields) + ')'
        _log.debug('uexpr=%r fexpr=%r', uexpr, fexpr)
        if self.account.uid:
            res = self.account._imap.uid('fetch', uexpr, fexpr)
        else:
            res = self.account._imap.fetch(uexpr, fexpr)
        unvlist = _parse(res[1])
        _log.debug('unvlist=%r', unvlist)
        uf = {}
        if self.account.uid:
            # (1, ('UID', 2348, 'ENVELOPE', (...)), ...)
            for id, nv in _iterpairs(unvlist):
                f = dict(_iterpairs(nv))
                uid = f.pop('UID')
                uf[uid] = f
        else:
            # (67, ('ENVELOPE', (...)), ...)
            for uid, nv in _iterpairs(unvlist):
                f = dict(_iterpairs(nv))
                uf[uid] = f
        return uf

class Email (object):
    def __init__(self, folder, uid):
        self.folder = folder
        self.uid = uid
        self.attr = {}

    @property
    def date(self):
        env = self._ensure_envelope()
        return env[0]

    @property
    def subject(self):
        env = self._ensure_envelope()
        return env[1]

    @property
    def from_(self):
        env = self._ensure_envelope()
        return _env_address(env[2])

    @property
    def sender(self):
        env = self._ensure_envelope()
        return _env_address(env[3])

    @property
    def reply_to(self):
        env = self._ensure_envelope()
        return _env_address(env[4])

    @property
    def to(self):
        env = self._ensure_envelope()
        return _env_address(env[5])

    @property
    def cc(self):
        env = self._ensure_envelope()
        return _env_address(env[6])

    @property
    def bcc(self):
        env = self._ensure_envelope()
        return _env_address(env[7])

    @property
    def message_id(self):
        env = self._ensure_envelope()
        return env[9]

    @property
    def flags(self):
        return self._ensure_attr('FLAGS')

    @property
    def size(self):
        return self._ensure_attr('RFC822.SIZE')

    def _ensure_envelope(self):
        # date, subject, from, sender, reply-to, to, cc, bcc,
        #  in-reply-to, message-id
        return self._ensure_attr('ENVELOPE')

    def _ensure_attr(self, name):
        if name not in self.attr:
            self.attr.update(self._get_fields((name,)))
        return self.attr[name]

    def write_to(self, file):
        # Use BODY.PEEK[] to avoid setting as seen
        data = self._get_fields(('BODY.PEEK[]',))
        file.write(data['BODY[]'])

    def _get_fields(self, fields):
        data = self.folder.get_fields((self.uid,), fields)
        return data[self.uid]

def _iterpairs(lst):
    for i in xrange(0,len(lst),2):
        yield lst[i], lst[i+1]

def _env_address(lst):
    if lst is None:
        return None
    return ['%s@%s' % (d[2], d[3])  for d in lst]
