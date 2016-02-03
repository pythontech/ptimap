#=======================================================================
#       $Id: ptlisp.py,v 1.2 2012/08/29 07:20:28 pythontech Exp pythontech $
#	Parse lispy stuff as returned by IMAP
#
#	Can be a simple expression e.g.
#	 "(1 'foo')"
#	or a tuple as in result of fetch:
#	 ('OK',
#	  [('1 (RFC822.HEADER {3986}',
#	    'Return-path: ....X-Foo-bar\r\n\r\n'
#	   ),
#	   ')'
#	  ]
#	 )
#=======================================================================
_atomstart = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' \
    'abcdefghijklmnopqrstuvwxyz' \
    '\\$'
_atomchars = _atomstart + \
    '0123456789-.[]'

class Parser(object):
    '''Parser for lisp expression (as used in IMAP)'''
    def __init__(self, data):
        self.lines = [data]  if isinstance(data, str)  else list(data)
        self.string = ''
        self.inline = None

    class ParseError(Exception): pass
    class NoMoreItems(Exception): pass

    def parse(self):
        list = None
        self.pos = -1
        try:
            list = self._items()
        except IndexError:
#            print "EOF: parse"
            pass
        return list

    def _items(self):
        items = []
        while True:
            try:
                item = self._item()
#                print 'item:',item
                items.append(item)
            except Parser.NoMoreItems:
                return tuple(items)

    def _item(self):
        try:
            self._wh()
        except IndexError:
            raise self.NoMoreItems
        if self.c==')':
            self.pos -= 1
            raise self.NoMoreItems

        if self.c in '0123456789':
#            print "Start int"
            val = ord(self.c)-ord('0')
            try:
                while self._next() in '0123456789':
                    val = 10*val + ord(self.c)-ord('0')
            except IndexError:
                pass
            self.pos -= 1
            return val
        elif self.c=='(':
#            print "start list"
            try:
                inner = self._items()
            except IndexError:
                raise self.ParseError("Mismatched parens at end")
            if self._next() != ')':
                raise self.ParseError("Mismatched parens at '%s'" % self.c)
            return inner
        elif self.c=='"':
            string = ''
            while self._next() != '"':
                if self.c=='\\':
                    string += self._next()
                else:
                    string += self.c
            return string
        elif self.c in _atomstart:
            atom = self.c
            try:
                while self._next() in _atomchars:
                    atom += self.c
            except IndexError:
                pass
            self.pos -= 1
            # N.B. NIL can be an atom in astring context but not nstring
            return None  if atom=='NIL'  else atom
        elif self.c == '{':
            # IMAP counted string: {size} followed by data
            count = 0
            while self._next() in '0123456789':
                count = 10*count + ord(self.c)-ord('0')
            #print 'inline len = %d' % count
            if self.c != '}':
                #print 'No }'
                raise self.ParseError("Mismatched braces at '%s'" % self.c)
            if self.inline is None:
                #print 'No inline'
                raise self.ParseError('No inline data')
            val = self.inline
            #print 'using inline %r' % val
            self.inline = None
            return val
            
        else:
            raise self.ParseError("Unknown character '%s'" % self.c)

    def _wh(self):
        '''Skip whitespace, returning next character'''
        while self._next() in ' \t\n':
            pass
        return self.c

    def _next(self):
        '''Get next character, save in self.c and return'''
        self.pos += 1
        while self.pos >= len(self.string):
            self._get_string()
            #print 'new string: %r' % self.string
            self.pos = 0
        self.c = self.string[self.pos]
        return self.c

    def _get_string(self):
        item = self.lines.pop(0)
        if isinstance(item, tuple):
            self.string, self.inline = item
        else:
            self.string, self.inline = item, None

if __name__=='__main__':
    import sys
    print Parser(sys.argv[1]).parse()
