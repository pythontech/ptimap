#=======================================================================
#       
#=======================================================================
import os

class LinkCache(object):
    """Manage sets of files using hard links to share common members.
    """
    def __init__(self, cachedir, sublen=None):
        self.cachedir = cachedir
        self.sublen = sublen

    def has_cached(self, key):
        cached = self._cachepath(key)
        if cached:
            return True
        return False

    def _cachepath(self, key, new=False):
        cached = os.path.join(self.cachedir, key)
        if os.path.exists(cached):
            return cached
        if self.sublen  and  len(key) > self.sublen:
            cached = os.path.join(self.cachedir,
                                  key[:self.sublen],
                                  key[self.sublen:])
            if os.path.exists(cached)  or  new:
                return cached
        return None

    def use_cached(self, key, path):
        """Use the cached version to populate the destination."""
        cached = self._cachepath(key)
        try:
            os.remove(path)
        except OSError: pass
        os.link(cached, path)

    def add_to_cache(self, key, path):
        cached = self._cachepath(key, new=True)
        if os.path.exists(cached):
            raise ValueError('Key already in cache')
        cachedir = os.path.dirname(cached)
        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
        os.link(path, cached)

if __name__=='__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('-c','--cachedir', default='.cache',
                    help='Cache directory (default: .cache)')
    ap.add_argument('-l','--sublength', type=int,
                    help='Length of subdirectory prefix')
    ap.add_argument('key')
    ap.add_argument('path')
    args = ap.parse_args()
    lc = LinkCache(args.cachedir, args.sublength)
    if lc.has_cached(args.key):
        lc.use_cached(args.key, args.path)
    else:
        lc.add_to_cache(args.key, args.path)
