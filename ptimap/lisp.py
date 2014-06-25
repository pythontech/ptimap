#=======================================================================
#       $Id: ptlisp.py,v 1.2 2012/08/29 07:20:28 pythontech Exp pythontech $
#	Parse lispy stuff as returned by IMAP
#=======================================================================
_atomstart = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' \
    'abcdefghijklmnopqrstuvwxyz' \
    '\\$'
_atomchars = _atomstart + \
    '0123456789-'

class Parser:
    '''Parser for lisp expression (as used in IMAP'''
    def __init__(self, string):
        self.string = string

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
                raise self.ParseError, "Mismatched parens at end"
            if self._next() != ')':
                raise self.ParseError, "Mismatched parens at '%s'" % self.c
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
            return atom
        else:
            raise self.ParseError, "Unknown character '%s'" % self.c

    def _wh(self):
        '''Skip whitespace, returning next character'''
        while self._next() in ' \t\n':
            pass
        return self.c

    def _next(self):
        '''Get next character, save in self.c and return'''
        self.pos += 1
        self.c = self.string[self.pos]
        return self.c

if __name__=='__main__':
    import sys
    print Parser(sys.argv[1]).parse()
