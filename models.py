
import logging
import time
from multiprocessing import Pool 
import numpy as np

log = logging.getLogger(__name__)

__all__ = ["Recommender", "Evaluation"]

class Recommender(object):
    def __init__(self, matrix):
        super(Recommender, self).__init__()
        self.matrix = matrix
        self.num_users = matrix.shape[0]
        self.num_items = matrix.shape[1]

    def train(self, before=None, after=None):
        raise NotImplementedError

    def predict(self, user, item):
        raise NotImplementedError

    def recommend(self, user, num=5, ruleout=True):
        scores = []
        for poi in xrange(self.num_items):
            scores.append((poi, self.predict(user, poi)))
        scores.sort(key=lambda x: x[1], reverse=True)

        if self.matrix is not None and ruleout:
            ruleouts = set(np.nonzero(self.matrix[user])[1])
        else:
            ruleouts = set()

        result = []
        for poi, score in scores:
            if poi in ruleouts:
                continue
            result.append(poi)
            if len(result) >= num:
                break
        return result 

        
def _proxy_test(args):
    evaluation, user, full = args
    bingos = evaluation.hits(user)
    n = len(bingos)
    if full and n > 0:
        log.debug("user %i hit %s" % (user, bingos))
    return (user, n)


class Evaluation(object):
    def __init__(self, matrix, model, N=5, users=None, _pool_num=6):
        """
        Evaluate a model.Report precision and recall.
        matrix: test checkin matrix, `sparse matrix`
        model: model for test, must has `recommend` methid
        N    : recommend N pois
        users: users for test, should be iterated
        _pool_num: thread number to test, most cases default is ok.
                    if 0, then turn off multiple threads.
        usage:
            >>> from scipy import sparse
            >>> import numpy as np
            >>> matrix = sparse.csr_matrix(np.matrix([[0, 1], [1, 1]]))
            >>> class M(object):
            ...     def recommend(self, u, N):
            ...         if u == 0:
            ...             return [1, -1, -1, -1, -1]
            ...         return [-1, -1, -1, -1, -1]
            >>> ev = Evaluation(matrix, model=M(), users=[0, 1], _pool_num=0)
            >>> ev.test()
            (0.5, 0.1)

        """
        self.matrix = matrix
        self.N = N
        self.model = model
        self._pool_num = _pool_num
        self.num_users = matrix.shape[0]
        self.num_items = matrix.shape[1]
        if users is None:
            self.users = xrange(self.num_users)
        else:
            self.users = users

    def hits(self, user):
        pois = set(np.nonzero(self.matrix[user])[1])
        if len(pois) <= 0:
            return []
        result = self.model.recommend(user, self.N)
        return list(set(pois) & set(result))

    def test(self, full=False):
        t0 = time.time()
        def prepare():
            for user in self.users:
                yield (self, user, full)

        if self._pool_num > 0:
            pool = Pool(self._pool_num)
            matchs = pool.map(_proxy_test, prepare()) 
            pool.close()
            pool.join()
        else:
            matchs = []
            for arg in prepare():
                matchs.append(_proxy_test(arg))
        
        nhits = sum([n for u, n in matchs])
        _recall = 0.0
        valid_num = 0
        for user, n in matchs:
            pois = np.nonzero(self.matrix[user])[1]
            if len(pois) > 0:
                valid_num += 1
                _recall += float(n) / len(pois)

        if valid_num == 0:
            raise ValueError("Checkin matrix should not be empty.")
        prec = float(nhits) / (valid_num * self.N)
        _recall = float(_recall) / valid_num 
        t1 = time.time()
        log.info("recall   : %.4f" % _recall)
        log.info("precision: %.4f" % prec)
        log.debug('time %.4f seconds' % (t1 - t0))
        return (_recall, prec)

